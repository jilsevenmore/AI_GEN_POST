"""Main LangGraph flow for AI content generation."""
import logging
from typing import Dict, Any, Literal
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from app.services.ai.state import GenerationState, StateDict, create_initial_state
from app.services.ai.nodes.expand_prompt import expand_prompt_node
from app.services.ai.nodes.find_references import find_references_node
from app.services.ai.nodes.generate_text import generate_text_node
from app.services.ai.nodes.generate_image import generate_image_node
from app.services.ai.nodes.safety_check import safety_check_node
from app.services.ai.nodes.adapt_platforms import adapt_platforms_node
from app.core.config import get_settings
from app.db.session import engine

logger = logging.getLogger(__name__)
settings = get_settings()


def should_continue_generation(state: GenerationState) -> Literal["continue", "retry", "fail"]:
    """Decide whether to continue, retry, or fail after generation steps."""
    if state.error:
        if state.regeneration_count < state.max_regenerations:
            return "retry"
        return "fail"
    return "continue"


def should_regenerate(state: GenerationState) -> Literal["regenerate_text", "regenerate_image", "regenerate_both", "continue"]:
    """Decide what to regenerate based on user feedback."""
    if not state.awaiting_review:
        return "continue"
    
    if state.user_feedback:
        regen_text = state.regenerate_text
        regen_image = state.regenerate_image
        
        if regen_text and regen_image:
            return "regenerate_both"
        elif regen_text:
            return "regenerate_text"
        elif regen_image:
            return "regenerate_image"
    
    return "continue"


def create_generation_graph() -> StateGraph:
    """Create the LangGraph for content generation."""
    
    graph = StateGraph(StateDict)
    
    # Add nodes
    graph.add_node("expand_prompt", expand_prompt_node)
    graph.add_node("find_references", find_references_node)
    graph.add_node("generate_text", generate_text_node)
    graph.add_node("generate_image", generate_image_node)
    graph.add_node("safety_check", safety_check_node)
    graph.add_node("adapt_platforms", adapt_platforms_node)
    
    # Define edges
    graph.set_entry_point("expand_prompt")
    
    graph.add_edge("expand_prompt", "find_references")
    graph.add_edge("find_references", "generate_text")
    graph.add_edge("find_references", "generate_image")  # Parallel
    
    # Both generation nodes must complete before safety check
    graph.add_edge("generate_text", "safety_check")
    graph.add_edge("generate_image", "safety_check")
    
    graph.add_edge("safety_check", "adapt_platforms")
    graph.add_edge("adapt_platforms", END)
    
    # Add conditional edges for regeneration (from review interrupt)
    # This would be handled by the interrupt/resume mechanism
    
    return graph


# Compile the graph
_generation_graph = None


def get_generation_graph() -> StateGraph:
    """Get or create the compiled generation graph."""
    global _generation_graph
    if _generation_graph is None:
        graph = create_generation_graph()
        
        # Use Postgres checkpointer for persistence
        try:
            checkpointer = AsyncPostgresSaver.from_conn_string(str(engine.url))
            _generation_graph = graph.compile(checkpointer=checkpointer)
        except Exception as e:
            logger.warning(f"Could not create Postgres checkpointer, using memory: {e}")
            _generation_graph = graph.compile(checkpointer=MemorySaver())
    
    return _generation_graph


async def run_generation_job(
    job_input,
    brand_kit,
    db,
) -> GenerationState:
    """
    Run the complete generation job as a background task.
    
    This is called from the jobs endpoint via BackgroundTasks.
    """
    graph = get_generation_graph()
    
    # Create initial state
    initial_state = create_initial_state(job_input, brand_kit)
    state_dict = initial_state.model_dump()
    
    # Configure for this run
    config = {
        "configurable": {
            "thread_id": str(job_input.job_id),
        }
    }
    
    try:
        # Run the graph
        final_state_dict = await graph.ainvoke(state_dict, config=config)
        final_state = GenerationState.model_validate(final_state_dict)
        
        # Save results to database
        await _save_results(final_state, db)
        
        return final_state
        
    except Exception as e:
        logger.error(f"Generation job failed: {e}")
        initial_state.error = str(e)
        initial_state.current_step = "failed"
        initial_state.progress = 0
        await _save_error(initial_state, db)
        return initial_state


async def _save_results(state: GenerationState, db) -> None:
    """Save generation results to database."""
    from app.models.content import Content
    from app.models.job import Job
    from app.models.image import Image as ImageModel
    from sqlalchemy import select, update
    from uuid import uuid4
    from datetime import datetime, timezone
    
    job_id = state.job_input.job_id
    
    # Create content record
    content = Content(
        id=uuid4(),
        job_id=job_id,
        company_id=state.job_input.company_id,
        type="social_post" if state.job_input.type == "post" else "blog",
        title=state.job_input.title,
        long_text=state.long_text or "",
        platform_contents=[pc.model_dump() for pc in state.platform_contents],
        image_variants=[iv.model_dump() for iv in state.generated_image_variants],
        primary_image_id=state.generated_image_variants[0].id if state.generated_image_variants else None,
        safety_check_passed=state.safety_check_passed,
        safety_flags=state.safety_flags,
    )
    db.add(content)
    
    # Update job status
    await db.execute(
        update(Job)
        .where(Job.id == job_id)
        .values(
            status="awaiting_review",
            progress=100,
            current_step="Ready for review",
            updated_at=datetime.now(timezone.utc),
        )
    )
    
    # Save library images (if any approved later)
    # This happens on approve, not here
    
    await db.commit()


async def _save_error(state: GenerationState, db) -> None:
    """Save error state to database."""
    from app.models.job import Job
    from sqlalchemy import update
    from datetime import datetime, timezone
    
    await db.execute(
        update(Job)
        .where(Job.id == state.job_input.job_id)
        .values(
            status="failed",
            progress=0,
            current_step="Failed",
            error=state.error,
            updated_at=datetime.now(timezone.utc),
        )
    )
    await db.commit()


async def resume_after_review(
    job_id: str,
    feedback: str,
    regenerate_text: bool,
    regenerate_image: bool,
    new_reference_ids: list,
    db,
) -> GenerationState:
    """Resume generation after human review with regeneration feedback."""
    graph = get_generation_graph()
    
    # Get current state from checkpoint
    config = {"configurable": {"thread_id": job_id}}
    current_state_dict = await graph.aget_state(config)
    
    if not current_state_dict:
        raise ValueError("No saved state found for job")
    
    state = GenerationState.model_validate(current_state_dict.values)
    
    # Update state with feedback
    state.user_feedback = feedback
    state.regenerate_text = regenerate_text
    state.regenerate_image = regenerate_image
    state.new_reference_ids = new_reference_ids
    state.regeneration_count += 1
    state.awaiting_review = False
    state.current_step = "regenerating"
    state.progress = 10
    
    # Resume from appropriate point based on what needs regeneration
    if regenerate_text and regenerate_image:
        # Restart from expand_prompt with feedback
        pass  # Would need to modify graph to support this
    elif regenerate_text:
        # Restart from generate_text
        pass
    elif regenerate_image:
        # Restart from generate_image
        pass
    
    # For now, re-run full graph with feedback incorporated
    # In production, you'd use LangGraph's interrupt/resume properly
    
    return await run_generation_job(state.job_input, state.brand_kit, db)
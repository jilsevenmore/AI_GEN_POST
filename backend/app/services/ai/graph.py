"""Main LangGraph flow for AI content generation."""
import logging
from typing import Dict, Any, Literal, Optional
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
# from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver  # Disabled due to psycopg issues
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


def should_generate_image(state: GenerationState) -> Literal["generate_image", "skip_image"]:
    """Decide whether to generate an image based on user toggle."""
    # User toggle takes precedence: if they disabled image generation, skip it
    if not state.job_input.generate_image:
        return "skip_image"
    return "generate_image"


def create_generation_graph() -> StateGraph:
    """Create the LangGraph for content generation."""
    
    graph = StateGraph(StateDict)
    
    # Add nodes
    graph.add_node("expand_prompt", expand_prompt_node)
    graph.add_node("find_references", find_references_node)
    graph.add_node("generate_text", generate_text_node)
    graph.add_node("generate_image", generate_image_node)
    graph.add_node("skip_image", lambda state: state)  # Pass-through for blog posts
    graph.add_node("safety_check", safety_check_node)
    graph.add_node("adapt_platforms", adapt_platforms_node)
    
    # Define edges
    graph.set_entry_point("expand_prompt")
    
    graph.add_edge("expand_prompt", "find_references")
    graph.add_edge("find_references", "generate_text")
    
    # Conditional: generate image for social posts, skip for blogs
    graph.add_conditional_edges(
        "find_references",
        should_generate_image,
    )
    
    # Both generation paths converge at safety_check
    graph.add_edge("generate_text", "safety_check")
    graph.add_edge("generate_image", "safety_check")
    graph.add_edge("skip_image", "safety_check")
    
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
        
        # Use MemorySaver for checkpointing (Postgres checkpointer disabled due to psycopg issues)
        _generation_graph = graph.compile(checkpointer=MemorySaver())
    
    return _generation_graph


async def run_generation_job(
    job_id_str: str,
    company_id_str: str,
    db_session_factory,
    user_feedback: Optional[str] = None,
    regenerate_text: bool = False,
    regenerate_image: bool = False,
    new_reference_ids: list = None,
) -> GenerationState:
    """
    Run the complete generation job as a background task.
    
    This is called from the jobs endpoint via BackgroundTasks.
    Accepts job_id and company_id as strings (avoids Pydantic serialization issues),
    then re-queries the database for full job and brand kit data.
    
    Optional regeneration parameters are applied to the initial state so a
    review-driven regeneration can incorporate user feedback.
    """
    from app.db.session import AsyncSessionLocal
    from app.models.job import Job
    from app.models.brand_kit import BrandKit
    from sqlalchemy import select, update
    from uuid import UUID
    from app.services.ai.state import JobInput, BrandKitData
    from datetime import datetime, timezone
    
    job_id = UUID(job_id_str)
    company_id = UUID(company_id_str)
    
    logger.info(f"🚀 Starting generation job {job_id} (company={company_id})")
    
    # Create a fresh DB session (the request session is closed by now)
    async with AsyncSessionLocal() as db:
        # Query the job from database
        result = await db.execute(select(Job).where(Job.id == job_id))
        db_job = result.scalar_one_or_none()
        if not db_job:
            logger.error(f"❌ Job {job_id} not found in database")
            raise RuntimeError(f"Job {job_id} not found")
        
        # Query brand kit from database
        brand_result = await db.execute(
            select(BrandKit).where(BrandKit.company_id == company_id)
        )
        brand_kit_model = brand_result.scalar_one_or_none()
        if not brand_kit_model:
            # Create default brand kit
            brand_kit_model = BrandKit(company_id=company_id, company_name="Demo Company")
            db.add(brand_kit_model)
            await db.commit()
            await db.refresh(brand_kit_model)
        
        # Build JobInput from database record
        job_input = JobInput(
            job_id=db_job.id,
            company_id=company_id,
            type=db_job.type,
            title=db_job.title,
            topic=db_job.topic,
            tone=db_job.tone,
            audience=db_job.audience,
            keywords=db_job.keywords or [],
            image_description=db_job.image_description,
            platforms=db_job.platforms or [],
            use_references=db_job.use_references,
            reference_image_ids=db_job.reference_image_ids or [],
            source_context=db_job.source_context_text,
            instagram_post_type=db_job.instagram_post_type,
            instagram_cover_image_url=db_job.instagram_cover_image_url,
            aspect_ratios=db_job.aspect_ratios or [],
            generate_image=db_job.generate_image,
        )
        
        brand_kit_data = BrandKitData(
            company_name=brand_kit_model.company_name or "Demo Company",
            tagline=brand_kit_model.tagline,
            address=brand_kit_model.address,
            logo_url=str(brand_kit_model.logo_url) if brand_kit_model.logo_url else None,
            primary_color=brand_kit_model.primary_color,
            secondary_color=brand_kit_model.secondary_color,
            tone=brand_kit_model.tone,
            use_openai_only=brand_kit_model.use_openai_only,
        )
        
        logger.info(f"📋 Loaded job {job_id}: type={db_job.type}, topic={db_job.topic}")
        logger.info(f"🎨 Loaded brand kit: {brand_kit_data.company_name}")
        
        # Create initial state using Pydantic models
        initial_state = create_initial_state(job_input, brand_kit_data)

        # Apply regeneration feedback if provided, so a review-driven
        # regeneration carries the user's instructions into the state.
        if user_feedback:
            initial_state.user_feedback = user_feedback
            initial_state.regenerate_text = regenerate_text
            initial_state.regenerate_image = regenerate_image
            initial_state.new_reference_ids = new_reference_ids or []
            initial_state.regeneration_count += 1

        # Call AI nodes directly (bypasses LangGraph Pydantic serialization issues)
        from app.services.ai.nodes.expand_prompt import expand_prompt_node
        from app.services.ai.nodes.find_references import find_references_node
        from app.services.ai.nodes.generate_text import generate_text_node
        from app.services.ai.nodes.generate_image import generate_image_node
        from app.services.ai.nodes.safety_check import safety_check_node
        from app.services.ai.nodes.adapt_platforms import adapt_platforms_node
        
        state = initial_state

        from app.services.job_events import publish_job_event

        async def _update_progress(step: str, progress: int, status: str = "pending"):
            try:
                await db.execute(
                    update(Job)
                    .where(Job.id == job_id)
                    .values(
                        status=status,
                        progress=progress,
                        current_step=step,
                        updated_at=datetime.now(timezone.utc),
                    )
                )
                await db.commit()
                publish_job_event(
                    str(job_id),
                    {
                        "id": str(job_id),
                        "status": status,
                        "progress": progress,
                        "current_step": step,
                        "error": None,
                    },
                )
            except Exception as e:
                logger.warning(f"Failed to update job progress for {job_id}: {e}")
                await db.rollback()
        
        try:
            await _update_progress("Expanding prompt", 10, "expanding_prompt")
            logger.info(f"🔄 Step 1: Expanding prompt for job {job_id}")
            state = await expand_prompt_node(state)
            
            if state.job_input.generate_image and state.job_input.use_references:
                await _update_progress("Finding references", 25, "expanding_prompt")
                logger.info(f"🔄 Step 2: Finding references for job {job_id}")
                state = await find_references_node(state, db)
            else:
                logger.info(f"⏩ Skipping finding references for job {job_id} (generate_image={state.job_input.generate_image})")
            
            await _update_progress("Writing text", 40, "writing_text")
            logger.info(f"🔄 Step 3a: Generating text for job {job_id}")
            state = await generate_text_node(state)
            
            # Generate image only if generate_image was requested by user
            should_gen_image = state.job_input.generate_image and (not user_feedback or regenerate_image)
            if should_gen_image:
                await _update_progress("Generating image", 60, "generating_image")
                logger.info(f"🔄 Step 3b: Generating image for job {job_id}")
                state = await generate_image_node(state)
            else:
                logger.info(f"⏩ Skipping image generation for job {job_id} (generate_image={state.job_input.generate_image})")
                if not state.job_input.generate_image:
                    state.generated_image_variants = []
            
            await _update_progress("Running safety checks", 80, "safety_check")
            logger.info(f"🔄 Step 4: Safety check for job {job_id}")
            state = await safety_check_node(state)
            
            await _update_progress("Adapting for platforms", 90, "adapting")
            logger.info(f"🔄 Step 5: Adapting platforms for job {job_id}")
            state = await adapt_platforms_node(state)
            
            logger.info(f"✅ Generation job {job_id} completed successfully")
            await _save_results(state, db, company_id)
            return state
            
        except Exception as e:
            logger.error(f"❌ Generation job {job_id} failed: {e}", exc_info=True)
            await db.execute(
                update(Job)
                .where(Job.id == job_id)
                .values(
                    status="failed",
                    progress=0,
                    current_step="Failed",
                    error=str(e),
                    updated_at=datetime.now(timezone.utc),
                )
            )
            await db.commit()
            publish_job_event(
                str(job_id),
                {
                    "id": str(job_id),
                    "status": "failed",
                    "progress": 0,
                    "current_step": "Failed",
                    "error": str(e),
                },
            )
            return None


async def _save_results(state: GenerationState, db, company_id) -> None:
    """Save generation results to database."""
    from app.models.content import Content
    from app.models.job import Job
    from app.models.image import Image as ImageModel
    from sqlalchemy import select, update
    from uuid import uuid4
    from datetime import datetime, timezone
    
    job_id = state.job_input.job_id
    
    # Check if content already exists for this job (e.g. on regeneration or retry)
    existing_result = await db.execute(select(Content).where(Content.job_id == job_id))
    content = existing_result.scalar_one_or_none()
    
    primary_img_id = state.generated_image_variants[0].id if state.generated_image_variants else None
    image_variants_json = [iv.model_dump(mode='json') for iv in state.generated_image_variants]
    platform_contents_json = [pc.model_dump(mode='json') for pc in state.platform_contents]

    if content:
        content.title = state.job_input.title
        content.long_text = state.long_text or ""
        content.platform_contents = platform_contents_json
        content.image_variants = image_variants_json
        content.primary_image_id = primary_img_id
        content.safety_check_passed = state.safety_check_passed
        content.safety_flags = state.safety_flags
    else:
        content = Content(
            id=uuid4(),
            job_id=job_id,
            company_id=company_id,
            type="social_post" if state.job_input.type == "post" else "blog",
            title=state.job_input.title,
            long_text=state.long_text or "",
            platform_contents=platform_contents_json,
            image_variants=image_variants_json,
            primary_image_id=primary_img_id,
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
    from app.services.job_events import publish_job_event
    publish_job_event(
        str(state.job_input.job_id),
        {
            "id": str(state.job_input.job_id),
            "status": "awaiting_review",
            "progress": 100,
            "current_step": "Ready for review",
            "error": state.error,
        },
    )


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
    from app.services.job_events import publish_job_event
    publish_job_event(
        str(state.job_input.job_id),
        {
            "id": str(state.job_input.job_id),
            "status": "failed",
            "progress": 0,
            "current_step": "Failed",
            "error": state.error,
        },
    )


async def resume_after_review(
    job_id: str,
    feedback: str,
    regenerate_text: bool,
    regenerate_image: bool,
    new_reference_ids: list,
    db,
) -> GenerationState:
    """Resume generation after human review with regeneration feedback."""
    from uuid import UUID
    from sqlalchemy import select
    from app.db.session import AsyncSessionLocal
    from app.models.job import Job

    job_uuid = UUID(str(job_id))
    result = await db.execute(select(Job).where(Job.id == job_uuid))
    db_job = result.scalar_one_or_none()

    if not db_job:
        raise ValueError(f"Job {job_id} not found")

    # Re-run the generation from the original job input, carrying the
    # review feedback into the new state so nodes can act on it.
    return await run_generation_job(
        str(db_job.id),
        str(db_job.company_id),
        AsyncSessionLocal,
        user_feedback=feedback,
        regenerate_text=regenerate_text,
        regenerate_image=regenerate_image,
        new_reference_ids=new_reference_ids,
    )
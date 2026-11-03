"""Node 3a: Generate text content (runs in parallel with image generation)."""
import logging
from langchain_core.messages import SystemMessage, HumanMessage
from app.services.ai.state import GenerationState
from app.services.ai.router import get_model_router

logger = logging.getLogger(__name__)

TEXT_GENERATION_PROMPT = """You are an expert content writer. Write the content based on the brief.

Text Brief:
- Outline: {outline}
- Key Points: {key_points}
- Target Length: {target_length} words
- Style Guidance: {style_guidance}

Brand Context:
- Company: {company_name}
- Tagline: {tagline}
- Tone: {tone}
- Address: {address}

Reference Images: {reference_info}

Requirements:
1. Write engaging, platform-agnostic content
2. For blogs: Full article with headings
3. For social posts: Core message that can be adapted
4. Naturally incorporate brand details
5. Include the address naturally if relevant

Return ONLY the written content as plain text (no JSON, no markdown unless requested)."""


async def generate_text_node(state: GenerationState) -> GenerationState:
    """Generate the main text content."""
    job = state.job_input
    brand = state.brand_kit
    text_brief = state.text_brief
    
    if not text_brief:
        state.error = "No text brief available"
        return state
    
    # Build reference info
    ref_info = ""
    if state.reference_images:
        ref_info = f"Available reference images: {len(state.reference_images)} images for style/subject guidance."
    
    context = {
        "outline": text_brief.outline,
        "key_points": ", ".join(text_brief.key_points),
        "target_length": text_brief.target_length,
        "style_guidance": text_brief.style_guidance,
        "company_name": brand.company_name,
        "tagline": brand.tagline or "N/A",
        "tone": brand.tone or "professional",
        "address": brand.address or "N/A",
        "reference_info": ref_info,
    }
    
    router = get_model_router()
    
    messages = [
        SystemMessage(content=TEXT_GENERATION_PROMPT.format(**context)),
        HumanMessage(content="Write the content now."),
    ]
    
    try:
        result = await router.ainvoke(
            messages,
            require_json=False,
            company_openai_only=brand.use_openai_only,
        )
        generated = result.generations[0].text.strip()
        
        # For blogs, this is the long form; for posts, this is the base
        if job.type == "blog":
            state.long_text = generated
        else:
            # For social posts, this becomes the LinkedIn/long version
            state.long_text = generated
            state.generated_text = generated  # Base for adaptation
        
        state.model_used_text = "free_or_openai"  # Would track actual model
        
    except Exception as e:
        logger.error(f"Text generation failed: {e}")
        state.error = f"Text generation failed: {str(e)}"
        # Fallback
        state.generated_text = f"Content about {job.topic} for {brand.company_name}."
        state.long_text = state.generated_text
    
    state.current_step = "generating_image"
    state.progress = 55
    
    return state
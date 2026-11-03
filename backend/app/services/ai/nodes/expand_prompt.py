"""Node 1: Expand user prompt into detailed text and image briefs."""
import json
import logging
from typing import Dict, Any
from langchain_core.messages import SystemMessage, HumanMessage
from app.services.ai.state import GenerationState, TextBrief, ImageBrief
from app.services.ai.router import get_model_router

logger = logging.getLogger(__name__)

TEXT_BRIEF_PROMPT = """You are an expert content strategist. Expand the user's brief into a detailed text generation brief.

User Input:
- Type: {type}
- Title: {title}
- Topic: {topic}
- Tone: {tone}
- Audience: {audience}
- Keywords: {keywords}
- Platforms: {platforms}

Brand Context:
- Company: {company_name}
- Tagline: {tagline}
- Tone: {brand_tone}

Create a detailed JSON brief with:
1. outline: Structured outline for the content
2. key_points: List of key points to cover
3. target_length: Approximate word count target
3. style_guidance: Specific style instructions

Return ONLY valid JSON matching this schema:
{{
  "outline": "string",
  "key_points": ["string"],
  "target_length": integer,
  "style_guidance": "string"
}}"""

IMAGE_BRIEF_PROMPT = """You are an expert visual prompt engineer. Create a detailed image generation brief.

User Input:
- Type: {type}
- Title: {title}
- Topic: {topic}
- Image Description: {image_description}
- Platforms: {platforms}

Brand Context:
- Company: {company_name}
- Primary Color: {primary_color}
- Secondary Color: {secondary_color}

Create a detailed JSON brief with:
1. prompt: Complete image generation prompt for GPT Image 2.5 Sunburst
2. style_keywords: Visual style keywords
3. composition_guidance: Layout and composition instructions
4. aspect_ratio: Best aspect ratio for primary platform
5. reference_roles: If references available, map image_id to role (style/subject/logo)

Return ONLY valid JSON matching this schema:
{{
  "prompt": "string",
  "style_keywords": ["string"],
  "composition_guidance": "string",
  "aspect_ratio": "string",
  "reference_roles": {{"image_id": "role"}}
}}"""


async def expand_prompt_node(state: GenerationState) -> GenerationState:
    """Expand the user's short prompt into detailed briefs for text and image."""
    job = state.job_input
    brand = state.brand_kit
    
    # Prepare context
    context = {
        "type": job.type,
        "title": job.title,
        "topic": job.topic,
        "tone": job.tone or brand.tone or "professional",
        "audience": job.audience or "general audience",
        "keywords": ", ".join(job.keywords) if job.keywords else "none",
        "platforms": ", ".join(job.platforms),
        "company_name": brand.company_name,
        "tagline": brand.tagline or "none",
        "brand_tone": brand.tone or "professional",
        "image_description": job.image_description or "Create a relevant, engaging image",
        "primary_color": brand.primary_color or "#2563EB",
        "secondary_color": brand.secondary_color or "#7C3AED",
    }
    
    router = get_model_router()
    
    # Generate text brief
    text_messages = [
        SystemMessage(content=TEXT_BRIEF_PROMPT.format(**context)),
        HumanMessage(content="Generate the text brief."),
    ]
    
    try:
        text_result = await router.ainvoke(text_messages, require_json=True)
        text_brief_data = json.loads(text_result.generations[0].text)
        state.text_brief = TextBrief(**text_brief_data)
    except Exception as e:
        logger.error(f"Text brief generation failed: {e}")
        # Fallback brief
        state.text_brief = TextBrief(
            outline=f"Write about {job.topic}",
            key_points=job.keywords[:5] if job.keywords else ["Main topic"],
            target_length=800 if job.type == "blog" else 200,
            style_guidance=f"Tone: {context['tone']}. Audience: {context['audience']}.",
        )
    
    # Generate image brief
    image_messages = [
        SystemMessage(content=IMAGE_BRIEF_PROMPT.format(**context)),
        HumanMessage(content="Generate the image brief."),
    ]
    
    try:
        image_result = await router.ainvoke(image_messages, require_json=True)
        image_brief_data = json.loads(image_result.generations[0].text)
        state.image_brief = ImageBrief(**image_brief_data)
    except Exception as e:
        logger.error(f"Image brief generation failed: {e}")
        # Fallback brief
        state.image_brief = ImageBrief(
            prompt=f"Professional image about {job.topic}, {context['tone']} style",
            style_keywords=["professional", "clean", "modern"],
            composition_guidance="Centered composition, good lighting",
            aspect_ratio="1:1",
            reference_roles={},
        )
    
    # Update progress
    state.current_step = "finding_references"
    state.progress = 20
    
    return state
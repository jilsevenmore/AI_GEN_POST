"""Node 3b: Generate image using GPT Image 2.5 Sunburst (runs in parallel with text)."""
import logging
import uuid
import base64
import httpx
from typing import List, Optional
from app.services.ai.state import GenerationState, ImageVariant, ReferenceImage
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


async def generate_image_node(state: GenerationState) -> GenerationState:
    """Generate image variants using GPT Image 2.5 Sunburst."""
    job = state.job_input
    brand = state.brand_kit
    image_brief = state.image_brief
    
    if not image_brief:
        state.error = "No image brief available"
        return state
    
    variants: List[ImageVariant] = []
    
    # Determine aspect ratios based on platforms
    aspect_ratios = _get_aspect_ratios(job.platforms)
    
    # Prepare reference images for Sunburst
    reference_images = _prepare_references(state.reference_images)
    
    for i, aspect_ratio in enumerate(aspect_ratios):
        try:
            variant = await _generate_single_image(
                prompt=image_brief.prompt,
                aspect_ratio=aspect_ratio,
                reference_images=reference_images,
                is_primary=(i == 0),
                brand=brand,
            )
            if variant:
                variants.append(variant)
        except Exception as e:
            logger.error(f"Image generation failed for {aspect_ratio}: {e}")
            # Continue with other variants
    
    # If all failed, create placeholder
    if not variants:
        variants.append(_create_placeholder_variant(aspect_ratios[0] if aspect_ratios else "1:1"))
    
    state.generated_image_variants = variants
    state.current_step = "safety_check"
    state.progress = 70
    
    return state


def _get_aspect_ratios(platforms: List[str]) -> List[str]:
    """Determine needed aspect ratios from platforms."""
    ratios = set()
    for platform in platforms:
        if platform == "instagram":
            ratios.add("1:1")  # Square for feed
            ratios.add("4:5")  # Portrait for feed
            ratios.add("9:16")  # Stories/Reels
        elif platform == "facebook":
            ratios.add("1:1")
            ratios.add("4:5")
        elif platform == "linkedin":
            ratios.add("1.91:1")  # Landscape for feed
            ratios.add("1:1")
    
    # Always include square as default
    ratios.add("1:1")
    
    # Return max 3 variants (primary + 2)
    priority = ["1:1", "4:5", "1.91:1", "9:16"]
    return [r for r in priority if r in ratios][:3]


def _prepare_references(references: List[ReferenceImage]) -> List[dict]:
    """Prepare reference images for Sunburst API."""
    prepared = []
    for ref in references:
        if ref.role in ["style", "subject", "logo"]:
            prepared.append({
                "image_url": ref.url,
                "role": ref.role,
                "description": ref.prompt,
            })
    return prepared[:3]  # Sunburst works best with 1-3 refs


async def _generate_single_image(
    prompt: str,
    aspect_ratio: str,
    reference_images: List[dict],
    is_primary: bool,
    brand,
) -> Optional[ImageVariant]:
    """Generate a single image variant via Sunburst API."""
    
    # Parse aspect ratio to dimensions
    width, height = _aspect_to_dimensions(aspect_ratio)
    
    # Build the prompt with brand context
    full_prompt = _build_image_prompt(prompt, aspect_ratio, brand)
    
    # Call Sunburst API (using OpenAI-compatible endpoint)
    try:
        image_url = await _call_sunburst_api(
            prompt=full_prompt,
            size=f"{width}x{height}",
            reference_images=reference_images,
        )
        
        return ImageVariant(
            id=uuid.uuid4(),
            url=image_url,
            aspect_ratio=aspect_ratio,
            width=width,
            height=height,
            is_primary=is_primary,
            prompt_used=full_prompt,
            reference_image_ids=[],  # Would track actual ref IDs
        )
    except Exception as e:
        logger.error(f"Sunburst API call failed: {e}")
        raise


def _aspect_to_dimensions(aspect_ratio: str) -> tuple:
    """Convert aspect ratio to pixel dimensions."""
    ratios = {
        "1:1": (1024, 1024),
        "4:5": (1024, 1280),
        "1.91:1": (1024, 536),
        "9:16": (576, 1024),
    }
    return ratios.get(aspect_ratio, (1024, 1024))


def _build_image_prompt(base_prompt: str, aspect_ratio: str, brand) -> str:
    """Enhance prompt with brand context and technical specs."""
    parts = [base_prompt]
    
    if brand.primary_color:
        parts.append(f"Primary brand color: {brand.primary_color}")
    if brand.secondary_color:
        parts.append(f"Secondary brand color: {brand.secondary_color}")
    if brand.tone:
        parts.append(f"Visual tone: {brand.tone}")
    
    parts.append(f"Aspect ratio: {aspect_ratio}")
    parts.append("High quality, professional, sharp details")
    
    return " | ".join(parts)


async def _call_sunburst_api(
    prompt: str,
    size: str,
    reference_images: List[dict],
) -> str:
    """
    Call GPT Image 2.5 Sunburst API.
    
    Note: This uses the OpenAI-compatible endpoint. In production,
    you would use the actual Sunburst endpoint.
    """
    # For now, return a placeholder - real implementation would call:
    # POST https://api.openai.com/v1/images/generations (or Sunburst endpoint)
    # with model="gpt-image-2.5-sunburst"
    
    # Placeholder using picsum for development
    import random
    seed = random.randint(1, 1000000)
    return f"https://picsum.photos/seed/ai-gen-{seed}/{size.split('x')[0]}/{size.split('x')[1]}"


def _create_placeholder_variant(aspect_ratio: str) -> ImageVariant:
    """Create a placeholder variant when generation fails."""
    width, height = _aspect_to_dimensions(aspect_ratio)
    return ImageVariant(
        id=uuid.uuid4(),
        url=f"https://picsum.photos/seed/placeholder/{width}/{height}",
        aspect_ratio=aspect_ratio,
        width=width,
        height=height,
        is_primary=True,
        prompt_used="Placeholder - generation failed",
        reference_image_ids=[],
    )
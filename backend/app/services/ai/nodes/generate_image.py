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

# Platform-specific allowed aspect ratios for feed/image posts (based on official docs)
# Instagram feed image (Graph API): 4:5 to 1.91:1 range
# LinkedIn single image post: 3:1 to 4:5 (width:height)
# Facebook feed photo: commonly supported 1:1, 4:5, 1.91:1 (9:16 is story/reel oriented)
PLATFORM_ALLOWED_ASPECT_RATIOS = {
    "instagram": ["1:1", "4:5", "1.91:1"],
    "facebook": ["1:1", "4:5", "1.91:1"],
    "linkedin": ["1:1", "4:5", "1.91:1"],
}
ALL_ASPECT_RATIOS = ["1:1", "4:5", "1.91:1", "9:16"]


async def generate_image_node(state: GenerationState) -> GenerationState:
    """Generate image variants using GPT Image 2.5 Sunburst."""
    job = state.job_input
    brand = state.brand_kit
    image_brief = state.image_brief
    
    if not image_brief:
        state.error = "No image brief available"
        return state
    
    variants: List[ImageVariant] = []
    
    # Determine aspect ratios: user-specified ratios take precedence,
    # otherwise auto-select based on platforms.
    aspect_ratios = _get_aspect_ratios(job.platforms, user_ratios=job.aspect_ratios)
    
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


def _get_aspect_ratios(
    platforms: List[str],
    user_ratios: Optional[List[str]] = None,
) -> List[str]:
    """Determine needed aspect ratios from platforms.

    Filters to ratios allowed for the selected platforms based on official docs:
    - Instagram feed images (API): 4:5 to 1.91:1 (1:1, 4:5, 1.91:1)
    - LinkedIn single image posts: 3:1 to 4:5 width:height (1:1, 4:5, 1.91:1)
    - Facebook feed images: commonly 1:1, 4:5, 1.91:1 (9:16 is story/reel oriented)
    """
    priority = ["1:1", "4:5", "1.91:1", "9:16"]

    if platforms:
        allowed_sets = [set(PLATFORM_ALLOWED_ASPECT_RATIOS.get(p, ALL_ASPECT_RATIOS)) for p in platforms]
        allowed = set.intersection(*allowed_sets) if allowed_sets else set(ALL_ASPECT_RATIOS)
    else:
        allowed = set(ALL_ASPECT_RATIOS)
    if not allowed:
        allowed = {"1:1"}

    if user_ratios:
        ratios = {r for r in user_ratios if r in allowed}
        if ratios:
            return [r for r in priority if r in ratios][:3]

    # Auto-select based on platforms, constrained by allowed set
    ratios = set()
    for platform in platforms:
        if platform == "instagram":
            ratios.update({"1:1", "4:5"})
        elif platform == "facebook":
            ratios.update({"1:1", "4:5"})
        elif platform == "linkedin":
            ratios.update({"1.91:1", "1:1"})
    ratios &= allowed

    if not ratios:
        ratios = {"1:1"} & allowed or {"1:1"}

    # Return max 3 variants (primary + 2)
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
    """Convert aspect ratio to pixel dimensions (platform-friendly sizes)."""
    ratios = {
        "1:1": (1080, 1080),      # Universal square (IG/FB/LinkedIn)
        "4:5": (1080, 1350),      # Instagram/Facebook portrait feed
        "1.91:1": (1200, 628),    # LinkedIn/Facebook landscape
        "9:16": (1080, 1920),     # Stories/Reels (when applicable)
    }
    return ratios.get(aspect_ratio, (1080, 1080))


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
    Call GPT Image 2.5 Sunburst API using OpenAI-compatible endpoint.
    
    Uses the user's detailed enhanced prompt to generate images matching
    their specific description (e.g., "Professional CRM software dashboard...").
    """
    import httpx
    from app.core.config import get_settings
    
    settings = get_settings()
    
    if not settings.SUNBURST_API_KEY:
        raise RuntimeError("SUNBURST_API_KEY not configured")
    
    headers = {
        "Authorization": f"Bearer {settings.SUNBURST_API_KEY}",
        "Content-Type": "application/json",
    }
    
    payload = {
        "model": settings.SUNBURST_MODEL,  # "gpt-image-2.5-sunburst"
        "prompt": prompt,
        "size": size,
        "n": 1,
    }
    
    # Add reference images if available (Sunburst supports up to 16 refs)
    if reference_images:
        payload["reference_images"] = reference_images[:16]
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{settings.SUNBURST_BASE_URL}/images/generations",
            headers=headers,
            json=payload,
        )
        
        if response.status_code != 200:
            raise RuntimeError(f"Sunburst API error {response.status_code}: {response.text}")
        
        result = response.json()
        
        # Handle different response formats (url or b64_json)
        data_item = result.get("data", [{}])[0]
        image_url = data_item.get("url")
        
        if not image_url:
            # Try b64_json format (Sunburst may return base64)
            b64_json = data_item.get("b64_json")
            if b64_json:
                # Upload to Cloudinary when configured so Buffer/other platforms can fetch it
                image_url = _upload_image_to_cloudinary(b64_json)
                if not image_url:
                    image_url = f"data:image/png;base64,{b64_json}"
            else:
                raise RuntimeError("Sunburst API returned no image URL or b64_json")
        
        return image_url


def _upload_image_to_cloudinary(b64_data: str) -> Optional[str]:
    """Upload base64 image data to Cloudinary and return a public https URL."""
    if not (settings.CLOUDINARY_CLOUD_NAME and settings.CLOUDINARY_API_KEY and settings.CLOUDINARY_API_SECRET):
        logger.warning("Cloudinary not configured; keeping image as base64 data URL")
        return None
    try:
        import cloudinary
        import cloudinary.uploader

        cloudinary.config(
            cloud_name=settings.CLOUDINARY_CLOUD_NAME,
            api_key=settings.CLOUDINARY_API_KEY,
            api_secret=settings.CLOUDINARY_API_SECRET,
            secure=True,
        )
        # Accept raw base64 or data URL
        if b64_data.startswith("data:"):
            payload = b64_data
        else:
            payload = f"data:image/png;base64,{b64_data}"
        folder = settings.CLOUDINARY_FOLDER_PUBLISHED or "published"
        res = cloudinary.uploader.upload(payload, folder=folder, resource_type="image")
        url = res.get("secure_url") or res.get("url")
        if url:
            logger.info(f"Uploaded generated image to Cloudinary: {url}")
        return url
    except Exception as e:
        logger.error(f"Cloudinary upload failed, falling back to base64: {e}")
        return None


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
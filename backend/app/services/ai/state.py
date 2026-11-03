"""LangGraph state definitions for the AI generation flow."""
from typing import List, Optional, Dict, Any, Literal
from uuid import UUID
from pydantic import BaseModel, Field
from datetime import datetime


class BrandKitData(BaseModel):
    """Brand kit information for prompt injection."""
    company_name: str
    tagline: Optional[str] = None
    address: Optional[str] = None
    logo_url: Optional[str] = None
    primary_color: Optional[str] = None
    secondary_color: Optional[str] = None
    tone: Optional[str] = None
    use_openai_only: bool = False


class JobInput(BaseModel):
    """Input parameters from the user."""
    job_id: UUID
    type: Literal["blog", "post"]
    title: str
    topic: str
    tone: Optional[str] = None
    audience: Optional[str] = None
    keywords: List[str] = Field(default_factory=list)
    image_description: Optional[str] = None
    platforms: List[str] = Field(default_factory=list)
    use_references: bool = True
    reference_image_ids: List[UUID] = Field(default_factory=list)


class TextBrief(BaseModel):
    """Detailed brief for text generation."""
    outline: str
    key_points: List[str]
    target_length: int
    style_guidance: str


class ImageBrief(BaseModel):
    """Detailed brief for image generation."""
    prompt: str
    style_keywords: List[str]
    composition_guidance: str
    aspect_ratio: str
    reference_roles: Dict[str, str] = Field(default_factory=dict)  # image_id -> role


class ReferenceImage(BaseModel):
    """Reference image with metadata."""
    id: UUID
    url: str
    prompt: str
    tags: List[str]
    role: str  # "style", "subject", "logo"


class PlatformContent(BaseModel):
    """Content adapted for a specific platform."""
    platform: str
    text: str
    hashtags: List[str]
    character_count: int


class ImageVariant(BaseModel):
    """Generated image variant."""
    id: UUID
    url: str
    aspect_ratio: str
    width: int
    height: int
    is_primary: bool = False
    prompt_used: str
    reference_image_ids: List[UUID] = Field(default_factory=list)


class GenerationState(BaseModel):
    """Complete state for the LangGraph flow."""
    # Input
    job_input: JobInput
    brand_kit: BrandKitData
    
    # Progress tracking
    current_step: str = "starting"
    progress: int = 0
    error: Optional[str] = None
    
    # Step 1: Expand prompt
    text_brief: Optional[TextBrief] = None
    image_brief: Optional[ImageBrief] = None
    
    # Step 2: Find references
    reference_images: List[ReferenceImage] = Field(default_factory=list)
    
    # Step 3: Generate (parallel)
    generated_text: Optional[str] = None
    generated_image_variants: List[ImageVariant] = Field(default_factory=list)
    long_text: Optional[str] = None  # For blog/LinkedIn
    
    # Step 4: Safety check
    safety_passed: bool = True
    safety_flags: List[str] = Field(default_factory=list)
    
    # Step 5: Adapt per platform
    platform_contents: List[PlatformContent] = Field(default_factory=list)
    
    # Step 6: Human review (interrupt point)
    awaiting_review: bool = False
    regeneration_count: int = 0
    max_regenerations: int = 3
    user_feedback: Optional[str] = None
    regenerate_text: bool = True
    regenerate_image: bool = True
    new_reference_ids: List[UUID] = Field(default_factory=list)
    
    # Output
    final_content_id: Optional[UUID] = None
    completed_at: Optional[datetime] = None
    
    # Metadata
    model_used_text: Optional[str] = None
    model_used_image: Optional[str] = None
    fallback_used: bool = False
    cost_usd: float = 0.0


# Type alias for the state dict used by LangGraph
StateDict = Dict[str, Any]


def create_initial_state(job_input: JobInput, brand_kit: BrandKitData) -> GenerationState:
    """Create initial state for a new generation job."""
    return GenerationState(
        job_input=job_input,
        brand_kit=brand_kit,
        current_step="expanding_prompt",
        progress=5,
    )


def state_to_dict(state: GenerationState) -> StateDict:
    """Convert Pydantic state to dict for LangGraph."""
    return state.model_dump()


def dict_to_state(data: StateDict) -> GenerationState:
    """Convert dict to Pydantic state."""
    return GenerationState.model_validate(data)
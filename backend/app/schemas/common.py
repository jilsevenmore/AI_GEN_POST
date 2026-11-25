from pydantic import BaseModel, Field, HttpUrl
from typing import Optional, List, Literal, Dict, Any
from datetime import datetime
from uuid import UUID, uuid4
from enum import Enum


# ==========================================
# Base / Common
# ==========================================

class TimestampMixin(BaseModel):
    created_at: datetime
    updated_at: datetime


class IDMixin(BaseModel):
    id: UUID = Field(default_factory=uuid4)


# ==========================================
# Enums (using Enum instead of Literal subclasses for Python 3.12+ compatibility)
# ==========================================

class JobType(str, Enum):
    blog = "blog"
    post = "post"


class JobStatus(str, Enum):
    pending = "pending"
    expanding_prompt = "expanding_prompt"
    writing_text = "writing_text"
    generating_image = "generating_image"
    safety_check = "safety_check"
    adapting = "adapting"
    awaiting_review = "awaiting_review"
    approved = "approved"
    regenerating = "regenerating"
    publishing = "publishing"
    published = "published"
    failed = "failed"


class Platform(str, Enum):
    instagram = "instagram"
    facebook = "facebook"
    linkedin = "linkedin"


class ContentType(str, Enum):
    blog = "blog"
    social_post = "social_post"


class ImageAspectRatio(str, Enum):
    _1_1 = "1:1"
    _4_5 = "4:5"
    _1_91_1 = "1.91:1"
    _9_16 = "9:16"


class PublishStatus(str, Enum):
    pending = "pending"
    sent = "sent"
    failed = "failed"
    retrying = "retrying"


# ==========================================
# Auth Schemas
# ==========================================

class TokenBase(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class Token(TokenBase):
    pass


class TokenPayload(BaseModel):
    sub: UUID
    exp: int
    type: Literal["access", "refresh"]


class UserRegister(BaseModel):
    email: str
    password: str
    company_name: str


class UserLogin(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    id: UUID
    email: str
    company_id: UUID
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ==========================================
# Company / Brand Kit
# ==========================================

class BrandKitBase(BaseModel):
    company_name: str
    tagline: Optional[str] = None
    address: Optional[str] = None
    logo_url: Optional[HttpUrl] = None
    primary_color: Optional[str] = Field(None, pattern="^#[0-9A-Fa-f]{6}$")
    secondary_color: Optional[str] = Field(None, pattern="^#[0-9A-Fa-f]{6}$")
    tone: Optional[str] = None  # e.g., "professional", "friendly", "witty"
    use_openai_only: bool = False


class BrandKitCreate(BrandKitBase):
    pass


class BrandKitUpdate(BrandKitBase):
    company_name: Optional[str] = None


class BrandKitResponse(BrandKitBase, IDMixin, TimestampMixin):
    company_id: UUID

    class Config:
        from_attributes = True


# ==========================================
# Job / Generation Schemas
# ==========================================

class JobCreate(BaseModel):
    type: JobType
    title: str = Field(..., min_length=1, max_length=200)
    topic: str = Field(..., min_length=1, max_length=500)
    tone: Optional[str] = None
    audience: Optional[str] = None
    keywords: List[str] = Field(default_factory=list)
    image_description: Optional[str] = None
    platforms: List[Platform] = Field(default_factory=list)
    use_references: bool = True
    reference_image_ids: List[UUID] = Field(default_factory=list)
    source_context: Optional[str] = Field(
        None, max_length=50000,
        description="Extracted text from an attached source document (.md/.txt) used as generation context."
    )
    source_file_name: Optional[str] = Field(None, description="Original name of the attached source file.")
    source_file_url: Optional[str] = Field(None, description="Storage URL of the attached source file.")
    instagram_post_type: Optional[str] = Field(
        None, description="Instagram post type: feed, story, or reel."
    )
    instagram_cover_image_url: Optional[str] = Field(
        None, description="Cover image URL for Instagram stories/reels."
    )
    aspect_ratios: Optional[List[ImageAspectRatio]] = Field(
        default_factory=list,
        description="Desired image aspect ratios (e.g. ['1:1', '4:5']). Empty = auto-select based on platforms.",
    )
    generate_image: bool = Field(
        default=False,
        description="Whether to generate an image alongside the content. If false, image generation is skipped entirely.",
    )


class JobResponse(IDMixin, TimestampMixin):
    type: JobType
    title: str
    topic: str
    tone: Optional[str]
    audience: Optional[str]
    keywords: List[str]
    image_description: Optional[str]
    platforms: List[Platform]
    status: JobStatus
    progress: int = Field(ge=0, le=100)
    current_step: Optional[str] = None
    error: Optional[str] = None
    company_id: UUID
    user_id: Optional[UUID] = None
    source_file_name: Optional[str] = None
    source_file_url: Optional[str] = None
    source_context_text: Optional[str] = None
    instagram_post_type: Optional[str] = None
    instagram_cover_image_url: Optional[str] = None
    aspect_ratios: Optional[List[ImageAspectRatio]] = None
    generate_image: bool = False

    class Config:
        from_attributes = True


class JobListResponse(BaseModel):
    jobs: List[JobResponse]
    total: int
    page: int
    page_size: int


# ==========================================
# Content Schemas (Generated Text + Image)
# ==========================================

class PlatformContent(BaseModel):
    platform: Platform
    text: str
    hashtags: List[str] = Field(default_factory=list)
    character_count: int


class ImageVariant(BaseModel):
    id: UUID
    url: str
    aspect_ratio: ImageAspectRatio
    width: int
    height: int
    is_primary: bool = False
    prompt_used: str
    reference_image_ids: List[UUID] = Field(default_factory=list)


class ContentResponse(IDMixin, TimestampMixin):
    job_id: UUID
    type: ContentType
    title: str
    long_text: str  # For blog / LinkedIn
    platform_contents: List[PlatformContent]
    image_variants: List[ImageVariant]
    primary_image_id: Optional[UUID] = None
    safety_check_passed: bool
    safety_flags: List[str] = Field(default_factory=list)

    class Config:
        from_attributes = True


class SourceFileUploadResponse(BaseModel):
    """Response returned after uploading a source document for a job."""
    file_id: UUID
    file_name: str
    file_url: str
    size_bytes: int
    extracted_text_preview: Optional[str] = None  # first ~500 chars for UI preview
    context_stored: bool  # whether the full text was saved to the job

    class Config:
        from_attributes = True


# ==========================================
# Review Schemas (Approve / Regenerate)
# ==========================================

class RegenerateRequest(BaseModel):
    feedback: str = Field(..., min_length=1, max_length=1000)
    regenerate_text: bool = True
    regenerate_image: bool = True
    reference_image_ids: List[UUID] = Field(default_factory=list)


class ApproveRequest(BaseModel):
    selected_image_id: Optional[UUID] = None
    edited_text: Optional[Dict[Platform, str]] = None  # Platform -> edited text
    schedule_at: Optional[datetime] = None  # If None, publish now
    channel_ids: Optional[List[UUID]] = None  # If provided, publish only to these channels
    auto_publish: bool = True  # If True, enqueue publishing after approval


class ReviewResponse(BaseModel):
    job_id: UUID
    content: ContentResponse
    can_regenerate: bool
    regeneration_count: int
    max_regenerations: int


# ==========================================
# Password Reset Schemas
# ==========================================


class ForgotPasswordRequest(BaseModel):
    email: str


class ForgotPasswordResponse(BaseModel):
    message: str


class ResetPasswordRequest(BaseModel):
    code: str
    new_password: str


class ResetPasswordResponse(BaseModel):
    message: str


# ==========================================
# Publish Schemas
# ==========================================

class ChannelConnection(BaseModel):
    id: UUID
    platform: Platform
    external_account_id: str
    account_name: str
    is_active: bool
    connected_at: datetime

    class Config:
        from_attributes = True


class PublishRequest(BaseModel):
    content_id: UUID
    channel_ids: List[UUID]
    schedule_at: Optional[datetime] = None


class PublishAttemptResponse(IDMixin, TimestampMixin):
    content_id: UUID
    channel_id: UUID
    platform: Platform
    status: PublishStatus
    external_post_id: Optional[str] = None
    error: Optional[str] = None
    retry_count: int = 0
    scheduled_at: Optional[datetime] = None
    published_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class BufferConnectRequest(BaseModel):
    code: str
    state: str


class BufferConnectResponse(BaseModel):
    authorization_url: str
    state: str


# ==========================================
# Image Library Schemas
# ==========================================

class ImageTag(BaseModel):
    name: str
    count: int


class LibraryImageResponse(IDMixin, TimestampMixin):
    url: HttpUrl
    thumbnail_url: Optional[HttpUrl] = None
    prompt: str
    tags: List[str]
    aspect_ratio: ImageAspectRatio
    width: int
    height: int
    is_global: bool
    company_id: UUID
    approved_at: datetime

    class Config:
        from_attributes = True


class LibrarySearchRequest(BaseModel):
    query: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    aspect_ratio: Optional[ImageAspectRatio] = None
    is_global: Optional[bool] = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class LibrarySearchResponse(BaseModel):
    images: List[LibraryImageResponse]
    total: int
    page: int
    page_size: int
    suggested_tags: List[ImageTag]


class SaveToLibraryRequest(BaseModel):
    content_id: UUID
    image_id: UUID
    tags: List[str] = Field(default_factory=list)
    is_global: bool = False


# ==========================================
# Quotas / Usage
# ==========================================

class QuotaResponse(BaseModel):
    daily_free_requests_used: int
    daily_free_requests_limit: int
    daily_spend_usd: float
    daily_spend_cap_usd: float
    regenerations_used: int
    regenerations_limit: int


# ==========================================
# Error Responses
# ==========================================

class ErrorDetail(BaseModel):
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None


class ErrorResponse(BaseModel):
    error: ErrorDetail
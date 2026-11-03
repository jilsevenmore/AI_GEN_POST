from pydantic import BaseModel, Field, HttpUrl
from typing import Optional, List, Literal, Dict, Any
from datetime import datetime
from uuid import UUID, uuid4


# ==========================================
# Base / Common
# ==========================================

class TimestampMixin(BaseModel):
    created_at: datetime
    updated_at: datetime


class IDMixin(BaseModel):
    id: UUID = Field(default_factory=uuid4)


# ==========================================
# Enums
# ==========================================

class JobType(str, Literal["blog", "post"]):
    pass


class JobStatus(str, Literal["pending", "expanding_prompt", "writing_text", "generating_image", "safety_check", "adapting", "awaiting_review", "approved", "regenerating", "publishing", "published", "failed"]):
    pass


class Platform(str, Literal["instagram", "facebook", "linkedin"]):
    pass


class ContentType(str, Literal["blog", "social_post"]):
    pass


class ImageAspectRatio(str, Literal["1:1", "4:5", "1.91:1", "9:16"]):
    pass


class PublishStatus(str, Literal["pending", "sent", "failed", "retrying"]):
    pass


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
    user_id: UUID

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
    url: HttpUrl
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


# ==========================================
# Review Schemas (Approve / Regenerate)
# ==========================================

class RegenerateRequest(BaseModel):
    feedback: str = Field(..., min_length=1, max_length=1000)
    regenerate_text: bool = True
    regenerate_image: bool = True
    reference_image_ids: List[UUID] = Field(default_factory=list)


class ApproveRequest(BaseModel):
    selected_image_id: UUID
    edited_text: Optional[Dict[Platform, str]] = None  # Platform -> edited text
    schedule_at: Optional[datetime] = None  # If None, publish now


class ReviewResponse(BaseModel):
    job_id: UUID
    content: ContentResponse
    can_regenerate: bool
    regeneration_count: int
    max_regenerations: int


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
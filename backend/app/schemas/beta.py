"""Beta program schemas."""
from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID
from enum import Enum


class BetaUserStatus(str, Enum):
    INVITED = "invited"
    ACTIVE = "active"
    INACTIVE = "inactive"
    COMPLETED = "completed"
    CHURNED = "churned"


class BetaFeedbackType(str, Enum):
    BUG = "bug"
    FEATURE_REQUEST = "feature_request"
    USABILITY = "usability"
    CONTENT_QUALITY = "content_quality"
    PERFORMANCE = "performance"
    GENERAL = "general"


class BetaFeedbackPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class OnboardingStepKey(str, Enum):
    CONNECT_CHANNELS = "connect_channels"
    FILL_BRAND_KIT = "fill_brand_kit"
    FIRST_POST = "first_post"


# Request/Response Models
class BetaUserInvite(BaseModel):
    email: EmailStr
    name: Optional[str] = None


class BetaUserActivate(BaseModel):
    pass  # No additional fields needed


class BetaUserResponse(BaseModel):
    id: UUID
    email: str
    name: Optional[str]
    status: BetaUserStatus
    invited_at: datetime
    activated_at: Optional[datetime]
    first_post_at: Optional[datetime]
    last_active_at: Optional[datetime]
    total_posts: int
    total_regenerations: int
    feedback_count: int
    nps_score: Optional[int]
    
    class Config:
        from_attributes = True


class BetaFeedbackSubmit(BaseModel):
    type: BetaFeedbackType
    title: str = Field(..., min_length=1, max_length=500)
    description: str = Field(..., min_length=1, max_length=5000)
    priority: BetaFeedbackPriority = BetaFeedbackPriority.MEDIUM
    context: Optional[Dict[str, Any]] = None


class BetaFeedbackResponse(BaseModel):
    id: UUID
    beta_user_id: UUID
    type: BetaFeedbackType
    priority: BetaFeedbackPriority
    title: str
    description: str
    context: Optional[Dict[str, Any]]
    status: str
    created_at: datetime
    
    class Config:
        from_attributes = True


class OnboardingStepResponse(BaseModel):
    id: UUID
    beta_user_id: UUID
    step_key: str
    step_name: str
    step_order: int
    completed: bool
    completed_at: Optional[datetime]
    skipped: bool
    time_spent_seconds: int
    
    class Config:
        from_attributes = True


class OnboardingProgressResponse(BaseModel):
    total_steps: int
    completed_steps: int
    progress_percent: float
    steps: List[Dict[str, Any]]


class BetaMetricsResponse(BaseModel):
    id: UUID
    date: datetime
    company_id: UUID
    total_generations: int
    approved_generations: int
    rejected_generations: int
    total_regenerations: int
    avg_time_to_first_post: float
    avg_time_to_approve: float
    avg_regenerations_per_post: float
    total_publishes: int
    successful_publishes: int
    failed_publishes: int
    total_spend_usd: float
    free_requests_used: int
    openai_fallbacks: int
    active_users: int
    new_users: int
    churned_users: int
    
    class Config:
        from_attributes = True


class BetaDashboardResponse(BaseModel):
    summary: Dict[str, Any]
    generation_metrics: Dict[str, Any]
    publish_metrics: Dict[str, Any]
    recent_feedback: List[Dict[str, Any]]
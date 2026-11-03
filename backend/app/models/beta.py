"""Beta program models."""
import uuid
from datetime import datetime, timezone
from enum import Enum as PyEnum
from typing import Optional, Dict, Any, List

from sqlalchemy import String, Text, DateTime, Integer, Boolean, ForeignKey, Enum as SQLEnum, JSON, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class BetaUserStatus(str, PyEnum):
    INVITED = "invited"
    ACTIVE = "active"
    INACTIVE = "inactive"
    COMPLETED = "completed"
    CHURNED = "churned"


class FeedbackType(str, PyEnum):
    BUG = "bug"
    FEATURE_REQUEST = "feature_request"
    USABILITY = "usability"
    CONTENT_QUALITY = "content_quality"
    PERFORMANCE = "performance"
    GENERAL = "general"


class FeedbackPriority(str, PyEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class BetaUser(Base):
    __tablename__ = "beta_users"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[BetaUserStatus] = mapped_column(
        SQLEnum(BetaUserStatus), default=BetaUserStatus.INVITED, nullable=False
    )
    invited_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    activated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    first_post_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_active_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    total_posts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_regenerations: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    feedback_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    nps_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False
    )
    
    # Relationships
    company: Mapped["Company"] = relationship(back_populates="beta_users")
    feedback: Mapped[List["BetaFeedback"]] = relationship(back_populates="beta_user", cascade="all, delete-orphan")
    onboarding_steps: Mapped[List["OnboardingStep"]] = relationship(back_populates="beta_user", cascade="all, delete-orphan")


class BetaFeedback(Base):
    __tablename__ = "beta_feedback"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    beta_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("beta_users.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[FeedbackType] = mapped_column(SQLEnum(FeedbackType), nullable=False)
    priority: Mapped[FeedbackPriority] = mapped_column(SQLEnum(FeedbackPriority), default=FeedbackPriority.MEDIUM, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    context: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="open", nullable=False)
    assigned_to: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False
    )
    
    # Relationships
    beta_user: Mapped["BetaUser"] = relationship(back_populates="feedback")


class OnboardingStep(Base):
    __tablename__ = "onboarding_steps"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    beta_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("beta_users.id", ondelete="CASCADE"), nullable=False
    )
    step_key: Mapped[str] = mapped_column(String(100), nullable=False)
    step_name: Mapped[str] = mapped_column(String(255), nullable=False)
    step_order: Mapped[int] = mapped_column(Integer, nullable=False)
    completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    skipped: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    time_spent_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False
    )
    
    # Relationships
    beta_user: Mapped["BetaUser"] = relationship(back_populates="onboarding_steps")


class BetaMetrics(Base):
    __tablename__ = "beta_metrics"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    
    total_generations: Mapped[int] = mapped_column(Integer, default=0)
    approved_generations: Mapped[int] = mapped_column(Integer, default=0)
    rejected_generations: Mapped[int] = mapped_column(Integer, default=0)
    total_regenerations: Mapped[int] = mapped_column(Integer, default=0)
    avg_time_to_first_post: Mapped[float] = mapped_column(default=0.0)
    avg_time_to_approve: Mapped[float] = mapped_column(default=0.0)
    avg_regenerations_per_post: Mapped[float] = mapped_column(default=0.0)
    total_publishes: Mapped[int] = mapped_column(Integer, default=0)
    successful_publishes: Mapped[int] = mapped_column(Integer, default=0)
    failed_publishes: Mapped[int] = mapped_column(Integer, default=0)
    total_spend_usd: Mapped[float] = mapped_column(default=0.0)
    free_requests_used: Mapped[int] = mapped_column(Integer, default=0)
    openai_fallbacks: Mapped[int] = mapped_column(Integer, default=0)
    active_users: Mapped[int] = mapped_column(Integer, default=0)
    new_users: Mapped[int] = mapped_column(Integer, default=0)
    churned_users: Mapped[int] = mapped_column(Integer, default=0)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False
    )
    
    __table_args__ = (
        UniqueConstraint('company_id', 'date', name='uq_beta_metrics_company_date'),
    )
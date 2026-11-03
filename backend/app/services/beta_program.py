"""Beta program management and user feedback collection."""
import logging
import uuid
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from enum import Enum

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import UUID

from app.db.session import Base
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Text, DateTime, Integer, Boolean, ForeignKey, Enum as SQLEnum, JSON

logger = logging.getLogger(__name__)


class BetaUserStatus(str, Enum):
    INVITED = "invited"
    ACTIVE = "active"
    INACTIVE = "inactive"
    COMPLETED = "completed"
    CHURNED = "churned"


class FeedbackType(str, Enum):
    BUG = "bug"
    FEATURE_REQUEST = "feature_request"
    USABILITY = "usability"
    CONTENT_QUALITY = "content_quality"
    PERFORMANCE = "performance"
    GENERAL = "general"


class FeedbackPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# Database Models
class BetaUser(Base):
    __tablename__ = "beta_users"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=True)
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[BetaUserStatus] = mapped_column(
        SQLEnum(BetaUserStatus), default=BetaUserStatus.INVITED, nullable=False
    )
    invited_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    activated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    first_post_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    last_active_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    total_posts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_regenerations: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    feedback_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    nps_score: Mapped[int] = mapped_column(Integer, nullable=True)  # 0-10
    notes: Mapped[str] = mapped_column(Text, nullable=True)
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
    context: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=True)  # job_id, page, etc.
    status: Mapped[str] = mapped_column(String(50), default="open", nullable=False)  # open, in_progress, resolved, wont_fix
    assigned_to: Mapped[str] = mapped_column(String(255), nullable=True)
    resolved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
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
    step_key: Mapped[str] = mapped_column(String(100), nullable=False)  # connect_channels, fill_brand_kit, first_post, etc.
    step_name: Mapped[str] = mapped_column(String(255), nullable=False)
    step_order: Mapped[int] = mapped_column(Integer, nullable=False)
    completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
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
    
    # Generation metrics
    total_generations: Mapped[int] = mapped_column(Integer, default=0)
    approved_generations: Mapped[int] = mapped_column(Integer, default=0)
    rejected_generations: Mapped[int] = mapped_column(Integer, default=0)
    total_regenerations: Mapped[int] = mapped_column(Integer, default=0)
    
    # Timing metrics (seconds)
    avg_time_to_first_post: Mapped[float] = mapped_column(default=0.0)
    avg_time_to_approve: Mapped[float] = mapped_column(default=0.0)
    avg_regenerations_per_post: Mapped[float] = mapped_column(default=0.0)
    
    # Publish metrics
    total_publishes: Mapped[int] = mapped_column(Integer, default=0)
    successful_publishes: Mapped[int] = mapped_column(Integer, default=0)
    failed_publishes: Mapped[int] = mapped_column(Integer, default=0)
    
    # Cost metrics
    total_spend_usd: Mapped[float] = mapped_column(default=0.0)
    free_requests_used: Mapped[int] = mapped_column(Integer, default=0)
    openai_fallbacks: Mapped[int] = mapped_column(Integer, default=0)
    
    # User engagement
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
        # Unique constraint per company per day
        db.UniqueConstraint('company_id', 'date', name='uq_beta_metrics_company_date'),
    )


# Service Classes
class BetaProgramService:
    """Service for managing beta program."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def invite_user(
        self, 
        email: str, 
        company_id: uuid.UUID,
        name: str = None
    ) -> BetaUser:
        """Invite a user to the beta program."""
        # Check if already invited
        existing = await self.db.execute(
            select(BetaUser).where(
                BetaUser.email == email,
                BetaUser.company_id == company_id
            )
        )
        if existing.scalar_one_or_none():
            raise ValueError("User already invited")
        
        beta_user = BetaUser(
            email=email,
            name=name,
            company_id=company_id,
            status=BetaUserStatus.INVITED,
        )
        self.db.add(beta_user)
        
        # Create onboarding steps
        onboarding_steps = [
            OnboardingStep(
                beta_user_id=beta_user.id,
                step_key="connect_channels",
                step_name="Connect Social Channels",
                step_order=1,
            ),
            OnboardingStep(
                beta_user_id=beta_user.id,
                step_key="fill_brand_kit",
                step_name="Fill Brand Kit",
                step_order=2,
            ),
            OnboardingStep(
                beta_user_id=beta_user.id,
                step_key="first_post",
                step_name="Create First Post",
                step_order=3,
            ),
        ]
        for step in onboarding_steps:
            self.db.add(step)
        
        await self.db.commit()
        await self.db.refresh(beta_user)
        
        # TODO: Send invitation email
        logger.info(f"Invited {email} to beta program")
        
        return beta_user
    
    async def activate_user(self, beta_user_id: uuid.UUID) -> BetaUser:
        """Mark beta user as active."""
        result = await self.db.execute(
            select(BetaUser).where(BetaUser.id == beta_user_id)
        )
        beta_user = result.scalar_one_or_none()
        
        if not beta_user:
            raise ValueError("Beta user not found")
        
        beta_user.status = BetaUserStatus.ACTIVE
        beta_user.activated_at = datetime.now(timezone.utc)
        beta_user.last_active_at = datetime.now(timezone.utc)
        
        await self.db.commit()
        await self.db.refresh(beta_user)
        
        return beta_user
    
    async def record_first_post(self, beta_user_id: uuid.UUID) -> BetaUser:
        """Record user's first post."""
        result = await self.db.execute(
            select(BetaUser).where(BetaUser.id == beta_user_id)
        )
        beta_user = result.scalar_one_or_none()
        
        if not beta_user:
            raise ValueError("Beta user not found")
        
        if not beta_user.first_post_at:
            beta_user.first_post_at = datetime.now(timezone.utc)
        
        beta_user.total_posts += 1
        beta_user.last_active_at = datetime.now(timezone.utc)
        
        await self.db.commit()
        await self.db.refresh(beta_user)
        
        return beta_user
    
    async def record_regeneration(self, beta_user_id: uuid.UUID) -> BetaUser:
        """Record a regeneration."""
        result = await self.db.execute(
            select(BetaUser).where(BetaUser.id == beta_user_id)
        )
        beta_user = result.scalar_one_or_none()
        
        if not beta_user:
            raise ValueError("Beta user not found")
        
        beta_user.total_regenerations += 1
        
        await self.db.commit()
        await self.db.refresh(beta_user)
        
        return beta_user
    
    async def complete_onboarding_step(
        self, 
        beta_user_id: uuid.UUID, 
        step_key: str,
        time_spent_seconds: int = 0
    ) -> OnboardingStep:
        """Mark an onboarding step as complete."""
        result = await self.db.execute(
            select(OnboardingStep).where(
                OnboardingStep.beta_user_id == beta_user_id,
                OnboardingStep.step_key == step_key
            )
        )
        step = result.scalar_one_or_none()
        
        if not step:
            raise ValueError(f"Onboarding step {step_key} not found")
        
        step.completed = True
        step.completed_at = datetime.now(timezone.utc)
        step.time_spent_seconds += time_spent_seconds
        
        # Update beta user last active
        beta_result = await self.db.execute(
            select(BetaUser).where(BetaUser.id == beta_user_id)
        )
        beta_user = beta_result.scalar_one_or_none()
        if beta_user:
            beta_user.last_active_at = datetime.now(timezone.utc)
        
        await self.db.commit()
        await self.db.refresh(step)
        
        return step
    
    async def get_onboarding_progress(self, beta_user_id: uuid.UUID) -> Dict[str, Any]:
        """Get onboarding progress for a beta user."""
        result = await self.db.execute(
            select(OnboardingStep).where(OnboardingStep.beta_user_id == beta_user_id)
        )
        steps = result.scalars().all()
        
        total = len(steps)
        completed = sum(1 for s in steps if s.completed)
        
        return {
            "total_steps": total,
            "completed_steps": completed,
            "progress_percent": (completed / total * 100) if total > 0 else 0,
            "steps": [
                {
                    "step_key": s.step_key,
                    "step_name": s.step_name,
                    "step_order": s.step_order,
                    "completed": s.completed,
                    "completed_at": s.completed_at,
                    "time_spent_seconds": s.time_spent_seconds,
                }
                for s in sorted(steps, key=lambda x: x.step_order)
            ],
        }
    
    async def submit_feedback(
        self,
        beta_user_id: uuid.UUID,
        type: FeedbackType,
        title: str,
        description: str,
        priority: FeedbackPriority = FeedbackPriority.MEDIUM,
        context: Dict[str, Any] = None,
    ) -> BetaFeedback:
        """Submit feedback from a beta user."""
        # Update beta user feedback count
        beta_result = await self.db.execute(
            select(BetaUser).where(BetaUser.id == beta_user_id)
        )
        beta_user = beta_result.scalar_one_or_none()
        
        if beta_user:
            beta_user.feedback_count += 1
            beta_user.last_active_at = datetime.now(timezone.utc)
        
        feedback = BetaFeedback(
            beta_user_id=beta_user_id,
            type=type,
            priority=priority,
            title=title,
            description=description,
            context=context or {},
        )
        self.db.add(feedback)
        
        await self.db.commit()
        await self.db.refresh(feedback)
        
        return feedback
    
    async def get_beta_users(
        self, 
        company_id: uuid.UUID,
        status: BetaUserStatus = None
    ) -> List[BetaUser]:
        """Get beta users for a company."""
        query = select(BetaUser).where(BetaUser.company_id == company_id)
        
        if status:
            query = query.where(BetaUser.status == status)
        
        query = query.order_by(BetaUser.invited_at.desc())
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def get_beta_metrics(self, company_id: uuid.UUID, days: int = 30) -> List[BetaMetrics]:
        """Get beta metrics for a company."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        result = await self.db.execute(
            select(BetaMetrics).where(
                BetaMetrics.company_id == company_id,
                BetaMetrics.date >= cutoff
            ).order_by(BetaMetrics.date.desc())
        )
        return list(result.scalars().all())
    
    async def compute_daily_metrics(self, company_id: uuid.UUID, date: datetime) -> BetaMetrics:
        """Compute daily metrics for a company."""
        # This would aggregate from various tables
        # For now, return empty metrics
        metrics = BetaMetrics(
            date=date,
            company_id=company_id,
        )
        self.db.add(metrics)
        await self.db.commit()
        await self.db.refresh(metrics)
        return metrics


class BetaMetricsAggregator:
    """Aggregates beta metrics from various sources."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def aggregate_daily(self, company_id: uuid.UUID, date: datetime) -> BetaMetrics:
        """Aggregate metrics for a specific day."""
        start = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        
        # Get beta users
        beta_users_result = await self.db.execute(
            select(BetaUser).where(
                BetaUser.company_id == company_id,
                BetaUser.invited_at < end,
            )
        )
        beta_users = beta_users_result.scalars().all()
        
        # Compute metrics
        metrics = BetaMetrics(
            date=start,
            company_id=company_id,
            active_users=sum(1 for u in beta_users if u.status == BetaUserStatus.ACTIVE and u.last_active_at and u.last_active_at >= start),
            new_users=sum(1 for u in beta_users if u.invited_at >= start),
            churned_users=sum(1 for u in beta_users if u.status == BetaUserStatus.CHURNED),
        )
        
        # Aggregate from jobs, contents, publish_attempts
        # This would join with those tables
        # For now, return basic metrics
        
        self.db.add(metrics)
        await self.db.commit()
        await self.db.refresh(metrics)
        
        return metrics


# Import db at module level for UniqueConstraint
from sqlalchemy import db
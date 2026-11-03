"""Beta program API endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List, Optional, Dict, Any
from uuid import UUID, uuid4
from datetime import datetime, timezone, timedelta

from app.db.session import get_db
from app.core.dependencies import get_current_user, get_current_company
from app.models.user import User
from app.models.company import Company
from app.models.beta_user import BetaUser, BetaUserStatus, BetaFeedback, BetaFeedbackType, BetaFeedbackPriority, OnboardingStep
from app.models.job import Job
from app.models.content import Content
from app.models.publish import PublishAttempt
from app.schemas.beta import (
    BetaUserResponse, BetaUserInvite, BetaUserActivate,
    BetaFeedbackSubmit, BetaFeedbackResponse,
    OnboardingStepResponse, OnboardingProgressResponse,
    BetaMetricsResponse, BetaDashboardResponse,
)
from app.services.beta_program import BetaProgramService, BetaMetricsAggregator

router = APIRouter()


@router.post("/invite", response_model=BetaUserResponse, status_code=status.HTTP_201_CREATED)
async def invite_beta_user(
    invite: BetaUserInvite,
    current_company = Depends(get_current_company),
    db: AsyncSession = Depends(get_db),
):
    """Invite a user to the beta program."""
    service = BetaProgramService(db)
    
    try:
        beta_user = await service.invite_user(
            email=invite.email,
            company_id=current_company.id,
            name=invite.name,
        )
        return BetaUserResponse.model_validate(beta_user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/users", response_model=List[BetaUserResponse])
async def list_beta_users(
    status: Optional[BetaUserStatus] = Query(None),
    current_company = Depends(get_current_company),
    db: AsyncSession = Depends(get_db),
):
    """List beta users for the current company."""
    service = BetaProgramService(db)
    users = await service.get_beta_users(current_company.id, status)
    return [BetaUserResponse.model_validate(u) for u in users]


@router.get("/users/{user_id}", response_model=BetaUserResponse)
async def get_beta_user(
    user_id: UUID,
    current_company = Depends(get_current_company),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific beta user."""
    result = await db.execute(
        select(BetaUser).where(
            BetaUser.id == user_id,
            BetaUser.company_id == current_company.id
        )
    )
    beta_user = result.scalar_one_or_none()
    
    if not beta_user:
        raise HTTPException(status_code=404, detail="Beta user not found")
    
    return BetaUserResponse.model_validate(beta_user)


@router.post("/users/{user_id}/activate", response_model=BetaUserResponse)
async def activate_beta_user(
    user_id: UUID,
    current_company = Depends(get_current_company),
    db: AsyncSession = Depends(get_db),
):
    """Activate a beta user (mark as active)."""
    service = BetaProgramService(db)
    
    try:
        beta_user = await service.activate_user(user_id)
        return BetaUserResponse.model_validate(beta_user)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/users/{user_id}/onboarding", response_model=OnboardingProgressResponse)
async def get_onboarding_progress(
    user_id: UUID,
    current_company = Depends(get_current_company),
    db: AsyncSession = Depends(get_db),
):
    """Get onboarding progress for a beta user."""
    service = BetaProgramService(db)
    progress = await service.get_onboarding_progress(user_id)
    return OnboardingProgressResponse(**progress)


@router.post("/users/{user_id}/onboarding/{step_key}/complete", response_model=OnboardingStepResponse)
async def complete_onboarding_step(
    user_id: UUID,
    step_key: str,
    time_spent_seconds: int = 0,
    current_company = Depends(get_current_company),
    db: AsyncSession = Depends(get_db),
):
    """Mark an onboarding step as complete."""
    service = BetaProgramService(db)
    
    try:
        step = await service.complete_onboarding_step(user_id, step_key, time_spent_seconds)
        return OnboardingStepResponse.model_validate(step)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/users/{user_id}/feedback", response_model=BetaFeedbackResponse, status_code=status.HTTP_201_CREATED)
async def submit_feedback(
    user_id: UUID,
    feedback: BetaFeedbackSubmit,
    current_company = Depends(get_current_company),
    db: AsyncSession = Depends(get_db),
):
    """Submit feedback from a beta user."""
    service = BetaProgramService(db)
    
    try:
        feedback_obj = await service.submit_feedback(
            beta_user_id=user_id,
            type=feedback.type,
            title=feedback.title,
            description=feedback.description,
            priority=feedback.priority,
            context=feedback.context,
        )
        return BetaFeedbackResponse.model_validate(feedback_obj)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/users/{user_id}/feedback", response_model=List[BetaFeedbackResponse])
async def get_user_feedback(
    user_id: UUID,
    current_company = Depends(get_current_company),
    db: AsyncSession = Depends(get_db),
):
    """Get feedback submitted by a beta user."""
    result = await db.execute(
        select(BetaFeedback)
        .where(BetaFeedback.beta_user_id == user_id)
        .order_by(BetaFeedback.created_at.desc())
    )
    feedback_list = result.scalars().all()
    return [BetaFeedbackResponse.model_validate(f) for f in feedback_list]


@router.get("/metrics", response_model=List[BetaMetricsResponse])
async def get_beta_metrics(
    days: int = Query(30, ge=1, le=365),
    current_company = Depends(get_current_company),
    db: AsyncSession = Depends(get_db),
):
    """Get beta metrics for the current company."""
    service = BetaProgramService(db)
    metrics = await service.get_beta_metrics(current_company.id, days)
    return [BetaMetricsResponse.model_validate(m) for m in metrics]


@router.get("/dashboard", response_model=BetaDashboardResponse)
async def get_beta_dashboard(
    current_company = Depends(get_current_company),
    db: AsyncSession = Depends(get_db),
):
    """Get beta program dashboard data."""
    service = BetaProgramService(db)
    aggregator = BetaMetricsAggregator(db)
    
    # Get all beta users
    users = await service.get_beta_users(current_company.id)
    
    # Get recent metrics
    recent_metrics = await service.get_beta_metrics(current_company.id, 30)
    
    # Compute summary stats
    total_invited = len(users)
    active_users = sum(1 for u in users if u.status == BetaUserStatus.ACTIVE)
    completed_onboarding = sum(1 for u in users if u.first_post_at is not None)
    
    # Recent feedback
    feedback_result = await db.execute(
        select(BetaFeedback)
        .join(BetaUser, BetaFeedback.beta_user_id == BetaUser.id)
        .where(BetaUser.company_id == current_company.id)
        .order_by(BetaFeedback.created_at.desc())
        .limit(10)
    )
    recent_feedback = feedback_result.scalars().all()
    
    # Compute metrics from last 7 days
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    recent_jobs = await db.execute(
        select(Job).where(
            Job.company_id == current_company.id,
            Job.created_at >= week_ago
        )
    )
    jobs = recent_jobs.scalars().all()
    
    total_generations = len(jobs)
    approved = sum(1 for j in jobs if j.status == "approved" or j.status == "published")
    regenerated = sum(getattr(j, 'regeneration_count', 0) for j in jobs)
    
    # Publish stats
    publish_result = await db.execute(
        select(PublishAttempt).where(
            PublishAttempt.created_at >= week_ago
        ).join(Content, PublishAttempt.content_id == Content.id)
        .where(Content.company_id == current_company.id)
    )
    publishes = publish_result.scalars().all()
    successful_publishes = sum(1 for p in publishes if p.status == "sent")
    failed_publishes = sum(1 for p in publishes if p.status == "failed")
    
    return BetaDashboardResponse(
        summary={
            "total_invited": total_invited,
            "active_users": active_users,
            "activation_rate": (active_users / total_invited * 100) if total_invited > 0 else 0,
            "completed_onboarding": completed_onboarding,
            "onboarding_completion_rate": (completed_onboarding / active_users * 100) if active_users > 0 else 0,
        },
        generation_metrics={
            "total_generations": total_generations,
            "approved_generations": approved,
            "approval_rate": (approved / total_generations * 100) if total_generations > 0 else 0,
            "total_regenerations": regenerated,
            "avg_regenerations_per_post": (regenerated / total_generations) if total_generations > 0 else 0,
        },
        publish_metrics={
            "total_publishes": len(publishes),
            "successful_publishes": successful_publishes,
            "failed_publishes": failed_publishes,
            "publish_success_rate": (successful_publishes / len(publishes) * 100) if publishes else 0,
        },
        recent_feedback=[{
            "id": f.id,
            "type": f.type.value,
            "priority": f.priority.value,
            "title": f.title,
            "created_at": f.created_at,
        } for f in recent_feedback],
    )


# Import datetime at module level
from datetime import datetime
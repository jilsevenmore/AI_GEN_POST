from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from uuid import UUID
from datetime import datetime, timezone
from app.db.session import get_db
from app.schemas.common import (
    RegenerateRequest, ApproveRequest, ReviewResponse,
    ContentResponse, ContentType, PlatformContent, Platform,
    ImageVariant, ImageAspectRatio, JobStatus
)
from app.core.dependencies import get_current_company
from app.models.job import Job
from app.models.content import Content

router = APIRouter()


@router.get("/{job_id}", response_model=ReviewResponse)
async def get_review(
    job_id: UUID,
    current_company = Depends(get_current_company),
    db: AsyncSession = Depends(get_db),
):
    """Get generated content for review (approve/regenerate)."""
    # Get job with company scoping
    job_result = await db.execute(
        select(Job).where(Job.id == job_id, Job.company_id == current_company.id)
    )
    job = job_result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Get content
    content_result = await db.execute(
        select(Content).where(Content.job_id == job_id)
    )
    content = content_result.scalar_one_or_none()
    
    if not content:
        raise HTTPException(status_code=404, detail="Content not found for this job")
    
    # Count regenerations (based on content updates)
    regen_count = 0  # TODO: Track properly in Phase 3
    
    return ReviewResponse(
        job_id=job_id,
        content=ContentResponse.model_validate(content),
        can_regenerate=job.status in [JobStatus.awaiting_review, JobStatus.regenerating],
        regeneration_count=regen_count,
        max_regenerations=3,
    )


@router.post("/{job_id}/regenerate", response_model=ReviewResponse)
async def regenerate_content(
    job_id: UUID,
    request: RegenerateRequest,
    current_company = Depends(get_current_company),
    db: AsyncSession = Depends(get_db),
):
    """Regenerate content with user feedback."""
    # Get job with company scoping
    job_result = await db.execute(
        select(Job).where(Job.id == job_id, Job.company_id == current_company.id)
    )
    job = job_result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Update job status
    job.status = JobStatus.regenerating
    job.current_step = "Regenerating with feedback..."
    job.updated_at = datetime.now(timezone.utc)
    await db.commit()
    
    # TODO: Implement real regeneration with LangGraph (Phase 3)
    # For now, return existing content
    content_result = await db.execute(
        select(Content).where(Content.job_id == job_id)
    )
    content = content_result.scalar_one_or_none()
    
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")
    
    # Reset job status for review
    job.status = JobStatus.awaiting_review
    job.current_step = "Ready for review"
    job.updated_at = datetime.now(timezone.utc)
    await db.commit()
    
    return ReviewResponse(
        job_id=job_id,
        content=ContentResponse.model_validate(content),
        can_regenerate=True,
        regeneration_count=1,
        max_regenerations=3,
    )


@router.post("/{job_id}/approve", response_model=ContentResponse)
async def approve_content(
    job_id: UUID,
    request: ApproveRequest,
    current_company = Depends(get_current_company),
    db: AsyncSession = Depends(get_db),
):
    """Approve content and move to publishing."""
    # Get job with company scoping
    job_result = await db.execute(
        select(Job).where(Job.id == job_id, Job.company_id == current_company.id)
    )
    job = job_result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Get content
    content_result = await db.execute(
        select(Content).where(Content.job_id == job_id)
    )
    content = content_result.scalar_one_or_none()
    
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")
    
    # Apply text edits if provided
    if request.edited_text:
        platform_contents = content.platform_contents
        for pc in platform_contents:
            platform_key = pc.get("platform")
            if platform_key in request.edited_text:
                pc["text"] = request.edited_text[platform_key]
        content.platform_contents = platform_contents
    
    # Set selected image as primary
    content.primary_image_id = request.selected_image_id
    content.updated_at = datetime.now(timezone.utc)
    
    # Update job status
    job.status = JobStatus.approved
    job.current_step = "Approved, ready for publishing"
    job.updated_at = datetime.now(timezone.utc)
    
    await db.commit()
    await db.refresh(content)
    
    # TODO: Trigger publishing flow (Phase 6)
    
    return ContentResponse.model_validate(content)
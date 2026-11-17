from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from uuid import UUID, uuid4
from datetime import datetime, timezone
import logging

from app.db.session import get_db
from app.schemas.common import (
    RegenerateRequest, ApproveRequest, ReviewResponse,
    ContentResponse, ContentType, PlatformContent, Platform,
    ImageVariant, ImageAspectRatio, JobStatus, PublishStatus
)
from app.core.dependencies import get_current_company
from app.models.job import Job
from app.models.content import Content
from app.models.channel import ChannelConnection as ChannelConnectionModel
from app.models.publish import PublishAttempt
from app.services.ai.graph import resume_after_review
from app.services.cloudinary_service import upload_image_to_cloudinary
from app.services.publisher import get_publisher
from app.services.publish_queue import get_publishing_queue

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/{job_id}", response_model=ReviewResponse)
async def get_review(
    job_id: UUID,
    current_company = Depends(get_current_company),
    db: AsyncSession = Depends(get_db),
):
    """Get generated content for review (approve/regenerate)."""
    job_result = await db.execute(
        select(Job).where(Job.id == job_id, Job.company_id == current_company.id)
    )
    job = job_result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    content_result = await db.execute(
        select(Content).where(Content.job_id == job_id)
    )
    content = content_result.scalar_one_or_none()
    
    if not content:
        raise HTTPException(status_code=404, detail="Content not found for this job")
    
    # Count regenerations from job metadata
    regen_count = getattr(job, 'regeneration_count', 0)
    
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
    """Regenerate content with user feedback using AI graph."""
    job_result = await db.execute(
        select(Job).where(Job.id == job_id, Job.company_id == current_company.id)
    )
    job = job_result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job.status not in [JobStatus.awaiting_review, JobStatus.regenerating]:
        raise HTTPException(status_code=400, detail="Job not in a state that allows regeneration")
    
    # Check regeneration limit
    regen_count = getattr(job, 'regeneration_count', 0)
    if regen_count >= 3:
        raise HTTPException(status_code=400, detail="Maximum regenerations reached")
    
    # Update job status
    job.status = JobStatus.regenerating
    job.current_step = "Regenerating with feedback..."
    job.updated_at = datetime.now(timezone.utc)
    await db.commit()
    
    # Run regeneration via AI graph
    try:
        final_state = await resume_after_review(
            job_id=str(job_id),
            feedback=request.feedback,
            regenerate_text=request.regenerate_text,
            regenerate_image=request.regenerate_image,
            new_reference_ids=request.reference_image_ids,
            db=db,
        )
        
        # Get updated content
        content_result = await db.execute(
            select(Content).where(Content.job_id == job_id)
        )
        content = content_result.scalar_one_or_none()
        
        if not content:
            raise HTTPException(status_code=404, detail="Content not found after regeneration")
        
        # Update regeneration count
        job.regeneration_count = regen_count + 1
        job.status = JobStatus.awaiting_review
        job.current_step = "Ready for review"
        job.updated_at = datetime.now(timezone.utc)
        await db.commit()
        
        return ReviewResponse(
            job_id=job_id,
            content=ContentResponse.model_validate(content),
            can_regenerate=job.regeneration_count < 3,
            regeneration_count=job.regeneration_count,
            max_regenerations=3,
        )
        
    except Exception as e:
        job.status = JobStatus.failed
        job.error = f"Regeneration failed: {str(e)}"
        job.updated_at = datetime.now(timezone.utc)
        await db.commit()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{job_id}/approve", response_model=ContentResponse)
async def approve_content(
    job_id: UUID,
    request: ApproveRequest,
    current_company = Depends(get_current_company),
    db: AsyncSession = Depends(get_db),
):
    """Approve content and optionally enqueue publishing automatically."""
    job_result = await db.execute(
        select(Job).where(Job.id == job_id, Job.company_id == current_company.id)
    )
    job = job_result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    content_result = await db.execute(
        select(Content).where(Content.job_id == job_id)
    )
    content = content_result.scalar_one_or_none()

    if not content:
        raise HTTPException(status_code=404, detail="Content not found")

    # Apply text edits if provided
    if request.edited_text:
        platform_contents = list(content.platform_contents or [])
        for pc in platform_contents:
            platform_key = pc.get("platform")
            if platform_key in request.edited_text:
                pc["text"] = request.edited_text[platform_key]
        content.platform_contents = platform_contents

    # Upload selected image to Cloudinary for public Buffer publishing
    selected_variant = None
    image_variants = list(content.image_variants or [])
    for variant in image_variants:
        if str(variant.get("id")) == str(request.selected_image_id):
            selected_variant = variant
            break

    if not selected_variant:
        raise HTTPException(status_code=400, detail="Selected image not found in content variants")

    source_url = selected_variant.get("url")
    if not source_url:
        raise HTTPException(status_code=400, detail="Selected image has no URL")

    try:
        public_url = await upload_image_to_cloudinary(
            source_url,
            folder="published",
            public_id=f"job_{job_id}_{request.selected_image_id}",
            tags=[str(content.company_id), str(job_id), content.type],
        )
        selected_variant["url"] = public_url
        selected_variant["cloudinary_url"] = public_url
        selected_variant["is_primary"] = True
        for variant in image_variants:
            if str(variant.get("id")) != str(request.selected_image_id):
                variant["is_primary"] = False
        content.image_variants = image_variants
    except Exception as e:
        logger.exception("Cloudinary upload on approve failed for job %s: %s", job_id, e)
        raise HTTPException(status_code=502, detail=f"Failed to upload approved image to Cloudinary: {str(e)}")

    # Set selected image as primary
    content.primary_image_id = request.selected_image_id
    content.updated_at = datetime.now(timezone.utc)

    # Resolve channels for auto-publishing
    channels_to_publish = []
    if request.auto_publish:
        if request.channel_ids:
            channels_result = await db.execute(
                select(ChannelConnectionModel).where(
                    ChannelConnectionModel.id.in_(request.channel_ids),
                    ChannelConnectionModel.company_id == current_company.id,
                    ChannelConnectionModel.is_active == True,
                )
            )
            channels_to_publish = list(channels_result.scalars().all())
            if len(channels_to_publish) != len(request.channel_ids):
                raise HTTPException(status_code=404, detail="One or more selected channels not found or inactive")
        else:
            channels_result = await db.execute(
                select(ChannelConnectionModel).where(
                    ChannelConnectionModel.company_id == current_company.id,
                    ChannelConnectionModel.is_active == True,
                )
            )
            channels_to_publish = list(channels_result.scalars().all())

    # Update job status
    if channels_to_publish:
        job.status = JobStatus.publishing
        job.current_step = "Approved, queued for publishing"
    else:
        job.status = JobStatus.approved
        if request.auto_publish:
            job.current_step = "Approved (no active channels connected for auto-publish)"
        else:
            job.current_step = "Approved, ready for publishing"
    job.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(content)

    # Enqueue publish attempts after approval is saved
    if channels_to_publish:
        publisher = get_publisher()
        queue = get_publishing_queue()
        for channel in channels_to_publish:
            idempotency_key = f"publish_{content.id}_{channel.id}_{uuid4().hex[:8]}"
            text = publisher._get_platform_text(content, channel.platform)
            text = publisher._truncate_text(text, channel.platform)
            image_url = publisher._select_best_image(content, channel.platform)

            attempt = PublishAttempt(
                content_id=content.id,
                channel_id=channel.id,
                platform=channel.platform,
                status=PublishStatus.pending,
                scheduled_at=request.schedule_at,
                idempotency_key=idempotency_key,
            )
            db.add(attempt)
            await db.flush()

            try:
                await queue.enqueue(attempt, channel, content, text, image_url)
            except RuntimeError:
                await db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Publishing queue is unavailable (Redis is not running). Content was approved but not published.",
                )

        await db.commit()
        queue.start_worker_task()

    return ContentResponse.model_validate(content)
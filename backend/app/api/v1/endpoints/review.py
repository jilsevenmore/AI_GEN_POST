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
    
    if job.status not in [JobStatus.awaiting_review, JobStatus.regenerating, JobStatus.failed]:
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
        if final_state is None:
            raise RuntimeError("Generation failed during regeneration")
        
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
    logger.info(
        "Approve requested job_id=%s company_id=%s auto_publish=%s selected_image_id=%s schedule_at=%s requested_channel_ids=%s",
        job_id,
        current_company.id,
        request.auto_publish,
        request.selected_image_id,
        request.schedule_at,
        [str(c) for c in (request.channel_ids or [])],
    )
    job_result = await db.execute(
        select(Job).where(Job.id == job_id, Job.company_id == current_company.id)
    )
    job = job_result.scalar_one_or_none()

    if not job:
        logger.warning("Approve failed: job not found job_id=%s company_id=%s", job_id, current_company.id)
        raise HTTPException(status_code=404, detail="Job not found")

    content_result = await db.execute(
        select(Content).where(Content.job_id == job_id)
    )
    content = content_result.scalar_one_or_none()

    if not content:
        logger.warning("Approve failed: content not found job_id=%s", job_id)
        raise HTTPException(status_code=404, detail="Content not found")

    # Apply text edits if provided
    if request.edited_text:
        platform_contents = list(content.platform_contents or [])
        for pc in platform_contents:
            platform_key = pc.get("platform")
            if platform_key in request.edited_text:
                pc["text"] = request.edited_text[platform_key]
        content.platform_contents = platform_contents
        logger.info("Applied edited text on approve job_id=%s platforms=%s", job_id, list(request.edited_text.keys()))

    # Upload selected image to Cloudinary for public Buffer publishing (if an image is selected)
    image_variants = list(content.image_variants or [])
    if request.selected_image_id:
        selected_variant = None
        for variant in image_variants:
            if str(variant.get("id")) == str(request.selected_image_id):
                selected_variant = variant
                break

        if not selected_variant:
            logger.warning("Approve failed: selected image missing job_id=%s selected_image_id=%s", job_id, request.selected_image_id)
            raise HTTPException(status_code=400, detail="Selected image not found in content variants")

        source_url = selected_variant.get("url")
        if not source_url:
            logger.warning("Approve failed: selected image has no URL job_id=%s selected_image_id=%s", job_id, request.selected_image_id)
            raise HTTPException(status_code=400, detail="Selected image has no URL")

        try:
            logger.info("Uploading approved image to Cloudinary job_id=%s selected_image_id=%s", job_id, request.selected_image_id)
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
            logger.info("Cloudinary upload on approve succeeded job_id=%s public_url_host=%s", job_id, public_url.split('/')[2] if '://' in public_url else 'unknown')
        except Exception as e:
            logger.exception("Cloudinary upload on approve failed for job %s: %s", job_id, e)
            raise HTTPException(status_code=502, detail=f"Failed to upload approved image to Cloudinary: {str(e)}")

        content.primary_image_id = request.selected_image_id
    else:
        content.primary_image_id = None
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
                logger.warning(
                    "Approve failed: requested channels missing/inactive job_id=%s requested=%s resolved=%s",
                    job_id,
                    [str(c) for c in request.channel_ids],
                    [str(c.id) for c in channels_to_publish],
                )
                raise HTTPException(status_code=404, detail="One or more selected channels not found or inactive")
        else:
            target_platforms = {
                str(getattr(p, "value", p)).lower()
                for p in (job.platforms or [])
            }
            if not target_platforms and content.platform_contents:
                target_platforms = {
                    str(getattr(pc.get("platform"), "value", pc.get("platform", ""))).lower()
                    for pc in content.platform_contents
                    if isinstance(pc, dict) and pc.get("platform")
                }

            channels_query = select(ChannelConnectionModel).where(
                ChannelConnectionModel.company_id == current_company.id,
                ChannelConnectionModel.is_active == True,
            )
            if target_platforms:
                channels_query = channels_query.where(
                    ChannelConnectionModel.platform.in_(sorted(target_platforms))
                )
            channels_result = await db.execute(channels_query)
            channels_to_publish = list(channels_result.scalars().all())
        logger.info(
            "Approve auto-publish channel resolution job_id=%s resolved_channels=%s",
            job_id,
            [(str(c.id), getattr(c.platform, 'value', str(c.platform)), c.account_name) for c in channels_to_publish],
        )

    # Update job status
    if channels_to_publish:
        job.status = JobStatus.publishing
        job.current_step = "Approved, queued for publishing"
    else:
        job.status = JobStatus.approved
        if request.auto_publish:
            job.current_step = "Approved (no active channels connected for auto-publish)"
            logger.warning("Approve auto-publish requested but no active channels found job_id=%s company_id=%s", job_id, current_company.id)
        else:
            job.current_step = "Approved, ready for publishing"
    job.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(content)

    # Enqueue publish attempts after approval is saved (skip channels already queued/sent)
    if channels_to_publish:
        existing_attempts_res = await db.execute(
            select(PublishAttempt.channel_id).where(
                PublishAttempt.content_id == content.id,
                PublishAttempt.channel_id.in_([c.id for c in channels_to_publish]),
                PublishAttempt.status.in_([
                    PublishStatus.pending,
                    PublishStatus.retrying,
                    PublishStatus.sent,
                ]),
            )
        )
        already_queued_channel_ids = set(existing_attempts_res.scalars().all())
        channels_to_publish = [c for c in channels_to_publish if c.id not in already_queued_channel_ids]

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
            logger.info(
                "Created publish attempt on approve attempt_id=%s job_id=%s content_id=%s channel_id=%s platform=%s scheduled=%s",
                attempt.id,
                job_id,
                content.id,
                channel.id,
                channel.platform,
                bool(request.schedule_at),
            )

            try:
                await queue.enqueue(attempt, channel, content, text, image_url)
                logger.info("Enqueued publish attempt on approve attempt_id=%s channel_id=%s", attempt.id, channel.id)
            except RuntimeError:
                logger.exception("Failed to enqueue publish attempt on approve attempt_id=%s (Redis unavailable)", attempt.id)
                await db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Publishing queue is unavailable (Redis is not running). Content was approved but not published.",
                )

        await db.commit()
        queue.start_worker_task()
        logger.info("Approve+publish enqueue complete job_id=%s attempts=%s", job_id, len(channels_to_publish))

    logger.info("Approve completed job_id=%s status=%s", job_id, job.status)
    return ContentResponse.model_validate(content)
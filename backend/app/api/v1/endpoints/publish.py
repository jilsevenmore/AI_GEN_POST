import logging
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

logger = logging.getLogger(__name__)
from typing import List, Optional
from uuid import UUID, uuid4
from datetime import datetime, timezone
from app.db.session import get_db
from app.schemas.common import (
    ChannelConnection, PublishRequest, PublishAttemptResponse,
    BufferConnectRequest, BufferConnectResponse, PublishStatus, Platform
)
from app.core.dependencies import get_current_company
from app.models.channel import ChannelConnection as ChannelConnectionModel
from app.models.publish import PublishAttempt
from app.models.content import Content
from app.models.job import Job
from app.services.publisher import (
    get_publisher,
    BufferPublisher,
    persist_refreshed_channel_tokens,
    sync_job_publish_status,
)
from app.services.publish_queue import get_publishing_queue, PublishingQueue

router = APIRouter()


async def _enqueue_publish_attempts(
    db: AsyncSession,
    content: Content,
    channels: List[ChannelConnectionModel],
    schedule_at: Optional[datetime],
    publisher: BufferPublisher,
    queue: PublishingQueue,
) -> List[PublishAttempt]:
    """Create publish attempts and enqueue them for the given channels.

    Mirrors the per-channel logic previously inlined in publish_content so it
    can be reused by the approve flow (Approve & Publish).
    """
    logger.info(
        "Creating publish attempts content_id=%s channel_count=%s schedule_at=%s",
        content.id,
        len(channels),
        schedule_at,
    )
    attempts: List[PublishAttempt] = []
    for channel in channels:
        idempotency_key = f"publish_{content.id}_{channel.id}_{uuid4().hex[:8]}"

        # Get platform-specific text and image
        text = publisher._get_platform_text(content, channel.platform)
        text = publisher._truncate_text(text, channel.platform)
        image_url = publisher._select_best_image(content, channel.platform)

        attempt = PublishAttempt(
            content_id=content.id,
            channel_id=channel.id,
            platform=channel.platform,
            status=PublishStatus.pending,
            scheduled_at=schedule_at,
            idempotency_key=idempotency_key,
        )
        db.add(attempt)
        await db.flush()  # Get attempt ID
        logger.info(
            "Prepared publish attempt attempt_id=%s content_id=%s channel_id=%s platform=%s account=%s",
            attempt.id,
            content.id,
            channel.id,
            getattr(channel.platform, "value", str(channel.platform)),
            getattr(channel, "account_name", None),
        )

        # Enqueue
        try:
            enqueued = await queue.enqueue(attempt, channel, content, text, image_url)
            if not enqueued:
                logger.warning("Skipped duplicate publish attempt attempt_id=%s channel_id=%s", attempt.id, channel.id)
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Duplicate publish attempt already queued",
                )
            logger.info("Enqueued publish attempt attempt_id=%s channel_id=%s", attempt.id, channel.id)
        except RuntimeError:
            logger.exception("Failed to enqueue publish attempt attempt_id=%s (Redis unavailable)", attempt.id)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Publishing queue is unavailable (Redis is not running)",
            )

        attempts.append(attempt)

    await db.commit()

    # Refresh to get IDs
    for attempt in attempts:
        await db.refresh(attempt)

    # Ensure queue worker is running
    queue.start_worker_task()
    logger.info("Publish attempts enqueued content_id=%s attempts=%s", content.id, [str(a.id) for a in attempts])

    return attempts


@router.get("/channels", response_model=List[ChannelConnection])
async def list_channels(
    current_company = Depends(get_current_company),
    db: AsyncSession = Depends(get_db),
):
    """List connected social channels for the current company."""
    result = await db.execute(
        select(ChannelConnectionModel)
        .where(ChannelConnectionModel.company_id == current_company.id)
        .order_by(ChannelConnectionModel.connected_at.desc())
    )
    channels = result.scalars().all()
    
    return [
        ChannelConnection.model_validate(channel) for channel in channels
    ]


@router.get("/buffer/connect", response_model=BufferConnectResponse)
async def get_buffer_auth_url(
    current_company = Depends(get_current_company),
    db: AsyncSession = Depends(get_db),
):
    """Get Buffer OAuth authorization URL."""
    publisher = get_publisher()
    state = f"buf_{uuid4().hex[:16]}"
    logger.info("Generating Buffer auth URL company_id=%s state=%s", current_company.id, state)

    # Store state in session or cache for verification
    # For now, we'll just return the URL
    authorization_url = await publisher.get_authorization_url(state)

    logger.info("Generated Buffer auth URL company_id=%s state=%s", current_company.id, state)
    return BufferConnectResponse(
        authorization_url=authorization_url,
        state=state,
    )


@router.post("/buffer/connect", response_model=List[ChannelConnection])
async def connect_buffer(
    request: BufferConnectRequest,
    current_company = Depends(get_current_company),
    db: AsyncSession = Depends(get_db),
):
    """Complete Buffer OAuth connection."""
    publisher = get_publisher()
    logger.info("Buffer connect callback received company_id=%s state_present=%s code_present=%s", current_company.id, bool(request.state), bool(request.code))

    try:
        # Exchange code for tokens
        channel_connections = await publisher.exchange_code(request.code, request.state)
        logger.info("Buffer token exchange succeeded company_id=%s channels_returned=%s", current_company.id, len(channel_connections))

        saved_channels: List[ChannelConnectionModel] = []
        for channel_connection in channel_connections:
            # Set company ID
            channel_connection.company_id = current_company.id

            # Check if a channel with same company + platform + external_account_id already exists
            existing = await db.execute(
                select(ChannelConnectionModel).where(
                    ChannelConnectionModel.company_id == current_company.id,
                    ChannelConnectionModel.platform == channel_connection.platform,
                    ChannelConnectionModel.external_account_id == channel_connection.external_account_id,
                )
            )
            existing_channel = existing.scalar_one_or_none()

            if existing_channel:
                logger.info(
                    "Updating existing Buffer channel company_id=%s channel_id=%s platform=%s account=%s",
                    current_company.id,
                    existing_channel.id,
                    existing_channel.platform,
                    channel_connection.account_name,
                )
                # Update existing channel with new tokens
                existing_channel.access_token_encrypted = channel_connection.access_token_encrypted
                existing_channel.refresh_token_encrypted = channel_connection.refresh_token_encrypted
                existing_channel.token_expires_at = channel_connection.token_expires_at
                existing_channel.account_name = channel_connection.account_name
                existing_channel.is_active = True
                existing_channel.updated_at = datetime.now(timezone.utc)
                await db.commit()
                await db.refresh(existing_channel)
                saved_channels.append(existing_channel)
            else:
                logger.info(
                    "Creating new Buffer channel company_id=%s platform=%s external_account_id=%s account=%s",
                    current_company.id,
                    channel_connection.platform,
                    channel_connection.external_account_id,
                    channel_connection.account_name,
                )
                # Insert new channel
                db.add(channel_connection)
                await db.commit()
                await db.refresh(channel_connection)
                saved_channels.append(channel_connection)

        publisher.clear_cached_tokens(current_company.id)
        logger.info("Buffer connect completed company_id=%s saved_channels=%s", current_company.id, len(saved_channels))
        return [ChannelConnection.model_validate(c) for c in saved_channels]

    except Exception as e:
        logger.exception("Buffer connect failed company_id=%s: %s", current_company.id, e)
        raise HTTPException(
            status_code=400,
            detail=f"Failed to connect Buffer: {str(e)}"
        )


@router.delete("/buffer/channels/{channel_id}", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect_buffer_channel(
    channel_id: UUID,
    current_company = Depends(get_current_company),
    db: AsyncSession = Depends(get_db),
):
    """Disconnect a Buffer channel."""
    publisher = get_publisher()
    logger.info("Disconnect channel requested company_id=%s channel_id=%s", current_company.id, channel_id)

    result = await db.execute(
        select(ChannelConnectionModel).where(
            ChannelConnectionModel.id == channel_id,
            ChannelConnectionModel.company_id == current_company.id
        )
    )
    channel = result.scalar_one_or_none()

    if not channel:
        logger.warning("Disconnect channel failed: not found company_id=%s channel_id=%s", current_company.id, channel_id)
        raise HTTPException(status_code=404, detail="Channel not found")

    # Disconnect via publisher
    await publisher.disconnect(channel)

    # Delete from database
    await db.delete(channel)
    await db.commit()
    logger.info("Channel disconnected company_id=%s channel_id=%s platform=%s", current_company.id, channel_id, getattr(channel, "platform", None))

    return None


async def _validate_publish_request(
    request: PublishRequest,
    current_company,
    db: AsyncSession,
) -> tuple[Content, List[ChannelConnectionModel]]:
    """Shared validation for publish and schedule endpoints.

    Verifies content exists, is approved for publishing, and that all
    requested channels are active and belong to the current company.
    """
    # Verify content exists and belongs to company
    content_result = await db.execute(
        select(Content).where(
            Content.id == request.content_id,
            Content.company_id == current_company.id
        )
    )
    content = content_result.scalar_one_or_none()

    if not content:
        logger.warning(
            "Publish failed: content not found company_id=%s content_id=%s",
            current_company.id, request.content_id,
        )
        raise HTTPException(status_code=404, detail="Content not found")

    # Verify content is approved (or currently publishing via Approve & Publish flow)
    job_result = await db.execute(
        select(Content).join(Content.job).where(
            Content.id == request.content_id,
            Content.job.has(Job.status.in_(["approved", "publishing"]))
        )
    )
    if not job_result.scalar_one_or_none():
        logger.warning(
            "Publish rejected: content not approved company_id=%s content_id=%s",
            current_company.id, request.content_id,
        )
        raise HTTPException(status_code=400, detail="Content not approved for publishing")

    # Verify channels exist and belong to company
    channels_result = await db.execute(
        select(ChannelConnectionModel).where(
            ChannelConnectionModel.id.in_(request.channel_ids),
            ChannelConnectionModel.company_id == current_company.id,
            ChannelConnectionModel.is_active == True
        )
    )
    channels = channels_result.scalars().all()

    if len(channels) != len(request.channel_ids):
        logger.warning(
            "Publish failed: channel mismatch company_id=%s requested=%s resolved=%s",
            current_company.id,
            [str(c) for c in request.channel_ids],
            [str(c.id) for c in channels],
        )
        raise HTTPException(status_code=404, detail="One or more channels not found or inactive")

    # Prevent duplicate publishing to channels that already have a sent or active attempt
    existing_result = await db.execute(
        select(PublishAttempt).where(
            PublishAttempt.content_id == content.id,
            PublishAttempt.channel_id.in_([c.id for c in channels]),
            PublishAttempt.status.in_([
                PublishStatus.pending,
                PublishStatus.retrying,
                PublishStatus.sent,
            ]),
        )
    )
    existing_attempts = existing_result.scalars().all()
    if existing_attempts:
        locked_ids = {a.channel_id for a in existing_attempts}
        locked_names = [c.account_name for c in channels if c.id in locked_ids]
        logger.warning(
            "Duplicate publish rejected company_id=%s content_id=%s channels=%s",
            current_company.id,
            content.id,
            locked_names,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Content is already published or queued for: {', '.join(locked_names)}",
        )

    return content, channels


@router.post("", response_model=List[PublishAttemptResponse], status_code=status.HTTP_200_OK)
async def publish_content(
    request: PublishRequest,
    current_company = Depends(get_current_company),
    db: AsyncSession = Depends(get_db),
):
    """Publish approved content to selected channels immediately.

    Returns 200 with the final send/failed status for each channel.
    """
    logger.info(
        "Immediate publish requested company_id=%s content_id=%s channel_ids=%s",
        current_company.id,
        request.content_id,
        [str(c) for c in request.channel_ids],
    )

    content, channels = await _validate_publish_request(request, current_company, db)

    publisher = get_publisher()
    attempts = await _publish_immediate(db, content, channels, publisher)
    logger.info(
        "Immediate publish completed company_id=%s content_id=%s attempts=%s",
        current_company.id, request.content_id, len(attempts),
    )
    return [PublishAttemptResponse.model_validate(a) for a in attempts]


@router.post("/schedule", response_model=List[PublishAttemptResponse], status_code=status.HTTP_202_ACCEPTED)
async def schedule_publish(
    request: PublishRequest,
    current_company = Depends(get_current_company),
    db: AsyncSession = Depends(get_db),
):
    """Schedule approved content for publishing at a later time.

    Requires `schedule_at` to be set. Returns 202 with pending attempts.
    """
    if request.schedule_at is None:
        logger.warning(
            "Schedule publish rejected: schedule_at missing company_id=%s content_id=%s",
            current_company.id, request.content_id,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="schedule_at is required for scheduled publishing",
        )

    if request.schedule_at <= datetime.now(timezone.utc):
        logger.warning(
            "Schedule publish rejected: schedule_at in the past company_id=%s content_id=%s schedule_at=%s",
            current_company.id, request.content_id, request.schedule_at,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="schedule_at must be in the future",
        )

    logger.info(
        "Scheduled publish requested company_id=%s content_id=%s channel_ids=%s schedule_at=%s",
        current_company.id,
        request.content_id,
        [str(c) for c in request.channel_ids],
        request.schedule_at,
    )

    content, channels = await _validate_publish_request(request, current_company, db)

    publisher = get_publisher()
    queue = get_publishing_queue()
    attempts = await _enqueue_publish_attempts(
        db, content, channels, request.schedule_at, publisher, queue
    )
    logger.info(
        "Scheduled publish enqueued company_id=%s content_id=%s attempts=%s",
        current_company.id, request.content_id, len(attempts),
    )
    return [PublishAttemptResponse.model_validate(a) for a in attempts]


async def _publish_immediate(
    db: AsyncSession,
    content: Content,
    channels: List[ChannelConnectionModel],
    publisher,
) -> List[PublishAttempt]:
    """Publish immediately to all channels synchronously (no queue)."""
    
    attempts: List[PublishAttempt] = []
    
    for channel in channels:
        idempotency_key = f"publish_{content.id}_{channel.id}_{uuid4().hex[:8]}"
        
        # Get platform-specific text and image
        text = publisher._get_platform_text(content, channel.platform)
        text = publisher._truncate_text(text, channel.platform)
        image_url = publisher._select_best_image(content, channel.platform)
        
        attempt = PublishAttempt(
            content_id=content.id,
            channel_id=channel.id,
            platform=channel.platform,
            status=PublishStatus.pending,
            scheduled_at=None,
            idempotency_key=idempotency_key,
        )
        db.add(attempt)
        await db.flush()  # Get attempt ID
        
        logger.info(
            "Publishing immediately attempt_id=%s content_id=%s channel_id=%s platform=%s",
            attempt.id,
            content.id,
            channel.id,
            getattr(channel.platform, "value", str(channel.platform)),
        )
        
        previous_access_token_encrypted = channel.access_token_encrypted
        try:
            result = await publisher.publish(
                channel=channel,
                content=content,
                image_url=image_url,
                text=text,
                schedule_at=None,
            )
            await persist_refreshed_channel_tokens(db, channel, previous_access_token_encrypted)
            if channel.access_token_encrypted != previous_access_token_encrypted:
                try:
                    prev_plain = publisher._decrypt(previous_access_token_encrypted)
                except Exception:
                    prev_plain = None
                for sibling in channels:
                    if sibling.id == channel.id:
                        continue
                    same_token = sibling.access_token_encrypted == previous_access_token_encrypted
                    if not same_token and prev_plain:
                        try:
                            same_token = publisher._decrypt(sibling.access_token_encrypted) == prev_plain
                        except Exception:
                            same_token = False
                    if same_token:
                        sibling.access_token_encrypted = channel.access_token_encrypted
                        sibling.refresh_token_encrypted = channel.refresh_token_encrypted
                        sibling.token_expires_at = channel.token_expires_at
            
            if result.success:
                attempt.status = PublishStatus.sent
                attempt.external_post_id = result.external_post_id
                attempt.published_at = datetime.now(timezone.utc)
                attempt.error = None
                logger.info("Immediate publish succeeded attempt_id=%s external_post_id=%s", attempt.id, result.external_post_id)
            else:
                attempt.status = PublishStatus.failed
                attempt.error = f"{result.error_code or 'UNKNOWN'}: {result.error}"
                attempt.retry_count = 0
                logger.warning("Immediate publish failed attempt_id=%s code=%s error=%s", attempt.id, result.error_code, result.error)
                
        except Exception as e:
            logger.exception("Immediate publish error attempt_id=%s: %s", attempt.id, e)
            attempt.status = PublishStatus.failed
            attempt.error = f"Processing error: {str(e)}"
        
        attempts.append(attempt)
    
    await db.flush()
    await sync_job_publish_status(db, content.id)
    await db.commit()
    
    # Refresh to get IDs
    for attempt in attempts:
        await db.refresh(attempt)
    
    return attempts


@router.get("/attempts/{content_id}", response_model=List[PublishAttemptResponse])
async def get_publish_attempts(
    content_id: UUID,
    current_company = Depends(get_current_company),
    db: AsyncSession = Depends(get_db),
):
    """Get publishing history for a content item."""
    # Verify content belongs to company
    content_result = await db.execute(
        select(Content).where(
            Content.id == content_id,
            Content.company_id == current_company.id
        )
    )
    content = content_result.scalar_one_or_none()
    
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")
    
    result = await db.execute(
        select(PublishAttempt)
        .where(PublishAttempt.content_id == content_id)
        .order_by(PublishAttempt.created_at.desc())
    )
    attempts = result.scalars().all()
    
    return [PublishAttemptResponse.model_validate(a) for a in attempts]


@router.post("/attempts/{attempt_id}/retry", response_model=PublishAttemptResponse)
async def retry_publish(
    attempt_id: UUID,
    current_company = Depends(get_current_company),
    db: AsyncSession = Depends(get_db),
):
    """Retry a failed publish attempt."""
    logger.info("Retry publish requested company_id=%s attempt_id=%s", current_company.id, attempt_id)
    result = await db.execute(
        select(PublishAttempt)
        .join(Content, PublishAttempt.content_id == Content.id)
        .where(
            PublishAttempt.id == attempt_id,
            Content.company_id == current_company.id
        )
    )
    attempt = result.scalar_one_or_none()

    if not attempt:
        logger.warning("Retry failed: attempt not found company_id=%s attempt_id=%s", current_company.id, attempt_id)
        raise HTTPException(status_code=404, detail="Publish attempt not found")

    if attempt.status not in [PublishStatus.failed, PublishStatus.retrying]:
        logger.warning("Retry rejected: invalid status company_id=%s attempt_id=%s status=%s", current_company.id, attempt_id, attempt.status)
        raise HTTPException(status_code=400, detail="Can only retry failed or retrying attempts")

    publisher = get_publisher()
    queue = get_publishing_queue()

    try:
        if await queue.is_attempt_queued(attempt.id):
            logger.warning("Retry rejected: attempt already queued company_id=%s attempt_id=%s", current_company.id, attempt_id)
            raise HTTPException(status_code=409, detail="Publish attempt is already queued or processing")
    except RuntimeError:
        logger.exception("Retry failed: queue unavailable company_id=%s attempt_id=%s", current_company.id, attempt_id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Publishing queue is unavailable (Redis is not running)",
        )

    channel = await db.get(ChannelConnectionModel, attempt.channel_id)
    content = await db.get(Content, attempt.content_id)

    if not channel or not content:
        logger.warning(
            "Retry skipped enqueue: missing channel/content company_id=%s attempt_id=%s channel=%s content=%s",
            current_company.id, attempt_id, bool(channel), bool(content),
        )
        attempt.status = PublishStatus.failed
        attempt.error = "Channel or content no longer available"
        await sync_job_publish_status(db, attempt.content_id)
        await db.commit()
        await db.refresh(attempt)
        return PublishAttemptResponse.model_validate(attempt)

    text = publisher._get_platform_text(content, channel.platform)
    text = publisher._truncate_text(text, channel.platform)
    image_url = publisher._select_best_image(content, channel.platform)

    # Rotate idempotency key and force enqueue before updating DB status to retrying
    attempt.idempotency_key = f"publish_{attempt.content_id}_{attempt.channel_id}_{uuid4().hex[:8]}"
    attempt.retry_count += 1

    try:
        enqueued = await queue.enqueue(attempt, channel, content, text, image_url, force=True)
        if not enqueued:
            raise RuntimeError("Queue rejected retry enqueue")
    except RuntimeError:
        logger.exception("Retry failed: queue unavailable company_id=%s attempt_id=%s", current_company.id, attempt_id)
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Publishing queue is unavailable (Redis is not running)",
        )

    attempt.status = PublishStatus.retrying
    attempt.updated_at = datetime.now(timezone.utc)
    attempt.error = None
    await db.flush()
    await sync_job_publish_status(db, attempt.content_id)
    await db.commit()
    await db.refresh(attempt)

    queue.start_worker_task()
    logger.info("Retry attempt re-enqueued company_id=%s attempt_id=%s channel_id=%s retry_count=%s", current_company.id, attempt_id, channel.id, attempt.retry_count)

    return PublishAttemptResponse.model_validate(attempt)


@router.get("/queue/stats")
async def get_queue_stats(
    current_company = Depends(get_current_company),
):
    """Get publishing queue statistics."""
    queue = get_publishing_queue()
    try:
        stats = await queue.get_queue_stats()
    except RuntimeError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Publishing queue is unavailable (Redis is not running)",
        )
    return stats

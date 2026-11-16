from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, join
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
from app.services.publisher import get_publisher, BufferPublisher
from app.services.publish_queue import get_publishing_queue, PublishJob, PublishingQueue

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

        # Create job for queue
        job = PublishJob(
            attempt_id=attempt.id,
            content_id=content.id,
            channel_id=channel.id,
            platform=channel.platform,
            text=text,
            image_url=image_url,
            schedule_at=schedule_at,
            idempotency_key=idempotency_key,
        )

        # Enqueue
        try:
            await queue.enqueue(attempt, channel, content, text, image_url)
        except RuntimeError:
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
    
    # Store state in session or cache for verification
    # For now, we'll just return the URL
    authorization_url = await publisher.get_authorization_url(state)
    
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
    
    try:
        # Exchange code for tokens
        channel_connections = await publisher.exchange_code(request.code, request.state)
        
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
                # Insert new channel
                db.add(channel_connection)
                await db.commit()
                await db.refresh(channel_connection)
                saved_channels.append(channel_connection)
        
        return [ChannelConnection.model_validate(c) for c in saved_channels]
        
    except Exception as e:
        logger.error(f"Buffer connect failed: {e}")
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
    
    result = await db.execute(
        select(ChannelConnectionModel).where(
            ChannelConnectionModel.id == channel_id,
            ChannelConnectionModel.company_id == current_company.id
        )
    )
    channel = result.scalar_one_or_none()
    
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    # Disconnect via publisher
    await publisher.disconnect(channel)
    
    # Delete from database
    await db.delete(channel)
    await db.commit()
    
    return None


@router.post("", response_model=List[PublishAttemptResponse], status_code=status.HTTP_202_ACCEPTED)
async def publish_content(
    request: PublishRequest,
    current_company = Depends(get_current_company),
    db: AsyncSession = Depends(get_db),
):
    """Publish approved content to selected channels."""
    # Verify content exists and belongs to company
    content_result = await db.execute(
        select(Content).where(
            Content.id == request.content_id,
            Content.company_id == current_company.id
        )
    )
    content = content_result.scalar_one_or_none()
    
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")
    
    # Verify content is approved
    job_result = await db.execute(
        select(Content).join(Content.job).where(
            Content.id == request.content_id,
            Content.job.has(status="approved")
        )
    )
    if not job_result.scalar_one_or_none():
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
        raise HTTPException(status_code=404, detail="One or more channels not found or inactive")
    
    # Get publisher and queue
    publisher = get_publisher()
    queue = get_publishing_queue()
    
    # Create publish attempts and queue them
    attempts = await _enqueue_publish_attempts(
        db, content, channels, request.schedule_at, publisher, queue
    )
    
    return [PublishAttemptResponse.model_validate(a) for a in attempts]


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
        raise HTTPException(status_code=404, detail="Publish attempt not found")
    
    if attempt.status not in [PublishStatus.failed, PublishStatus.retrying]:
        raise HTTPException(status_code=400, detail="Can only retry failed or retrying attempts")
    
    # Reset for retry
    attempt.status = PublishStatus.retrying
    attempt.retry_count += 1
    attempt.updated_at = datetime.now(timezone.utc)
    attempt.error = None
    await db.commit()
    await db.refresh(attempt)
    
    # Re-queue
    publisher = get_publisher()
    queue = get_publishing_queue()
    
    channel = await db.get(ChannelConnectionModel, attempt.channel_id)
    content = await db.get(Content, attempt.content_id)
    
    if channel and content:
        text = publisher._get_platform_text(content, channel.platform)
        text = publisher._truncate_text(text, channel.platform)
        image_url = publisher._select_best_image(content, channel.platform)
        
        job = PublishJob(
            attempt_id=attempt.id,
            content_id=attempt.content_id,
            channel_id=attempt.channel_id,
            platform=channel.platform,
            text=text,
            image_url=image_url,
            schedule_at=attempt.scheduled_at,
            idempotency_key=attempt.idempotency_key,
            retry_count=attempt.retry_count,
        )
        
        try:
            await queue.enqueue(attempt, channel, content, text, image_url)
        except RuntimeError:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Publishing queue is unavailable (Redis is not running)",
            )
        queue.start_worker_task()
    
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


# Add logger import
import logging
logger = logging.getLogger(__name__)

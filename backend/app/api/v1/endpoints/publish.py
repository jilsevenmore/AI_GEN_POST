from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List
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

router = APIRouter()


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
    # TODO: Implement real Buffer OAuth PKCE flow (Phase 6)
    state = "mock_state_" + str(uuid4())[:8]
    return BufferConnectResponse(
        authorization_url=f"https://publish.buffer.com/oauth2/authorize?client_id=mock&redirect_uri=http://localhost:5173/auth/buffer/callback&response_type=code&state={state}",
        state=state,
    )


@router.post("/buffer/connect", response_model=ChannelConnection)
async def connect_buffer(
    request: BufferConnectRequest,
    current_company = Depends(get_current_company),
    db: AsyncSession = Depends(get_db),
):
    """Complete Buffer OAuth connection."""
    # TODO: Implement real token exchange (Phase 6)
    # For now, create a mock channel
    channel = ChannelConnectionModel(
        company_id=current_company.id,
        platform=Platform.instagram,
        external_account_id="ig_new_" + str(uuid4())[:8],
        account_name="New Instagram Account",
        access_token_encrypted="encrypted_token_placeholder",
        is_active=True,
    )
    db.add(channel)
    await db.commit()
    await db.refresh(channel)
    
    return ChannelConnection.model_validate(channel)


@router.delete("/buffer/channels/{channel_id}", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect_buffer_channel(
    channel_id: UUID,
    current_company = Depends(get_current_company),
    db: AsyncSession = Depends(get_db),
):
    """Disconnect a Buffer channel."""
    result = await db.execute(
        select(ChannelConnectionModel).where(
            ChannelConnectionModel.id == channel_id,
            ChannelConnectionModel.company_id == current_company.id
        )
    )
    channel = result.scalar_one_or_none()
    
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
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
    
    # Verify channels exist and belong to company
    channels_result = await db.execute(
        select(ChannelConnectionModel).where(
            ChannelConnectionModel.id.in_(request.channel_ids),
            ChannelConnectionModel.company_id == current_company.id
        )
    )
    channels = channels_result.scalars().all()
    
    if len(channels) != len(request.channel_ids):
        raise HTTPException(status_code=404, detail="One or more channels not found")
    
    # Create publish attempts
    attempts = []
    for channel in channels:
        idempotency_key = f"publish_{request.content_id}_{channel.id}_{uuid4().hex[:8]}"
        
        attempt = PublishAttempt(
            content_id=request.content_id,
            channel_id=channel.id,
            platform=channel.platform,
            status=PublishStatus.pending,
            scheduled_at=request.schedule_at,
            idempotency_key=idempotency_key,
        )
        db.add(attempt)
        attempts.append(attempt)
    
    await db.commit()
    
    # Refresh to get IDs
    for attempt in attempts:
        await db.refresh(attempt)
    
    # TODO: Queue background publishing job (Phase 6)
    
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
    
    if attempt.status != PublishStatus.failed:
        raise HTTPException(status_code=400, detail="Can only retry failed attempts")
    
    attempt.status = PublishStatus.retrying
    attempt.retry_count += 1
    attempt.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(attempt)
    
    # TODO: Queue retry job (Phase 6)
    
    return PublishAttemptResponse.model_validate(attempt)
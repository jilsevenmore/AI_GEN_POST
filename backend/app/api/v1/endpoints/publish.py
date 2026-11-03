from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from uuid import UUID, uuid4
from datetime import datetime
from app.db.session import get_db
from app.schemas.common import (
    ChannelConnection, PublishRequest, PublishAttemptResponse,
    BufferConnectRequest, BufferConnectResponse, PublishStatus, Platform
)

router = APIRouter()

# Mock stores
MOCK_CHANNELS = {}
MOCK_PUBLISH_ATTEMPTS = {}


@router.get("/channels", response_model=List[ChannelConnection])
async def list_channels(db: AsyncSession = Depends(get_db)):
    """List connected social channels for the current company."""
    # TODO: Implement real channel listing from DB
    return [
        ChannelConnection(
            id=uuid4(),
            platform=Platform.instagram,
            external_account_id="ig_123456",
            account_name="my_brand_instagram",
            is_active=True,
            connected_at=datetime.utcnow(),
        ),
        ChannelConnection(
            id=uuid4(),
            platform=Platform.facebook,
            external_account_id="fb_789012",
            account_name="My Brand Facebook",
            is_active=True,
            connected_at=datetime.utcnow(),
        ),
        ChannelConnection(
            id=uuid4(),
            platform=Platform.linkedin,
            external_account_id="li_345678",
            account_name="My Brand LinkedIn",
            is_active=True,
            connected_at=datetime.utcnow(),
        ),
    ]


@router.get("/buffer/connect", response_model=BufferConnectResponse)
async def get_buffer_auth_url(db: AsyncSession = Depends(get_db)):
    """Get Buffer OAuth authorization URL."""
    # TODO: Implement real Buffer OAuth PKCE flow
    state = "mock_state_" + str(uuid4())[:8]
    return BufferConnectResponse(
        authorization_url=f"https://publish.buffer.com/oauth2/authorize?client_id=mock&redirect_uri=http://localhost:5173/auth/buffer/callback&response_type=code&state={state}",
        state=state,
    )


@router.post("/buffer/connect", response_model=ChannelConnection)
async def connect_buffer(
    request: BufferConnectRequest,
    db: AsyncSession = Depends(get_db),
):
    """Complete Buffer OAuth connection."""
    # TODO: Implement real token exchange
    return ChannelConnection(
        id=uuid4(),
        platform=Platform.instagram,
        external_account_id="ig_new_123",
        account_name="New Instagram Account",
        is_active=True,
        connected_at=datetime.utcnow(),
    )


@router.delete("/buffer/channels/{channel_id}", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect_buffer_channel(channel_id: UUID, db: AsyncSession = Depends(get_db)):
    """Disconnect a Buffer channel."""
    # TODO: Implement real disconnection
    return None


@router.post("", response_model=List[PublishAttemptResponse], status_code=status.HTTP_202_ACCEPTED)
async def publish_content(
    request: PublishRequest,
    db: AsyncSession = Depends(get_db),
):
    """Publish approved content to selected channels."""
    # TODO: Implement real publishing via Buffer API
    attempts = []
    for channel_id in request.channel_ids:
        attempt = PublishAttemptResponse(
            id=uuid4(),
            content_id=request.content_id,
            channel_id=channel_id,
            platform=Platform.instagram,  # Would come from channel
            status=PublishStatus.pending,
            scheduled_at=request.schedule_at,
            retry_count=0,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        MOCK_PUBLISH_ATTEMPTS[attempt.id] = attempt
        attempts.append(attempt)
    
    # TODO: Queue background publishing job
    return attempts


@router.get("/attempts/{content_id}", response_model=List[PublishAttemptResponse])
async def get_publish_attempts(content_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get publishing history for a content item."""
    return [a for a in MOCK_PUBLISH_ATTEMPTS.values() if a.content_id == content_id]


@router.post("/attempts/{attempt_id}/retry", response_model=PublishAttemptResponse)
async def retry_publish(attempt_id: UUID, db: AsyncSession = Depends(get_db)):
    """Retry a failed publish attempt."""
    attempt = MOCK_PUBLISH_ATTEMPTS.get(attempt_id)
    if not attempt:
        raise HTTPException(status_code=404, detail="Publish attempt not found")
    if attempt.status != PublishStatus.failed:
        raise HTTPException(status_code=400, detail="Can only retry failed attempts")
    
    attempt.status = PublishStatus.retrying
    attempt.retry_count += 1
    attempt.updated_at = datetime.utcnow()
    # TODO: Queue retry job
    return attempt
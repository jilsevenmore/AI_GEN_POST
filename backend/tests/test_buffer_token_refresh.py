"""Tests for Buffer OAuth token refresh locking, deduplication, and persistence."""
import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet

from app.services.publisher import BufferPublisher, PublishResult, persist_refreshed_channel_tokens
from app.services.publish_queue import PublishJob, PublishingQueue


def _make_channel(company_id, platform: str, access_token: str, refresh_token: str, publisher: BufferPublisher):
    return SimpleNamespace(
        id=uuid4(),
        company_id=company_id,
        platform=platform,
        external_account_id=f"ext_{platform}",
        account_name=f"Account {platform}",
        access_token_encrypted=publisher._encrypt(access_token),
        refresh_token_encrypted=publisher._encrypt(refresh_token),
        token_expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        is_active=True,
        updated_at=datetime.now(timezone.utc) - timedelta(hours=2),
    )


@pytest.mark.asyncio
async def test_concurrent_publish_deduplicates_token_refresh():
    key = Fernet.generate_key()
    publisher = BufferPublisher(encryption_key=key)
    company_id = uuid4()

    fb_channel = _make_channel(company_id, "facebook", "old_access", "old_refresh", publisher)
    ig_channel = _make_channel(company_id, "instagram", "old_access", "old_refresh", publisher)
    content = SimpleNamespace(id=uuid4())

    refresh_calls = 0

    async def fake_refresh(channel):
        nonlocal refresh_calls
        refresh_calls += 1
        # Yield control so a second coroutine would race if not locked
        await asyncio.sleep(0.02)
        channel.access_token_encrypted = publisher._encrypt("new_access")
        channel.refresh_token_encrypted = publisher._encrypt("new_refresh")
        channel.token_expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        channel.updated_at = datetime.now(timezone.utc)
        return channel

    async def fake_graphql(token, mutation):
        if token == "old_access":
            raise RuntimeError("401 Unauthorized")
        if token == "new_access":
            return {"createPost": {"post": {"id": f"post_{uuid4().hex[:6]}", "text": "hi"}}}
        raise AssertionError(f"Unexpected token: {token}")

    publisher.refresh_token = fake_refresh
    publisher._graphql = fake_graphql

    fb_res, ig_res = await asyncio.gather(
        publisher.publish(fb_channel, content, "https://example.com/a.jpg", "hello"),
        publisher.publish(ig_channel, content, "https://example.com/a.jpg", "hello"),
    )

    assert fb_res.success is True
    assert ig_res.success is True
    assert refresh_calls == 1
    assert publisher._decrypt(fb_channel.access_token_encrypted) == "new_access"
    assert publisher._decrypt(ig_channel.access_token_encrypted) == "new_access"
    assert publisher._decrypt(fb_channel.refresh_token_encrypted) == "new_refresh"
    assert publisher._decrypt(ig_channel.refresh_token_encrypted) == "new_refresh"


@pytest.mark.asyncio
async def test_persist_refreshed_channel_tokens_executes_update_only_when_changed():
    db = AsyncMock()
    channel = SimpleNamespace(
        id=uuid4(),
        company_id=uuid4(),
        access_token_encrypted="old_enc",
        refresh_token_encrypted="new_ref",
        token_expires_at=datetime.now(timezone.utc),
    )

    # No-op when unchanged
    await persist_refreshed_channel_tokens(db, channel, "old_enc")
    db.execute.assert_not_awaited()

    # Executes update when changed
    channel.access_token_encrypted = "new_enc"
    await persist_refreshed_channel_tokens(db, channel, "old_enc")
    db.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_publish_queue_process_job_persists_refreshed_tokens():
    attempt_id = uuid4()
    channel_id = uuid4()
    content_id = uuid4()
    company_id = uuid4()

    attempt = SimpleNamespace(
        id=attempt_id,
        status="pending",
        error=None,
        retry_count=0,
        external_post_id=None,
        published_at=None,
    )
    channel = SimpleNamespace(
        id=channel_id,
        company_id=company_id,
        platform="facebook",
        access_token_encrypted="old_enc",
        refresh_token_encrypted="old_ref",
        token_expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
    )
    content = SimpleNamespace(id=content_id)

    async def fake_publish(channel, content, image_url, text, schedule_at=None):
        channel.access_token_encrypted = "new_enc"
        channel.refresh_token_encrypted = "new_ref"
        channel.token_expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        return PublishResult(success=True, external_post_id="buf_123")

    publisher = MagicMock()
    publisher.publish = AsyncMock(side_effect=fake_publish)

    queue = PublishingQueue()
    queue._publisher = publisher
    queue._ensure_connected = AsyncMock()
    queue.mark_processing = AsyncMock()
    queue.wait_for_rate_limit = AsyncMock()
    queue.mark_done = AsyncMock()

    session_1 = AsyncMock()
    session_1.get = AsyncMock(side_effect=[attempt, channel, content])
    session_2 = AsyncMock()
    session_2.get = AsyncMock(return_value=attempt)

    sessions = [session_1, session_2]

    def make_session_cm():
        s = sessions.pop(0)
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=s)
        cm.__aexit__ = AsyncMock(return_value=False)
        return cm

    job = PublishJob(
        attempt_id=attempt_id,
        content_id=content_id,
        channel_id=channel_id,
        platform="facebook",
        text="hello",
        image_url="https://example.com/a.jpg",
    )

    with (
        patch("app.services.publish_queue.AsyncSessionLocal", side_effect=make_session_cm),
        patch("app.services.publish_queue.sync_job_publish_status", new_callable=AsyncMock) as mock_sync,
    ):
        await queue.process_job(job)

    assert attempt.status == "sent"
    assert attempt.external_post_id == "buf_123"
    # Second session must have executed the ChannelConnection token update and committed
    session_2.execute.assert_awaited_once()
    mock_sync.assert_awaited_once_with(session_2, content_id)
    session_2.commit.assert_awaited_once()

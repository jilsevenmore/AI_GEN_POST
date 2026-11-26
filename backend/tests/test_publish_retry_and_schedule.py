"""Tests for Option B scheduled publishing, manual retries, and stale attempt recovery."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.v1.endpoints.publish import retry_publish
from app.schemas.common import PublishStatus
from app.services.publisher import BufferPublisher, PublishResult
from app.services.publish_queue import PublishJob, PublishingQueue
from app.services.scheduled_jobs import recover_stale_publish_attempts


def _make_fake_redis():
    store: dict[str, str] = {}
    lists: dict[str, list[str]] = {}
    zsets: dict[str, dict[str, float]] = {}
    sets: dict[str, set[str]] = {}

    r = MagicMock()
    r.get = AsyncMock(side_effect=lambda k: store.get(k))
    r.set = AsyncMock(side_effect=lambda k, v, ex=None: store.__setitem__(k, v))
    r.lpush = AsyncMock(side_effect=lambda k, v: lists.setdefault(k, []).insert(0, v))
    r.lrange = AsyncMock(side_effect=lambda k, start, end: lists.get(k, []))
    r.zadd = AsyncMock(side_effect=lambda k, mapping: zsets.setdefault(k, {}).update(mapping))
    r.zrange = AsyncMock(side_effect=lambda k, start, end: list(zsets.get(k, {}).keys()))
    r.sismember = AsyncMock(side_effect=lambda k, v: v in sets.get(k, set()))
    return r, store, lists, zsets, sets


@pytest.mark.asyncio
async def test_enqueue_scheduled_dispatches_to_immediate_queue_and_force_bypasses_idempotency():
    r, store, lists, zsets, _ = _make_fake_redis()
    queue = PublishingQueue()
    queue._redis = r

    future_time = datetime.now(timezone.utc) + timedelta(hours=2)
    attempt = SimpleNamespace(
        id=uuid4(),
        content_id=uuid4(),
        channel_id=uuid4(),
        scheduled_at=future_time,
        idempotency_key="idem_key_1",
        retry_count=0,
    )
    channel = SimpleNamespace(platform="instagram")
    content = SimpleNamespace(id=attempt.content_id)

    # First enqueue succeeds and goes straight to QUEUE_NAME (not SCHEDULED_QUEUE)
    first = await queue.enqueue(attempt, channel, content, "hello", "https://img.test/1.png")
    assert first is True
    assert len(lists.get(queue.QUEUE_NAME, [])) == 1
    assert len(zsets.get(queue.SCHEDULED_QUEUE, {})) == 0

    # Duplicate without force is skipped
    dup = await queue.enqueue(attempt, channel, content, "hello", "https://img.test/1.png")
    assert dup is False
    assert len(lists[queue.QUEUE_NAME]) == 1

    # Force=True (manual retry) bypasses idempotency and re-enqueues
    forced = await queue.enqueue(attempt, channel, content, "hello", "https://img.test/1.png", force=True)
    assert forced is True
    assert len(lists[queue.QUEUE_NAME]) == 2


@pytest.mark.asyncio
async def test_requeue_preserves_target_schedule_at():
    r, _, lists, zsets, _ = _make_fake_redis()
    queue = PublishingQueue()
    queue._redis = r

    target_schedule = datetime.now(timezone.utc) + timedelta(hours=3)
    job = PublishJob(
        attempt_id=uuid4(),
        content_id=uuid4(),
        channel_id=uuid4(),
        platform="facebook",
        text="scheduled post",
        schedule_at=target_schedule,
    )

    await queue.requeue(job, delay=60)
    assert job.retry_count == 1
    assert job.schedule_at == target_schedule
    stored_raw = next(iter(zsets[queue.SCHEDULED_QUEUE].keys()))
    assert PublishJob.from_json(stored_raw).schedule_at == target_schedule


@pytest.mark.asyncio
async def test_process_job_clears_past_schedule_at_for_immediate_publish():
    attempt_id = uuid4()
    channel_id = uuid4()
    content_id = uuid4()

    attempt = SimpleNamespace(
        id=attempt_id,
        status="retrying",
        error=None,
        retry_count=1,
        external_post_id=None,
        published_at=None,
    )
    channel = SimpleNamespace(
        id=channel_id,
        company_id=uuid4(),
        platform="instagram",
        access_token_encrypted="enc",
    )
    content = SimpleNamespace(id=content_id)

    publisher = MagicMock()
    publisher.publish = AsyncMock(return_value=PublishResult(success=True, external_post_id="buf_past_ok"))

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

    past_time = datetime.now(timezone.utc) - timedelta(minutes=10)
    job = PublishJob(
        attempt_id=attempt_id,
        content_id=content_id,
        channel_id=channel_id,
        platform="instagram",
        text="hello",
        image_url="https://example.com/a.jpg",
        schedule_at=past_time,
        retry_count=1,
    )

    with (
        patch("app.services.publish_queue.AsyncSessionLocal", side_effect=make_session_cm),
        patch("app.services.publish_queue.sync_job_publish_status", new_callable=AsyncMock),
    ):
        await queue.process_job(job)

    assert attempt.status == "sent"
    assert publisher.publish.await_args.kwargs["schedule_at"] is None


@pytest.mark.asyncio
async def test_retry_publish_rotates_key_forces_enqueue_and_rejects_already_queued():
    company_id = uuid4()
    attempt_id = uuid4()
    content_id = uuid4()
    channel_id = uuid4()
    old_key = "publish_old_key"

    attempt = SimpleNamespace(
        id=attempt_id,
        content_id=content_id,
        channel_id=channel_id,
        platform="instagram",
        status=PublishStatus.failed,
        external_post_id=None,
        error="NO_POST_ID: Scheduled time must be in the future",
        retry_count=0,
        idempotency_key=old_key,
        scheduled_at=datetime.now(timezone.utc) - timedelta(hours=1),
        published_at=None,
        created_at=datetime.now(timezone.utc) - timedelta(hours=1),
        updated_at=datetime.now(timezone.utc) - timedelta(hours=1),
    )
    channel = SimpleNamespace(id=channel_id, platform="instagram")
    content = SimpleNamespace(id=content_id)

    db = AsyncMock()
    exec_result = MagicMock()
    exec_result.scalar_one_or_none = MagicMock(return_value=attempt)
    db.execute = AsyncMock(return_value=exec_result)
    db.get = AsyncMock(side_effect=[channel, content])

    publisher = MagicMock()
    publisher._get_platform_text.return_value = "text"
    publisher._truncate_text.return_value = "text"
    publisher._select_best_image.return_value = "https://example.com/img.png"

    queue = MagicMock()
    queue.is_attempt_queued = AsyncMock(return_value=False)
    queue.enqueue = AsyncMock(return_value=True)
    queue.start_worker_task = MagicMock()

    company = SimpleNamespace(id=company_id)

    with (
        patch("app.api.v1.endpoints.publish.get_publisher", return_value=publisher),
        patch("app.api.v1.endpoints.publish.get_publishing_queue", return_value=queue),
        patch("app.api.v1.endpoints.publish.sync_job_publish_status", new_callable=AsyncMock) as mock_sync,
    ):
        resp = await retry_publish(attempt_id, current_company=company, db=db)

    assert resp.status == PublishStatus.retrying
    assert resp.retry_count == 1
    assert attempt.idempotency_key != old_key
    assert queue.enqueue.await_args.kwargs["force"] is True
    queue.start_worker_task.assert_called_once()
    mock_sync.assert_awaited_once_with(db, content_id)

    # Now verify 409 when attempt is already queued in Redis
    queue.is_attempt_queued = AsyncMock(return_value=True)
    exec_result2 = MagicMock()
    exec_result2.scalar_one_or_none = MagicMock(return_value=attempt)
    db.execute = AsyncMock(return_value=exec_result2)

    with (
        patch("app.api.v1.endpoints.publish.get_publisher", return_value=publisher),
        patch("app.api.v1.endpoints.publish.get_publishing_queue", return_value=queue),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await retry_publish(attempt_id, current_company=company, db=db)
    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_recover_stale_publish_attempts_marks_orphaned_attempts_failed():
    stale_id = uuid4()
    active_id = uuid4()
    content_id = uuid4()
    old_time = datetime.now(timezone.utc) - timedelta(minutes=30)

    stale_attempt = SimpleNamespace(
        id=stale_id,
        content_id=content_id,
        status="retrying",
        error=None,
        updated_at=old_time,
    )
    active_attempt = SimpleNamespace(
        id=active_id,
        content_id=content_id,
        status="retrying",
        error=None,
        updated_at=old_time,
    )

    queue = MagicMock()
    queue._ensure_connected = AsyncMock()
    queue.is_attempt_queued = AsyncMock(side_effect=lambda aid: aid == active_id)

    session = AsyncMock()
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = [stale_attempt, active_attempt]
    exec_res = MagicMock()
    exec_res.scalars.return_value = scalars_mock
    session.execute = AsyncMock(return_value=exec_res)

    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("app.services.publish_queue.get_publishing_queue", return_value=queue),
        patch("app.services.publisher.sync_job_publish_status", new_callable=AsyncMock) as mock_sync,
        patch("app.services.scheduled_jobs.AsyncSessionLocal", return_value=cm),
    ):
        result = await recover_stale_publish_attempts(stale_minutes=15)

    assert result == {"recovered": 1}
    assert stale_attempt.status == "failed"
    assert stale_attempt.error is not None
    assert active_attempt.status == "retrying"
    mock_sync.assert_awaited_once_with(session, content_id)
    session.commit.assert_awaited_once()


def test_get_platform_text_deduplicates_and_normalizes_hashtags():
    publisher = BufferPublisher()
    content = SimpleNamespace(
        long_text="Fallback",
        platform_contents=[
            {
                "platform": "instagram",
                "text": "Swipe for 3 ways AI is changing work 👉\n\n#ArtificialIntelligence #FutureOfWork",
                "hashtags": [
                    "#ArtificialIntelligence",
                    "futureofwork",
                    "#TechLeadership",
                    "TechLeadership",
                    "Catz",
                ],
            }
        ],
    )

    result = publisher._get_platform_text(content, "instagram")
    assert result == (
        "Swipe for 3 ways AI is changing work 👉\n\n"
        "#ArtificialIntelligence #FutureOfWork\n\n"
        "#TechLeadership #Catz"
    )
    assert "##" not in result


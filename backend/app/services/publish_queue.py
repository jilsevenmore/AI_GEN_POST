"""Publishing queue with Redis for rate limiting and background processing."""
import json
import logging
import asyncio
from typing import Optional, Dict, Any, List
from uuid import UUID, uuid4
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, asdict
from enum import Enum

import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_

from app.db.session import AsyncSessionLocal
from app.models.publish import PublishAttempt
from app.models.channel import ChannelConnection
from app.models.content import Content
from app.services.publisher import get_publisher, Publisher, PublishResult

logger = logging.getLogger(__name__)


class PublishStatus(str, Enum):
    PENDING = "pending"
    QUEUED = "queued"
    PROCESSING = "processing"
    SENT = "sent"
    FAILED = "failed"
    RETRYING = "retrying"
    DEAD_LETTER = "dead_letter"


@dataclass
class PublishJob:
    """Job data for the publishing queue."""
    attempt_id: UUID
    content_id: UUID
    channel_id: UUID
    platform: str
    text: str
    image_url: str
    schedule_at: Optional[datetime] = None
    idempotency_key: str = ""
    retry_count: int = 0
    max_retries: int = 3
    
    def to_json(self) -> str:
        data = asdict(self)
        # Convert UUIDs and datetimes to strings
        data["attempt_id"] = str(data["attempt_id"])
        data["content_id"] = str(data["content_id"])
        data["channel_id"] = str(data["channel_id"])
        if data["schedule_at"]:
            data["schedule_at"] = data["schedule_at"].isoformat()
        return json.dumps(data)
    
    @classmethod
    def from_json(cls, json_str: str) -> "PublishJob":
        data = json.loads(json_str)
        data["attempt_id"] = UUID(data["attempt_id"])
        data["content_id"] = UUID(data["content_id"])
        data["channel_id"] = UUID(data["channel_id"])
        if data["schedule_at"]:
            data["schedule_at"] = datetime.fromisoformat(data["schedule_at"])
        return cls(**data)


class PublishingQueue:
    """
    Redis-based publishing queue with rate limiting.
    
    Features:
    - Rate limiting (100 req/15 min per app)
    - Priority queue for scheduled posts
    - Exponential backoff retries
    - Dead letter queue for failed jobs
    - Idempotency key checking
    """
    
    # Queue names
    QUEUE_NAME = "publish_queue"
    SCHEDULED_QUEUE = "publish_scheduled"
    DEAD_LETTER_QUEUE = "publish_dead_letter"
    PROCESSING_SET = "publish_processing"
    RATE_LIMIT_KEY = "publish_rate_limit"
    IDEMPOTENCY_PREFIX = "publish_idempotency:"
    
    # Rate limit: 100 requests per 15 minutes (900 seconds)
    RATE_LIMIT_MAX = 100
    RATE_LIMIT_WINDOW = 900  # seconds
    
    def __init__(self, redis_url: str = None):
        self.redis_url = redis_url or "redis://localhost:6379/0"
        self._redis: Optional[redis.Redis] = None
        self._publisher = get_publisher()
        self._worker_task: Optional[asyncio.Task] = None
        self._running = False
    
    async def connect(self):
        """Connect to Redis."""
        self._redis = redis.from_url(self.redis_url, decode_responses=True)
        await self._redis.ping()
        logger.info("Publishing queue connected to Redis")
    
    async def disconnect(self):
        """Disconnect from Redis."""
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        if self._redis:
            await self._redis.close()
        logger.info("Publishing queue disconnected")
    
    def _get_idempotency_key(self, idempotency_key: str) -> str:
        return f"{self.IDEMPOTENCY_PREFIX}{idempotency_key}"
    
    async def check_idempotency(self, idempotency_key: str) -> Optional[UUID]:
        """Check if idempotency key exists, return existing attempt ID."""
        key = self._get_idempotency_key(idempotency_key)
        existing = await self._redis.get(key)
        if existing:
            return UUID(existing)
        return None
    
    async def set_idempotency(self, idempotency_key: str, attempt_id: UUID, ttl: int = 86400 * 7):
        """Set idempotency key with TTL (default 7 days)."""
        key = self._get_idempotency_key(idempotency_key)
        await self._redis.set(key, str(attempt_id), ex=ttl)
    
    async def check_rate_limit(self) -> bool:
        """Check if we're under rate limit. Returns True if allowed."""
        current = await self._redis.get(self.RATE_LIMIT_KEY)
        if current is None:
            # First request, set with expiry
            await self._redis.set(self.RATE_LIMIT_KEY, "1", ex=self.RATE_LIMIT_WINDOW)
            return True
        
        count = int(current)
        if count >= self.RATE_LIMIT_MAX:
            return False
        
        await self._redis.incr(self.RATE_LIMIT_KEY)
        return True
    
    async def wait_for_rate_limit(self, check_interval: float = 1.0) -> None:
        """Wait until rate limit allows a request."""
        while not await self.check_rate_limit():
            await asyncio.sleep(check_interval)
    
    async def enqueue(
        self,
        attempt: PublishAttempt,
        channel: ChannelConnection,
        content: Content,
        text: str,
        image_url: str,
    ) -> bool:
        """Add a publish job to the queue."""
        # Check idempotency
        existing_id = await self.check_idempotency(attempt.idempotency_key)
        if existing_id:
            logger.info(f"Duplicate publish attempt detected: {attempt.idempotency_key}")
            return False
        
        # Create job
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
        
        # Set idempotency key
        await self.set_idempotency(attempt.idempotency_key, attempt.id)
        
        if attempt.scheduled_at and attempt.scheduled_at > datetime.now(timezone.utc):
            # Schedule for later - add to scheduled queue with score = timestamp
            score = attempt.scheduled_at.timestamp()
            await self._redis.zadd(self.SCHEDULED_QUEUE, {job.to_json(): score})
            logger.info(f"Scheduled publish for {attempt.scheduled_at}: {attempt.id}")
        else:
            # Add to immediate queue
            await self._redis.lpush(self.QUEUE_NAME, job.to_json())
            logger.info(f"Enqueued publish: {attempt.id}")
        
        return True
    
    async def dequeue(self) -> Optional[PublishJob]:
        """Get next job from queue, checking scheduled queue first."""
        # First, move any due scheduled jobs to main queue
        await self._move_due_scheduled()
        
        # Try to get from main queue
        job_json = await self._redis.rpop(self.QUEUE_NAME)
        if job_json:
            return PublishJob.from_json(job_json)
        return None
    
    async def _move_due_scheduled(self):
        """Move scheduled jobs that are due to the main queue."""
        now = datetime.now(timezone.utc).timestamp()
        due_jobs = await self._redis.zrangebyscore(
            self.SCHEDULED_QUEUE, 0, now, start=0, num=100
        )
        
        if due_jobs:
            # Remove from scheduled and add to main queue
            pipeline = self._redis.pipeline()
            for job_json in due_jobs:
                pipeline.zrem(self.SCHEDULED_QUEUE, job_json)
                pipeline.lpush(self.QUEUE_NAME, job_json)
            await pipeline.execute()
            logger.info(f"Moved {len(due_jobs)} scheduled jobs to queue")
    
    async def requeue(self, job: PublishJob, delay: float = 0) -> None:
        """Requeue a job for retry."""
        job.retry_count += 1
        if delay > 0:
            # Schedule for later
            schedule_at = datetime.now(timezone.utc) + timedelta(seconds=delay)
            job.schedule_at = schedule_at
            score = schedule_at.timestamp()
            await self._redis.zadd(self.SCHEDULED_QUEUE, {job.to_json(): score})
        else:
            await self._redis.lpush(self.QUEUE_NAME, job.to_json())
    
    async def move_to_dead_letter(self, job: PublishJob, error: str) -> None:
        """Move job to dead letter queue."""
        dead_letter_data = {
            "job": job.to_json(),
            "error": error,
            "failed_at": datetime.now(timezone.utc).isoformat(),
        }
        await self._redis.lpush(self.DEAD_LETTER_QUEUE, json.dumps(dead_letter_data))
        logger.warning(f"Moved job to dead letter: {job.attempt_id} - {error}")
    
    async def mark_processing(self, attempt_id: UUID) -> None:
        """Mark attempt as being processed."""
        await self._redis.sadd(self.PROCESSING_SET, str(attempt_id))
    
    async def mark_done(self, attempt_id: UUID) -> None:
        """Mark attempt as done processing."""
        await self._redis.srem(self.PROCESSING_SET, str(attempt_id))
    
    async def get_queue_stats(self) -> Dict[str, int]:
        """Get queue statistics."""
        pipe = self._redis.pipeline()
        pipe.llen(self.QUEUE_NAME)
        pipe.zcard(self.SCHEDULED_QUEUE)
        pipe.llen(self.DEAD_LETTER_QUEUE)
        pipe.scard(self.PROCESSING_SET)
        results = await pipe.execute()
        
        return {
            "queued": results[0],
            "scheduled": results[1],
            "dead_letter": results[2],
            "processing": results[3],
        }
    
    async def process_job(self, job: PublishJob) -> None:
        """Process a single publish job."""
        attempt_id = job.attempt_id
        
        # Mark as processing
        await self.mark_processing(attempt_id)
        
        try:
            # Get fresh data from DB
            async with AsyncSessionLocal() as db:
                attempt = await db.get(PublishAttempt, attempt_id)
                if not attempt:
                    logger.error(f"Attempt not found: {attempt_id}")
                    return
                
                channel = await db.get(ChannelConnection, job.channel_id)
                if not channel:
                    logger.error(f"Channel not found: {job.channel_id}")
                    attempt.status = "failed"
                    attempt.error = "Channel not found"
                    await db.commit()
                    return
                
                content = await db.get(Content, job.content_id)
                if not content:
                    logger.error(f"Content not found: {job.content_id}")
                    attempt.status = "failed"
                    attempt.error = "Content not found"
                    await db.commit()
                    return
                
                # Update status to processing
                attempt.status = "retrying" if job.retry_count > 0 else "pending"
                await db.commit()
            
            # Wait for rate limit
            await self.wait_for_rate_limit()
            
            # Publish
            result = await self._publisher.publish(
                channel=channel,
                content=content,
                image_url=job.image_url,
                text=job.text,
                schedule_at=job.schedule_at,
            )
            
            async with AsyncSessionLocal() as db:
                attempt = await db.get(PublishAttempt, attempt_id)
                if not attempt:
                    return
                
                if result.success:
                    attempt.status = "sent"
                    attempt.external_post_id = result.external_post_id
                    attempt.published_at = datetime.now(timezone.utc)
                    attempt.error = None
                    logger.info(f"Published successfully: {attempt_id} -> {result.external_post_id}")
                else:
                    # Handle failure
                    error_code = result.error_code or "UNKNOWN"
                    attempt.error = f"{error_code}: {result.error}"
                    attempt.retry_count = job.retry_count
                    
                    # Determine if we should retry
                    should_retry = job.retry_count < job.max_retries and error_code in [
                        "RATE_LIMITED",
                        "TOKEN_EXPIRED",
                        "MEDIA_FETCH_FAILED",
                        "API_ERROR",
                        "UNKNOWN_ERROR",
                    ]
                    
                    if should_retry:
                        attempt.status = "retrying"
                        # Calculate exponential backoff: 2^retry * 60 seconds
                        delay = min(2 ** job.retry_count * 60, 3600)  # Max 1 hour
                        logger.info(f"Scheduling retry for {attempt_id} in {delay}s (attempt {job.retry_count + 1})")
                        await self.requeue(job, delay=delay)
                    else:
                        attempt.status = "failed"
                        await self.move_to_dead_letter(job, result.error or "Unknown error")
                        logger.error(f"Publish failed permanently: {attempt_id} - {result.error}")
                
                await db.commit()
        
        except Exception as e:
            logger.exception(f"Error processing job {attempt_id}: {e}")
            async with AsyncSessionLocal() as db:
                attempt = await db.get(PublishAttempt, attempt_id)
                if attempt:
                    attempt.status = "failed"
                    attempt.error = f"Processing error: {str(e)}"
                    await db.commit()
            await self.move_to_dead_letter(job, str(e))
        
        finally:
            await self.mark_done(attempt_id)
    
    async def start_worker(self, poll_interval: float = 2.0) -> None:
        """Start the background worker."""
        self._running = True
        logger.info("Publishing worker started")
        
        while self._running:
            try:
                job = await self.dequeue()
                if job:
                    await self.process_job(job)
                else:
                    await asyncio.sleep(poll_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception(f"Worker error: {e}")
                await asyncio.sleep(poll_interval)
    
    def start_worker_task(self, poll_interval: float = 2.0) -> asyncio.Task:
        """Start worker as asyncio task."""
        self._worker_task = asyncio.create_task(self.start_worker(poll_interval))
        return self._worker_task
    
    async def stop_worker(self) -> None:
        """Stop the background worker."""
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass


# Global queue instance
_queue_instance: Optional[PublishingQueue] = None


def get_publishing_queue() -> PublishingQueue:
    """Get or create the publishing queue instance."""
    global _queue_instance
    if _queue_instance is None:
        _queue_instance = PublishingQueue()
    return _queue_instance
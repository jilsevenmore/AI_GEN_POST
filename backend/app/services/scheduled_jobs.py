"""Scheduled jobs for cleanup and maintenance."""
import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.services.image_library import ImageLibraryService
from app.models.image import Image as ImageModel
from app.models.job import Job
from app.models.publish import PublishAttempt

logger = logging.getLogger(__name__)


async def cleanup_old_images() -> dict:
    """Cleanup old library images based on retention policy."""
    logger.info("Starting image cleanup job")
    
    async with AsyncSessionLocal() as db:
        service = ImageLibraryService(db)
        result = await service.cleanup_old_images()
        
        logger.info(f"Image cleanup completed: {result}")
        return result


async def cleanup_failed_jobs(retention_days: int = 7) -> dict:
    """Clean up old failed/abandoned jobs."""
    logger.info("Starting failed job cleanup")
    
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    
    async with AsyncSessionLocal() as db:
        # Find old failed/pending jobs that are stuck
        result = await db.execute(
            select(Job).where(
                Job.status.in_(["failed", "pending", "expanding_prompt", "writing_text"]),
                Job.updated_at < cutoff,
            )
        )
        old_jobs = result.scalars().all()
        
        count = len(old_jobs)
        for job in old_jobs:
            if job.status == "pending":
                job.status = "failed"
                job.error = "Cleaned up: stuck in pending state"
            # Already failed jobs just get cleaned up metadata
            job.updated_at = datetime.now(timezone.utc)
        
        await db.commit()
        
        logger.info(f"Cleaned up {count} old jobs")
        return {"jobs_cleaned": count}


async def cleanup_old_publish_attempts(retention_days: int = 90) -> dict:
    """Clean up old publish attempt records."""
    logger.info("Starting publish attempt cleanup")
    
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(PublishAttempt).where(
                PublishAttempt.created_at < cutoff,
                PublishAttempt.status.in_(["sent", "failed"]),
            )
        )
        old_attempts = result.scalars().all()
        
        count = len(old_attempts)
        for attempt in old_attempts:
            await db.delete(attempt)
        
        await db.commit()
        
        logger.info(f"Cleaned up {count} old publish attempts")
        return {"attempts_cleaned": count}


async def recover_stale_publish_attempts(stale_minutes: int = 15) -> dict:
    """Mark pending/retrying publish attempts as failed if missing from Redis queue."""
    from app.services.publish_queue import get_publishing_queue
    from app.services.publisher import sync_job_publish_status

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(minutes=stale_minutes)
    queue = get_publishing_queue()

    try:
        await queue._ensure_connected()
    except RuntimeError:
        logger.warning("Skipping stale publish attempt recovery: Redis is not connected")
        return {"recovered": 0, "skipped": True}

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(PublishAttempt).where(
                PublishAttempt.status.in_(["pending", "retrying"]),
                PublishAttempt.updated_at < cutoff,
            )
        )
        candidates = result.scalars().all()
        if not candidates:
            return {"recovered": 0}

        recovered = 0
        affected_content_ids = set()
        for attempt in candidates:
            if await queue.is_attempt_queued(attempt.id):
                continue
            attempt.status = "failed"
            attempt.error = attempt.error or "Publish job stalled or missing from queue; please retry."
            attempt.updated_at = now
            affected_content_ids.add(attempt.content_id)
            recovered += 1

        if recovered:
            await db.flush()
            for content_id in affected_content_ids:
                await sync_job_publish_status(db, content_id)
            await db.commit()
            logger.warning("Recovered %d stale publish attempts missing from queue", recovered)

        return {"recovered": recovered}


async def generate_missing_search_vectors(batch_size: int = 100) -> dict:
    """Generate search vectors for images that don't have them."""
    logger.info("Starting search vector generation")

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(ImageModel).where(
                ImageModel.search_vector.is_(None)
            ).limit(batch_size)
        )
        images = result.scalars().all()
        if not images:
            return {"vectors_generated": 0, "pending": 0}

        from app.services.embedding_service import embed_text

        count = 0
        for image in images:
            text_value = " ".join([image.prompt or "", " ".join(image.tags or [])]).strip()
            try:
                image.search_vector = await embed_text(text_value, is_query=False)
                if image.search_vector is not None:
                    count += 1
            except Exception as e:
                logger.warning("Failed to generate embedding for image %s: %s", image.id, e)

        await db.commit()
        logger.info("Generated search vectors for %d/%d images", count, len(images))
        return {"vectors_generated": count, "pending": max(len(images) - count, 0)}


async def reset_daily_quotas() -> dict:
    """Reset daily quotas for all companies (run at midnight UTC)."""
    logger.info("Starting daily quota reset")
    
    from app.models.quota import Quota
    from app.models.company import Company
    
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Quota))
        quotas = result.scalars().all()
        
        today = datetime.now(timezone.utc).date()
        count = 0
        
        for quota in quotas:
            if quota.last_reset_date != today:
                quota.daily_free_requests_used = 0
                quota.daily_spend_usd = 0
                quota.regenerations_used = 0
                quota.last_reset_date = today
                count += 1
        
        await db.commit()
        
        logger.info(f"Reset quotas for {count} companies")
        return {"quotas_reset": count, "date": today.isoformat()}


# Import timedelta
from datetime import timedelta
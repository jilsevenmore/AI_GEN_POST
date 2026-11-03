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


async def generate_missing_search_vectors(batch_size: int = 100) -> dict:
    """Generate search vectors for images that don't have them."""
    logger.info("Starting search vector generation")
    
    async with AsyncSessionLocal() as db:
        # Find images without search vectors
        result = await db.execute(
            select(ImageModel).where(
                ImageModel.search_vector.is_(None)
            ).limit(batch_size)
        )
        images = result.scalars().all()
        
        count = 0
        for image in images:
            # Generate search vector from prompt + tags
            search_text = f"{image.prompt} {' '.join(image.tags)}"
            image.search_vector = search_text  # In production, this would be an embedding
            count += 1
        
        await db.commit()
        
        logger.info(f"Generated search vectors for {count} images")
        return {"vectors_generated": count}


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
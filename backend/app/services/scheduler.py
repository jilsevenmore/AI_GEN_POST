"""Background scheduler for recurring maintenance tasks."""
import logging
from contextlib import asynccontextmanager
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.services.scheduled_jobs import (
    cleanup_old_images,
    cleanup_failed_jobs,
    cleanup_old_publish_attempts,
    generate_missing_search_vectors,
    reset_daily_quotas,
)

logger = logging.getLogger(__name__)

_scheduler: Optional[AsyncIOScheduler] = None


def get_scheduler() -> AsyncIOScheduler:
    """Get or create the scheduler instance."""
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler(timezone="UTC")
    return _scheduler


def start_scheduler() -> None:
    """Start the background scheduler with all recurring jobs."""
    scheduler = get_scheduler()
    
    if scheduler.running:
        logger.warning("Scheduler already running")
        return
    
    # Daily at 2:00 AM UTC - cleanup old images
    scheduler.add_job(
        cleanup_old_images,
        CronTrigger(hour=2, minute=0, timezone="UTC"),
        id="cleanup_old_images",
        name="Cleanup old library images",
        max_instances=1,
        coalesce=True,
    )
    
    # Daily at 3:00 AM UTC - cleanup failed jobs
    scheduler.add_job(
        cleanup_failed_jobs,
        CronTrigger(hour=3, minute=0, timezone="UTC"),
        id="cleanup_failed_jobs",
        name="Cleanup failed/abandoned jobs",
        max_instances=1,
        coalesce=True,
    )
    
    # Weekly on Sunday at 4:00 AM UTC - cleanup old publish attempts
    scheduler.add_job(
        cleanup_old_publish_attempts,
        CronTrigger(day_of_week="sun", hour=4, minute=0, timezone="UTC"),
        id="cleanup_old_publish_attempts",
        name="Cleanup old publish attempts",
        max_instances=1,
        coalesce=True,
    )
    
    # Every 6 hours - generate missing search vectors
    scheduler.add_job(
        generate_missing_search_vectors,
        IntervalTrigger(hours=6, timezone="UTC"),
        id="generate_missing_search_vectors",
        name="Generate missing search vectors",
        max_instances=1,
        coalesce=True,
    )
    
    # Daily at midnight UTC - reset daily quotas
    scheduler.add_job(
        reset_daily_quotas,
        CronTrigger(hour=0, minute=0, timezone="UTC"),
        id="reset_daily_quotas",
        name="Reset daily quotas",
        max_instances=1,
        coalesce=True,
    )
    
    scheduler.start()
    logger.info("Background scheduler started with all recurring jobs")


def stop_scheduler() -> None:
    """Stop the background scheduler."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("Background scheduler stopped")


@asynccontextmanager
async def scheduler_lifespan():
    """Context manager for scheduler lifecycle."""
    start_scheduler()
    try:
        yield
    finally:
        stop_scheduler()
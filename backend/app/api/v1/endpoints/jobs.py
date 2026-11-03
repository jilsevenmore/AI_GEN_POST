from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from typing import List, Optional
from uuid import UUID, uuid4
from datetime import datetime, timezone
from app.db.session import get_db
from app.schemas.common import (
    JobCreate, JobResponse, JobListResponse, JobStatus, JobType, Platform
)
from app.core.dependencies import get_current_user, get_current_company
from app.models.job import Job
from app.models.user import User

router = APIRouter()


@router.post("", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def create_job(
    job_data: JobCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    current_company = Depends(get_current_company),
    db: AsyncSession = Depends(get_db),
):
    """Start a new AI generation job (blog or post)."""
    job = Job(
        company_id=current_company.id,
        user_id=current_user.id,
        type=job_data.type,
        title=job_data.title,
        topic=job_data.topic,
        tone=job_data.tone,
        audience=job_data.audience,
        keywords=job_data.keywords,
        image_description=job_data.image_description,
        platforms=[p.value for p in job_data.platforms],
        use_references=job_data.use_references,
        reference_image_ids=job_data.reference_image_ids,
        status=JobStatus.pending,
        progress=0,
        current_step="queued",
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    
    # TODO: Start background worker (Phase 3)
    # background_tasks.add_task(run_generation_job, job.id)
    
    return JobResponse.model_validate(job)


@router.get("", response_model=JobListResponse)
async def list_jobs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Optional[JobStatus] = Query(None),
    current_company = Depends(get_current_company),
    db: AsyncSession = Depends(get_db),
):
    """List company's generation jobs with pagination."""
    # Build query with company scoping
    query = select(Job).where(Job.company_id == current_company.id)
    
    if status_filter:
        query = query.where(Job.status == status_filter.value)
    
    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # Get paginated results
    query = query.order_by(Job.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    jobs = result.scalars().all()
    
    return JobListResponse(
        jobs=[JobResponse.model_validate(job) for job in jobs],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: UUID,
    current_company = Depends(get_current_company),
    db: AsyncSession = Depends(get_db),
):
    """Get job details by ID (company-scoped)."""
    result = await db.execute(
        select(Job).where(Job.id == job_id, Job.company_id == current_company.id)
    )
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return JobResponse.model_validate(job)


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_job(
    job_id: UUID,
    current_company = Depends(get_current_company),
    db: AsyncSession = Depends(get_db),
):
    """Cancel a pending/running job."""
    result = await db.execute(
        select(Job).where(Job.id == job_id, Job.company_id == current_company.id)
    )
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job.status in [JobStatus.published, JobStatus.failed]:
        raise HTTPException(status_code=400, detail="Cannot cancel completed job")
    
    job.status = JobStatus.failed
    job.error = "Cancelled by user"
    job.updated_at = datetime.now(timezone.utc)
    await db.commit()
    
    return None


# Mock background job simulation (for frontend testing)
@router.post("/{job_id}/simulate-progress", response_model=JobResponse)
async def simulate_job_progress(
    job_id: UUID,
    current_company = Depends(get_current_company),
    db: AsyncSession = Depends(get_db),
):
    """Simulate job progress for frontend testing (REMOVE IN PRODUCTION)."""
    result = await db.execute(
        select(Job).where(Job.id == job_id, Job.company_id == current_company.id)
    )
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    steps = [
        (JobStatus.expanding_prompt, 10, "Expanding prompt..."),
        (JobStatus.writing_text, 30, "Writing content..."),
        (JobStatus.generating_image, 50, "Generating image..."),
        (JobStatus.safety_check, 70, "Running safety checks..."),
        (JobStatus.adapting, 85, "Adapting for platforms..."),
        (JobStatus.awaiting_review, 100, "Ready for review"),
    ]
    
    for status, progress, step in steps:
        job.status = status
        job.progress = progress
        job.current_step = step
        job.updated_at = datetime.now(timezone.utc)
        # In real implementation, this would be streamed via SSE/WebSocket
    
    await db.commit()
    await db.refresh(job)
    
    return JobResponse.model_validate(job)
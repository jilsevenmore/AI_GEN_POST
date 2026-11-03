from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from uuid import UUID, uuid4
from datetime import datetime
from app.db.session import get_db
from app.schemas.common import (
    JobCreate, JobResponse, JobListResponse, JobStatus, JobType, Platform
)

router = APIRouter()

# Mock job store (replace with real DB in Phase 2/3)
MOCK_JOBS = {}


@router.post("", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def create_job(
    job_data: JobCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Start a new AI generation job (blog or post)."""
    # TODO: Implement real job creation with LangGraph background worker
    job_id = uuid4()
    job = JobResponse(
        id=job_id,
        type=job_data.type,
        title=job_data.title,
        topic=job_data.topic,
        tone=job_data.tone,
        audience=job_data.audience,
        keywords=job_data.keywords,
        image_description=job_data.image_description,
        platforms=job_data.platforms,
        status=JobStatus.pending,
        progress=0,
        current_step="queued",
        company_id=uuid4(),  # from auth
        user_id=uuid4(),     # from auth
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    MOCK_JOBS[job_id] = job
    
    # TODO: Start background worker
    # background_tasks.add_task(run_generation_job, job_id)
    
    return job


@router.get("", response_model=JobListResponse)
async def list_jobs(
    page: int = 1,
    page_size: int = 20,
    status_filter: JobStatus = None,
    db: AsyncSession = Depends(get_db),
):
    """List user's generation jobs with pagination."""
    jobs = list(MOCK_JOBS.values())
    if status_filter:
        jobs = [j for j in jobs if j.status == status_filter]
    
    total = len(jobs)
    start = (page - 1) * page_size
    end = start + page_size
    
    return JobListResponse(
        jobs=jobs[start:end],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(job_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get job details by ID."""
    job = MOCK_JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_job(job_id: UUID, db: AsyncSession = Depends(get_db)):
    """Cancel a pending/running job."""
    job = MOCK_JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status in [JobStatus.published, JobStatus.failed]:
        raise HTTPException(status_code=400, detail="Cannot cancel completed job")
    job.status = JobStatus.failed
    job.error = "Cancelled by user"
    job.updated_at = datetime.utcnow()
    return None


# Mock background job simulation (for frontend testing)
@router.post("/{job_id}/simulate-progress", response_model=JobResponse)
async def simulate_job_progress(job_id: UUID, db: AsyncSession = Depends(get_db)):
    """Simulate job progress for frontend testing (REMOVE IN PRODUCTION)."""
    job = MOCK_JOBS.get(job_id)
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
        job.updated_at = datetime.utcnow()
        # In real implementation, this would be streamed via SSE/WebSocket
    
    return job
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Query, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from typing import List, Optional
from uuid import UUID, uuid4
from datetime import datetime, timezone
from app.db.session import get_db
from app.schemas.common import (
    JobCreate, JobResponse, JobListResponse, JobStatus, JobType, Platform,
    SourceFileUploadResponse,
)
from app.core.dependencies import get_current_user, get_current_company
from app.models.job import Job
from app.models.user import User
from app.models.brand_kit import BrandKit
from app.services.ai.graph import run_generation_job
from app.services.ai.state import JobInput, BrandKitData

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
    platform_values = [p.value for p in job_data.platforms]
    # Filter aspect ratios to those supported by all selected platforms (feed/post constraints)
    platform_allowed = {
        "instagram": {"1:1", "4:5", "1.91:1"},
        "facebook": {"1:1", "4:5", "1.91:1"},
        "linkedin": {"1:1", "4:5", "1.91:1"},
    }
    if platform_values:
        allowed = set.intersection(*(set(platform_allowed.get(p, {"1:1","4:5","1.91:1","9:16"})) for p in platform_values)) or {"1:1"}
    else:
        allowed = {"1:1", "4:5", "1.91:1", "9:16"}
    requested_ratios = [str(r.value if hasattr(r, "value") else r) for r in (job_data.aspect_ratios or [])]
    filtered_ratios = [r for r in requested_ratios if r in allowed]

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
        platforms=platform_values,
        use_references=job_data.use_references,
        reference_image_ids=job_data.reference_image_ids,
        source_context_text=job_data.source_context,
        instagram_post_type=job_data.instagram_post_type,
        instagram_cover_image_url=job_data.instagram_cover_image_url,
        aspect_ratios=filtered_ratios,
        status=JobStatus.pending,
        progress=0,
        current_step="queued",
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    
    # Get brand kit for AI generation
    brand_result = await db.execute(
        select(BrandKit).where(BrandKit.company_id == current_company.id)
    )
    brand_kit_model = brand_result.scalar_one_or_none()
    
    if not brand_kit_model:
        # Create default brand kit
        brand_kit_model = BrandKit(company_id=current_company.id, company_name=current_company.name)
        db.add(brand_kit_model)
        await db.commit()
        await db.refresh(brand_kit_model)
    
    # Convert to AI service types
    job_input = JobInput(
        job_id=job.id,
        company_id=current_company.id,
        type=job_data.type.value,  # Convert JobType enum to string literal
        title=job_data.title,
        topic=job_data.topic,
        tone=job_data.tone,
        audience=job_data.audience,
        keywords=job_data.keywords,
        image_description=job_data.image_description,
        platforms=platform_values,
        use_references=job_data.use_references,
        reference_image_ids=job_data.reference_image_ids,
        source_context=job_data.source_context,
        instagram_post_type=job_data.instagram_post_type.value if job_data.instagram_post_type else None,
        instagram_cover_image_url=job_data.instagram_cover_image_url,
        aspect_ratios=filtered_ratios,
    )
    
    brand_kit_data = BrandKitData(
        company_name=brand_kit_model.company_name,
        tagline=brand_kit_model.tagline,
        address=brand_kit_model.address,
        logo_url=str(brand_kit_model.logo_url) if brand_kit_model.logo_url else None,
        primary_color=brand_kit_model.primary_color,
        secondary_color=brand_kit_model.secondary_color,
        tone=brand_kit_model.tone,
        use_openai_only=brand_kit_model.use_openai_only,
    )
    
    # Start background generation (pass job_id only — avoids Pydantic serialization issues)
    from app.db.session import AsyncSessionLocal
    background_tasks.add_task(
        run_generation_job,
        str(job.id),
        str(current_company.id),
        AsyncSessionLocal,
    )
    
    return JobResponse.model_validate(job)


@router.post("/{job_id}/source-files", response_model=SourceFileUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_source_file(
    job_id: UUID,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    current_company = Depends(get_current_company),
    db: AsyncSession = Depends(get_db),
):
    """Upload a source document (.md / .txt) to a job.

    The file is stored (Cloudinary) and its text is extracted and saved on the job
    as generation context. The AI uses this context when writing the post/blog.
    """
    # Validate job exists and belongs to the current company
    result = await db.execute(
        select(Job).where(Job.id == job_id, Job.company_id == current_company.id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # --- File validation ---
    MAX_FILE_BYTES = 5 * 1024 * 1024  # 5 MB
    ALLOWED_EXTENSIONS = {".md", ".markdown", ".txt"}
    ALLOWED_MIME_PREFIXES = ("text/", "application/markdown")

    filename = file.filename or "source.md"
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if not any(filename.lower().endswith(e) for e in ALLOWED_EXTENSIONS):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}."
        )

    if file.content_type and not any(
        file.content_type.startswith(p) for p in ALLOWED_MIME_PREFIXES
    ):
        # Be lenient: some browsers send application/octet-stream for .md
        if file.content_type not in ("application/octet-stream",):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid content type '{file.content_type}'. Expected a text file."
            )

    # Read file bytes
    contents = await file.read()
    if len(contents) > MAX_FILE_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"File too large ({len(contents)} bytes). Max {MAX_FILE_BYTES} bytes."
        )
    if len(contents) == 0:
        raise HTTPException(status_code=400, detail="Empty file.")

    # Decode text (UTF-8)
    try:
        source_text = contents.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=400,
            detail="File is not valid UTF-8 text. Please upload a .md or .txt file."
        )

    # --- Storage: upload to Cloudinary (raw), mirroring the brand logo pattern ---
    # TODO: Wire real Cloudinary upload when CLOUDINARY credentials are configured.
    # For now, store a placeholder URL and the extracted text on the job.
    import uuid as _uuid
    object_name = f"source_files/{current_company.id}/{job_id}/{_uuid.uuid4().hex}_{filename}"
    file_url = f"https://res.cloudinary.com/demo/raw/upload/v1/source_files/{object_name}"

    # --- Persist to job ---
    job.source_file_name = filename
    job.source_file_url = file_url
    job.source_context_text = source_text
    job.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(job)

    preview = source_text[:500] + ("…" if len(source_text) > 500 else "")

    return SourceFileUploadResponse(
        file_id=job.id,
        file_name=filename,
        file_url=file_url,
        size_bytes=len(contents),
        extracted_text_preview=preview,
        context_stored=bool(source_text.strip()),
    )


@router.get("", response_model=JobListResponse)
async def list_jobs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Optional[JobStatus] = Query(None),
    current_company = Depends(get_current_company),
    db: AsyncSession = Depends(get_db),
):
    """List company's generation jobs with pagination."""
    query = select(Job).where(Job.company_id == current_company.id)
    
    if status_filter:
        query = query.where(Job.status == status_filter.value)
    
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
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


# Keep simulate-progress for testing (can remove later)
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
    
    await db.commit()
    await db.refresh(job)
    
    return JobResponse.model_validate(job)
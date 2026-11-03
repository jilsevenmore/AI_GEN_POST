from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, and_
from sqlalchemy.orm import selectinload
from typing import List, Optional
from uuid import UUID, uuid4
from datetime import datetime, timezone
from app.db.session import get_db
from app.schemas.common import (
    LibraryImageResponse, LibrarySearchRequest, LibrarySearchResponse,
    SaveToLibraryRequest, ImageTag, ImageAspectRatio
)
from app.core.dependencies import get_current_company
from app.models.image import Image
from app.models.content import Content

router = APIRouter()


@router.get("/search", response_model=LibrarySearchResponse)
async def search_library(
    query: Optional[str] = Query(None),
    tags: List[str] = Query(default=[]),
    aspect_ratio: Optional[ImageAspectRatio] = Query(None),
    is_global: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_company = Depends(get_current_company),
    db: AsyncSession = Depends(get_db),
):
    """Search image library with filters."""
    # Build query - show own images + global images
    base_query = select(Image).where(
        or_(
            Image.company_id == current_company.id,
            Image.is_global == True
        )
    )
    
    if query:
        # Simple text search on prompt and tags
        search_term = f"%{query.lower()}%"
        base_query = base_query.where(
            or_(
                Image.prompt.ilike(search_term),
                Image.tags.any(query.lower())  # For array columns
            )
        )
    
    if tags:
        # All tags must match
        for tag in tags:
            base_query = base_query.where(Image.tags.any(tag))
    
    if aspect_ratio:
        base_query = base_query.where(Image.aspect_ratio == aspect_ratio.value)
    
    if is_global is not None:
        base_query = base_query.where(Image.is_global == is_global)
    
    # Get total count
    count_query = select(func.count()).select_from(base_query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # Get paginated results
    query = base_query.order_by(Image.approved_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    images = result.scalars().all()
    
    # Generate suggested tags from results
    all_tags = {}
    for img in images:
        for tag in img.tags:
            all_tags[tag] = all_tags.get(tag, 0) + 1
    suggested = [
        ImageTag(name=k, count=v) 
        for k, v in sorted(all_tags.items(), key=lambda x: -x[1])[:10]
    ]
    
    return LibrarySearchResponse(
        images=[LibraryImageResponse.model_validate(img) for img in images],
        total=total,
        page=page,
        page_size=page_size,
        suggested_tags=suggested,
    )


@router.get("/{image_id}", response_model=LibraryImageResponse)
async def get_library_image(
    image_id: UUID,
    current_company = Depends(get_current_company),
    db: AsyncSession = Depends(get_db),
):
    """Get a single library image by ID (own or global)."""
    result = await db.execute(
        select(Image).where(
            Image.id == image_id,
            or_(
                Image.company_id == current_company.id,
                Image.is_global == True
            )
        )
    )
    image = result.scalar_one_or_none()
    
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    
    return LibraryImageResponse.model_validate(image)


@router.post("", response_model=LibraryImageResponse, status_code=status.HTTP_201_CREATED)
async def save_to_library(
    request: SaveToLibraryRequest,
    current_company = Depends(get_current_company),
    db: AsyncSession = Depends(get_db),
):
    """Save an approved image to the library."""
    # Verify content exists and belongs to company
    content_result = await db.execute(
        select(Content).where(
            Content.id == request.content_id,
            Content.company_id == current_company.id
        )
    )
    content = content_result.scalar_one_or_none()
    
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")
    
    # Find the image variant
    image_variant = None
    for variant in content.image_variants:
        if variant.get("id") == str(request.image_id):
            image_variant = variant
            break
    
    if not image_variant:
        raise HTTPException(status_code=404, detail="Image variant not found in content")
    
    # Create library image
    image = Image(
        company_id=current_company.id,
        content_id=request.content_id,
        url=image_variant.get("url"),
        thumbnail_url=image_variant.get("thumbnail_url"),
        prompt=image_variant.get("prompt_used", ""),
        tags=request.tags,
        aspect_ratio=image_variant.get("aspect_ratio", "1:1"),
        width=image_variant.get("width", 1024),
        height=image_variant.get("height", 1024),
        is_global=request.is_global,
        approved_at=datetime.now(timezone.utc),
    )
    db.add(image)
    await db.commit()
    await db.refresh(image)
    
    return LibraryImageResponse.model_validate(image)


@router.patch("/{image_id}/tags", response_model=LibraryImageResponse)
async def update_image_tags(
    image_id: UUID,
    tags: List[str],
    current_company = Depends(get_current_company),
    db: AsyncSession = Depends(get_db),
):
    """Update tags for a library image (own images only)."""
    result = await db.execute(
        select(Image).where(
            Image.id == image_id,
            Image.company_id == current_company.id  # Only own images
        )
    )
    image = result.scalar_one_or_none()
    
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    
    image.tags = tags
    image.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(image)
    
    return LibraryImageResponse.model_validate(image)


@router.delete("/{image_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_library_image(
    image_id: UUID,
    current_company = Depends(get_current_company),
    db: AsyncSession = Depends(get_db),
):
    """Delete an image from the library (own images only)."""
    result = await db.execute(
        select(Image).where(
            Image.id == image_id,
            Image.company_id == current_company.id  # Only own images
        )
    )
    image = result.scalar_one_or_none()
    
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    
    await db.delete(image)
    await db.commit()
    
    return None


@router.get("/tags/popular", response_model=List[ImageTag])
async def get_popular_tags(
    limit: int = Query(20, ge=1, le=100),
    current_company = Depends(get_current_company),
    db: AsyncSession = Depends(get_db),
):
    """Get most popular tags across the library (own + global)."""
    result = await db.execute(
        select(Image.tags).where(
            or_(
                Image.company_id == current_company.id,
                Image.is_global == True
            )
        )
    )
    all_tag_arrays = result.scalars().all()
    
    all_tags = {}
    for tag_array in all_tag_arrays:
        for tag in tag_array:
            all_tags[tag] = all_tags.get(tag, 0) + 1
    
    return [
        ImageTag(name=k, count=v) 
        for k, v in sorted(all_tags.items(), key=lambda x: -x[1])[:limit]
    ]
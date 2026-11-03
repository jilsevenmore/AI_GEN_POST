from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from uuid import UUID, uuid4
from datetime import datetime
from app.db.session import get_db
from app.schemas.common import (
    LibraryImageResponse, LibrarySearchRequest, LibrarySearchResponse,
    SaveToLibraryRequest, ImageTag, ImageAspectRatio
)

router = APIRouter()

# Mock library store
MOCK_LIBRARY_IMAGES = {}


@router.get("/search", response_model=LibrarySearchResponse)
async def search_library(
    query: Optional[str] = Query(None),
    tags: List[str] = Query(default=[]),
    aspect_ratio: Optional[ImageAspectRatio] = Query(None),
    is_global: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Search image library with filters."""
    # TODO: Implement real vector search with pgvector
    images = list(MOCK_LIBRARY_IMAGES.values())
    
    # Apply filters
    if query:
        images = [i for i in images if query.lower() in i.prompt.lower() or any(query.lower() in t.lower() for t in i.tags)]
    if tags:
        images = [i for i in images if all(t in i.tags for t in tags)]
    if aspect_ratio:
        images = [i for i in images if i.aspect_ratio == aspect_ratio]
    if is_global is not None:
        images = [i for i in images if i.is_global == is_global]
    
    total = len(images)
    start = (page - 1) * page_size
    end = start + page_size
    
    # Generate suggested tags
    all_tags = {}
    for img in images:
        for tag in img.tags:
            all_tags[tag] = all_tags.get(tag, 0) + 1
    suggested = [ImageTag(name=k, count=v) for k, v in sorted(all_tags.items(), key=lambda x: -x[1])[:10]]
    
    return LibrarySearchResponse(
        images=images[start:end],
        total=total,
        page=page,
        page_size=page_size,
        suggested_tags=suggested,
    )


@router.get("/{image_id}", response_model=LibraryImageResponse)
async def get_library_image(image_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get a single library image by ID."""
    image = MOCK_LIBRARY_IMAGES.get(image_id)
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    return image


@router.post("", response_model=LibraryImageResponse, status_code=status.HTTP_201_CREATED)
async def save_to_library(
    request: SaveToLibraryRequest,
    db: AsyncSession = Depends(get_db),
):
    """Save an approved image to the library."""
    # TODO: Implement real save with Cloudinary upload, vector embedding
    image_id = uuid4()
    image = LibraryImageResponse(
        id=image_id,
        url=f"https://res.cloudinary.com/demo/image/upload/v1/library/{image_id}.jpg",
        thumbnail_url=f"https://res.cloudinary.com/demo/image/upload/c_thumb,w_200,h_200/v1/library/{image_id}.jpg",
        prompt="Saved from content generation",
        tags=request.tags,
        aspect_ratio=ImageAspectRatio._1_1,
        width=1024,
        height=1024,
        is_global=request.is_global,
        company_id=uuid4(),  # from auth
        approved_at=datetime.utcnow(),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    MOCK_LIBRARY_IMAGES[image_id] = image
    return image


@router.patch("/{image_id}/tags", response_model=LibraryImageResponse)
async def update_image_tags(
    image_id: UUID,
    tags: List[str],
    db: AsyncSession = Depends(get_db),
):
    """Update tags for a library image."""
    image = MOCK_LIBRARY_IMAGES.get(image_id)
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    image.tags = tags
    image.updated_at = datetime.utcnow()
    return image


@router.delete("/{image_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_library_image(image_id: UUID, db: AsyncSession = Depends(get_db)):
    """Delete an image from the library (own images only)."""
    if image_id not in MOCK_LIBRARY_IMAGES:
        raise HTTPException(status_code=404, detail="Image not found")
    del MOCK_LIBRARY_IMAGES[image_id]
    return None


@router.get("/tags/popular", response_model=List[ImageTag])
async def get_popular_tags(limit: int = 20, db: AsyncSession = Depends(get_db)):
    """Get most popular tags across the library."""
    all_tags = {}
    for img in MOCK_LIBRARY_IMAGES.values():
        for tag in img.tags:
            all_tags[tag] = all_tags.get(tag, 0) + 1
    return [ImageTag(name=k, count=v) for k, v in sorted(all_tags.items(), key=lambda x: -x[1])[:limit]]


# Seed mock data for frontend testing
def _seed_mock_library():
    """Seed mock library images for frontend development."""
    festivals = ["diwali", "christmas", "new year", "holi", "eid", "thanksgiving", "halloween"]
    for i, festival in enumerate(festivals):
        img_id = uuid4()
        MOCK_LIBRARY_IMAGES[img_id] = LibraryImageResponse(
            id=img_id,
            url=f"https://picsum.photos/seed/festival-{festival}/1024/1024",
            thumbnail_url=f"https://picsum.photos/seed/festival-{festival}/200/200",
            prompt=f"Festive {festival} celebration image",
            tags=[festival, "festival", "celebration"],
            aspect_ratio=ImageAspectRatio._1_1,
            width=1024,
            height=1024,
            is_global=True,
            company_id=uuid4(),
            approved_at=datetime.utcnow(),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

_seed_mock_library()
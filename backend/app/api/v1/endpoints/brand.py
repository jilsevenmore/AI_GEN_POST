from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from datetime import datetime, timezone
from typing import Optional
from app.db.session import get_db
from app.schemas.common import (
    BrandKitCreate, BrandKitUpdate, BrandKitResponse
)
from app.core.dependencies import get_current_company
from app.models.brand_kit import BrandKit
from app.services.brand_kit import composite_brand_elements, BrandKitService

router = APIRouter()


@router.get("", response_model=BrandKitResponse)
async def get_brand_kit(
    current_company = Depends(get_current_company),
    db: AsyncSession = Depends(get_db),
):
    """Get the current company's brand kit."""
    result = await db.execute(
        select(BrandKit).where(BrandKit.company_id == current_company.id)
    )
    brand_kit = result.scalar_one_or_none()
    
    if not brand_kit:
        # Create default brand kit
        brand_kit = BrandKit(
            company_id=current_company.id,
            company_name=current_company.name,
        )
        db.add(brand_kit)
        await db.commit()
        await db.refresh(brand_kit)
    
    return BrandKitResponse.model_validate(brand_kit)


@router.put("", response_model=BrandKitResponse)
async def upsert_brand_kit(
    brand_data: BrandKitCreate,
    current_company = Depends(get_current_company),
    db: AsyncSession = Depends(get_db),
):
    """Create or update the company's brand kit."""
    result = await db.execute(
        select(BrandKit).where(BrandKit.company_id == current_company.id)
    )
    brand_kit = result.scalar_one_or_none()
    
    if brand_kit:
        # Update existing
        update_data = brand_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(brand_kit, field, value)
        brand_kit.updated_at = datetime.now(timezone.utc)
    else:
        # Create new
        brand_kit = BrandKit(
            company_id=current_company.id,
            **brand_data.model_dump(),
        )
        db.add(brand_kit)
    
    await db.commit()
    await db.refresh(brand_kit)
    
    return BrandKitResponse.model_validate(brand_kit)


@router.patch("", response_model=BrandKitResponse)
async def update_brand_kit(
    brand_data: BrandKitUpdate,
    current_company = Depends(get_current_company),
    db: AsyncSession = Depends(get_db),
):
    """Partially update the brand kit."""
    result = await db.execute(
        select(BrandKit).where(BrandKit.company_id == current_company.id)
    )
    brand_kit = result.scalar_one_or_none()
    
    if not brand_kit:
        raise HTTPException(status_code=404, detail="Brand kit not found. Create one first.")
    
    update_data = brand_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(brand_kit, field, value)
    
    brand_kit.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(brand_kit)
    
    return BrandKitResponse.model_validate(brand_kit)


@router.post("/logo", response_model=BrandKitResponse)
async def upload_logo(
    file: UploadFile = File(...),
    current_company = Depends(get_current_company),
    db: AsyncSession = Depends(get_db),
):
    """Upload company logo (uploads to Cloudinary, returns URL)."""
    # TODO: Implement real Cloudinary upload (Phase 5)
    result = await db.execute(
        select(BrandKit).where(BrandKit.company_id == current_company.id)
    )
    brand_kit = result.scalar_one_or_none()
    
    if not brand_kit:
        raise HTTPException(status_code=404, detail="Brand kit not found. Create one first.")
    
    # Mock: return a placeholder URL
    logo_url = f"https://res.cloudinary.com/demo/image/upload/v1/logos/{current_company.id}/{file.filename}"
    
    brand_kit.logo_url = logo_url
    brand_kit.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(brand_kit)
    
    return BrandKitResponse.model_validate(brand_kit)


@router.delete("/logo", response_model=BrandKitResponse)
async def delete_logo(
    current_company = Depends(get_current_company),
    db: AsyncSession = Depends(get_db),
):
    """Remove company logo."""
    result = await db.execute(
        select(BrandKit).where(BrandKit.company_id == current_company.id)
    )
    brand_kit = result.scalar_one_or_none()
    
    if not brand_kit:
        raise HTTPException(status_code=404, detail="Brand kit not found")
    
    brand_kit.logo_url = None
    brand_kit.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(brand_kit)
    
    return BrandKitResponse.model_validate(brand_kit)


@router.post("/test-composite", response_model=dict)
async def test_composite(
    image_url: str,
    aspect_ratio: str = "1:1",
    current_company = Depends(get_current_company),
    db: AsyncSession = Depends(get_db),
):
    """
    Test brand compositing on an image URL.
    
    Downloads the image, composites brand elements, returns base64 result.
    """
    import base64
    import httpx
    
    # Get brand kit
    brand_service = BrandKitService(db)
    brand_kit = await brand_service.get_or_create_brand_kit(current_company.id)
    
    # Download image
    async with httpx.AsyncClient() as client:
        response = await client.get(image_url, timeout=10.0)
        response.raise_for_status()
        image_bytes = response.content
    
    # Composite brand elements
    composited_bytes = composite_brand_elements(
        image_bytes=image_bytes,
        brand_kit=brand_kit,
        aspect_ratio=aspect_ratio,
    )
    
    # Return as base64
    b64 = base64.b64encode(composited_bytes).decode()
    return {
        "image_base64": f"data:image/png;base64,{b64}",
        "brand_elements_applied": {
            "logo": bool(brand_kit.logo_url),
            "address": bool(brand_kit.address),
            "company_name": bool(brand_kit.company_name),
        }
    }
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID, uuid4
from datetime import datetime
from app.db.session import get_db
from app.schemas.common import (
    BrandKitCreate, BrandKitUpdate, BrandKitResponse
)

router = APIRouter()

# Mock brand kit store (one per company)
MOCK_BRAND_KITS = {}


@router.get("", response_model=BrandKitResponse)
async def get_brand_kit(db: AsyncSession = Depends(get_db)):
    """Get the current company's brand kit."""
    # TODO: Get company_id from auth
    company_id = uuid4()  # mock
    
    if company_id not in MOCK_BRAND_KITS:
        # Return default empty brand kit
        return BrandKitResponse(
            id=uuid4(),
            company_id=company_id,
            company_name="My Company",
            tagline=None,
            address=None,
            logo_url=None,
            primary_color="#2563EB",
            secondary_color="#7C3AED",
            tone="professional",
            use_openai_only=False,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
    
    return MOCK_BRAND_KITS[company_id]


@router.put("", response_model=BrandKitResponse)
async def upsert_brand_kit(
    brand_data: BrandKitCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create or update the company's brand kit."""
    company_id = uuid4()  # from auth
    
    brand = BrandKitResponse(
        id=MOCK_BRAND_KITS.get(company_id, {}).id if company_id in MOCK_BRAND_KITS else uuid4(),
        company_id=company_id,
        **brand_data.model_dump(),
        created_at=MOCK_BRAND_KITS.get(company_id, {}).created_at if company_id in MOCK_BRAND_KITS else datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    MOCK_BRAND_KITS[company_id] = brand
    return brand


@router.patch("", response_model=BrandKitResponse)
async def update_brand_kit(
    brand_data: BrandKitUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Partially update the brand kit."""
    company_id = uuid4()  # from auth
    
    if company_id not in MOCK_BRAND_KITS:
        raise HTTPException(status_code=404, detail="Brand kit not found. Create one first.")
    
    existing = MOCK_BRAND_KITS[company_id]
    update_data = brand_data.model_dump(exclude_unset=True)
    
    for field, value in update_data.items():
        setattr(existing, field, value)
    
    existing.updated_at = datetime.utcnow()
    return existing


@router.post("/logo", response_model=BrandKitResponse)
async def upload_logo(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Upload company logo (uploads to Cloudinary, returns URL)."""
    # TODO: Implement real Cloudinary upload
    company_id = uuid4()  # from auth
    
    if company_id not in MOCK_BRAND_KITS:
        raise HTTPException(status_code=404, detail="Brand kit not found. Create one first.")
    
    # Mock: return a placeholder URL
    logo_url = f"https://res.cloudinary.com/demo/image/upload/v1/logos/{company_id}/{file.filename}"
    
    existing = MOCK_BRAND_KITS[company_id]
    existing.logo_url = logo_url
    existing.updated_at = datetime.utcnow()
    
    return existing


@router.delete("/logo", response_model=BrandKitResponse)
async def delete_logo(db: AsyncSession = Depends(get_db)):
    """Remove company logo."""
    company_id = uuid4()  # from auth
    
    if company_id not in MOCK_BRAND_KITS:
        raise HTTPException(status_code=404, detail="Brand kit not found")
    
    existing = MOCK_BRAND_KITS[company_id]
    existing.logo_url = None
    existing.updated_at = datetime.utcnow()
    
    return existing
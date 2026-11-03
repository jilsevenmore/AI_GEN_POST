"""Brand Kit service with logo/address compositing via Pillow."""
import logging
import io
from typing import Optional, Tuple
from uuid import UUID
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.brand_kit import BrandKit
from app.models.company import Company

logger = logging.getLogger(__name__)


class BrandKitService:
    """Service for managing brand kits and compositing logos/addresses."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_or_create_brand_kit(self, company_id: UUID) -> BrandKit:
        """Get existing brand kit or create default."""
        result = await self.db.execute(
            select(BrandKit).where(BrandKit.company_id == company_id)
        )
        brand_kit = result.scalar_one_or_none()
        
        if not brand_kit:
            # Get company name for default
            company_result = await self.db.execute(
                select(Company).where(Company.id == company_id)
            )
            company = company_result.scalar_one()
            
            brand_kit = BrandKit(
                company_id=company_id,
                company_name=company.name,
            )
            self.db.add(brand_kit)
            await self.db.commit()
            await self.db.refresh(brand_kit)
        
        return brand_kit
    
    async def update_brand_kit(
        self, 
        company_id: UUID, 
        **kwargs
    ) -> BrandKit:
        """Update brand kit fields."""
        brand_kit = await self.get_or_create_brand_kit(company_id)
        
        for field, value in kwargs.items():
            if hasattr(brand_kit, field) and value is not None:
                setattr(brand_kit, field, value)
        
        brand_kit.updated_at = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(brand_kit)
        
        return brand_kit
    
    async def upload_logo(
        self, 
        company_id: UUID, 
        file_content: bytes,
        filename: str
    ) -> str:
        """
        Upload logo to Cloudinary and return URL.
        
        Note: Actual Cloudinary upload would happen here.
        For now, returns placeholder.
        """
        brand_kit = await self.get_or_create_brand_kit(company_id)
        
        # TODO: Implement actual Cloudinary upload
        # from cloudinary.uploader import upload
        # result = upload(file_content, folder=f"brand_kits/{company_id}/logos", public_id=f"logo_{uuid.uuid4().hex[:8]}")
        # logo_url = result["secure_url"]
        
        # Placeholder
        logo_url = f"https://res.cloudinary.com/demo/image/upload/v1/brand_kits/{company_id}/logos/{filename}"
        
        brand_kit.logo_url = logo_url
        brand_kit.updated_at = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(brand_kit)
        
        return logo_url
    
    async def remove_logo(self, company_id: UUID) -> BrandKit:
        """Remove logo from brand kit."""
        brand_kit = await self.get_or_create_brand_kit(company_id)
        brand_kit.logo_url = None
        brand_kit.updated_at = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(brand_kit)
        return brand_kit


# Pillow-based image compositing
def composite_brand_elements(
    image_bytes: bytes,
    brand_kit: BrandKit,
    aspect_ratio: str = "1:1",
) -> bytes:
    """
    Composite logo and address onto generated image using Pillow.
    
    This runs AFTER Sunburst generates the base image, ensuring
    small text (logo, address) is crisp and accurate.
    
    Args:
        image_bytes: Raw bytes of the generated image
        brand_kit: BrandKit with logo_url, address, colors
        aspect_ratio: Image aspect ratio for positioning
        
    Returns:
        Composited image bytes
    """
    try:
        from PIL import Image, ImageDraw, ImageFont, ImageOps
    except ImportError:
        logger.warning("Pillow not installed, skipping brand compositing")
        return image_bytes
    
    # Open base image
    base_img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    width, height = base_img.size
    
    # Create overlay for brand elements
    overlay = Image.new("RGBA", base_img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    
    # Calculate positions based on aspect ratio
    positions = _calculate_positions(width, height, aspect_ratio)
    
    # 1. Add logo (top-right or bottom-right)
    if brand_kit.logo_url:
        logo_img = _load_logo(brand_kit.logo_url, max_size=(width // 5, height // 5))
        if logo_img:
            logo_pos = positions["logo"]
            overlay.paste(logo_img, logo_pos, logo_img if logo_img.mode == "RGBA" else None)
    
    # 2. Add address (bottom-left or bottom-center)
    if brand_kit.address:
        address_text = _format_address(brand_kit.address)
        font_size = max(12, min(width, height) // 50)
        font = _get_font(font_size)
        
        # Calculate text position
        bbox = draw.textbbox((0, 0), address_text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        address_pos = positions["address"]
        # Adjust for text size
        x = address_pos[0]
        y = address_pos[1] - text_height - 10  # 10px padding from bottom
        
        # Add background for readability
        padding = 8
        bg_coords = [
            x - padding, y - padding,
            x + text_width + padding, y + text_height + padding
        ]
        draw.rounded_rectangle(bg_coords, radius=6, fill=(0, 0, 0, 180))
        
        # Draw text
        draw.text((x, y), address_text, font=font, fill=(255, 255, 255, 255))
    
    # 3. Add company name (optional, top-left)
    if brand_kit.company_name and width > 800:
        font_size = max(14, min(width, height) // 45)
        font = _get_font(font_size, bold=True)
        name_pos = positions["company_name"]
        
        # Add subtle background
        bbox = draw.textbbox((0, 0), brand_kit.company_name, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        padding = 8
        bg_coords = [
            name_pos[0] - padding, name_pos[1] - padding,
            name_pos[0] + text_width + padding, name_pos[1] + text_height + padding
        ]
        draw.rounded_rectangle(bg_coords, radius=6, fill=(0, 0, 0, 150))
        
        draw.text(name_pos, brand_kit.company_name, font=font, fill=(255, 255, 255, 255))
    
    # Composite overlay onto base
    result = Image.alpha_composite(base_img, overlay)
    
    # Convert back to bytes
    output = io.BytesIO()
    result.save(output, format="PNG")
    return output.getvalue()


def _calculate_positions(width: int, height: int, aspect_ratio: str) -> dict:
    """Calculate brand element positions based on image dimensions and aspect ratio."""
    margin = max(20, min(width, height) // 40)
    
    if aspect_ratio in ["9:16", "4:5"]:  # Portrait - more vertical space
        return {
            "logo": (width - margin - 100, margin),  # top-right
            "address": (margin, height - margin),  # bottom-left
            "company_name": (margin, margin),  # top-left
        }
    elif aspect_ratio == "1.91:1":  # Landscape
        return {
            "logo": (width - margin - 120, margin),
            "address": (margin, height - margin),
            "company_name": (margin, margin),
        }
    else:  # Square (1:1) - default
        return {
            "logo": (width - margin - 100, margin),
            "address": (margin, height - margin),
            "company_name": (margin, margin),
        }


def _load_logo(logo_url: str, max_size: Tuple[int, int]) -> Optional["Image.Image"]:
    """Load logo from URL or local path."""
    try:
        from PIL import Image
        import requests
        
        # For local development, try to load from URL
        if logo_url.startswith("http"):
            response = requests.get(logo_url, timeout=5)
            if response.status_code == 200:
                img = Image.open(io.BytesIO(response.content)).convert("RGBA")
                img.thumbnail(max_size, Image.Resampling.LANCZOS)
                return img
        else:
            # Local file path
            img = Image.open(logo_url).convert("RGBA")
            img.thumbnail(max_size, Image.Resampling.LANCZOS)
            return img
    except Exception as e:
        logger.warning(f"Failed to load logo: {e}")
    
    return None


def _format_address(address: str) -> str:
    """Format address for display (shorten if too long)."""
    if len(address) <= 60:
        return address
    # Try to keep city, state, zip
    parts = address.split(", ")
    if len(parts) >= 3:
        return ", ".join(parts[-3:])
    return address[:57] + "..."


def _get_font(size: int, bold: bool = False) -> "ImageFont.FreeTypeFont":
    """Get font for text rendering."""
    try:
        from PIL import ImageFont
        # Try to use a nice font, fall back to default
        font_paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
            "C:/Windows/Fonts/arial.ttf",
        ]
        
        for path in font_paths:
            try:
                if bold and "Bold" not in path:
                    bold_path = path.replace(".ttf", "-Bold.ttf").replace(".ttc", "-Bold.ttc")
                    return ImageFont.truetype(bold_path, size)
                return ImageFont.truetype(path, size)
            except:
                continue
    except:
        pass
    
    # Ultimate fallback
    from PIL import ImageFont
    return ImageFont.load_default()
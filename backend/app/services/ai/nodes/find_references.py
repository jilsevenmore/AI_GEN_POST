"""Node 2: Find reference images from library for style/subject/logo."""
import logging
from typing import List
from uuid import UUID
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.ai.state import GenerationState, ReferenceImage
from app.models.image import Image as ImageModel

logger = logging.getLogger(__name__)


async def find_references_node(state: GenerationState, db: AsyncSession) -> GenerationState:
    """Find relevant reference images from the library."""
    job = state.job_input
    
    if not job.use_references:
        state.current_step = "generating"
        state.progress = 30
        return state
    
    references: List[ReferenceImage] = []
    
    # 1. Use explicitly provided reference IDs
    if job.reference_image_ids:
        result = await db.execute(
            select(ImageModel).where(
                ImageModel.id.in_(job.reference_image_ids),
                or_(
                    ImageModel.company_id == job.company_id,
                    ImageModel.is_global == True
                )
            )
        )
        explicit_images = result.scalars().all()
        for img in explicit_images:
            references.append(ReferenceImage(
                id=img.id,
                url=img.url,
                prompt=img.prompt,
                tags=img.tags,
                role="subject",  # Default role for explicit refs
            ))
    
    # 2. Search by keywords/tags if we need more
    if len(references) < 3:
        search_terms = []
        if job.keywords:
            search_terms.extend(job.keywords[:3])
        if job.topic:
            # Extract key terms from topic
            search_terms.extend(job.topic.split()[:5])
        
        for term in search_terms[:5]:
            if len(references) >= 4:
                break
                
            result = await db.execute(
                select(ImageModel).where(
                    or_(
                        ImageModel.tags.any(term.lower()),
                        ImageModel.prompt.ilike(f"%{term}%")
                    ),
                    or_(
                        ImageModel.company_id == job.company_id,
                        ImageModel.is_global == True
                    )
                ).order_by(ImageModel.approved_at.desc()).limit(2)
            )
            found = result.scalars().all()
            for img in found:
                if img.id not in [r.id for r in references]:
                    references.append(ReferenceImage(
                        id=img.id,
                        url=img.url,
                        prompt=img.prompt,
                        tags=img.tags,
                        role="style",
                    ))
    
    # 3. Add logo as reference if brand has one
    if state.brand_kit.logo_url and len(references) < 4:
        # Create a pseudo-reference for the logo
        logo_ref = ReferenceImage(
            id=UUID("00000000-0000-0000-0000-000000000001"),  # Special ID for logo
            url=state.brand_kit.logo_url,
            prompt="Company logo",
            tags=["logo", "brand"],
            role="logo",
        )
        references.append(logo_ref)
    
    # Limit to max 4 references (Sunburst limit, but we use fewer for quality)
    state.reference_images = references[:4]
    state.current_step = "generating"
    state.progress = 35
    
    logger.info(f"Found {len(references)} reference images for job {job.job_id}")
    return state
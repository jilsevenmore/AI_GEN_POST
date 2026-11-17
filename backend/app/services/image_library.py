"""Image Library service with pgvector search and reference management."""
import logging
import uuid
from typing import List, Optional, Tuple
from uuid import UUID
from datetime import datetime, timezone, timedelta

from sqlalchemy import select, func, or_, and_, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from app.models.image import Image as ImageModel
from app.models.content import Content
from app.models.company import Company
from app.services.ai.state import ReferenceImage, ImageBrief
from app.core.config import get_settings
from app.services.embedding_service import embed_text

logger = logging.getLogger(__name__)
settings = get_settings()


class ImageLibraryService:
    """Service for managing the image library with vector search."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def save_approved_image(
        self,
        content_id: UUID,
        image_id: UUID,
        tags: List[str],
        is_global: bool = False,
        company_id: UUID = None,
    ) -> ImageModel:
        """Save an approved image to the library."""
        # Get the image variant from content
        content_result = await self.db.execute(
            select(Content).where(Content.id == content_id)
        )
        content = content_result.scalar_one_or_none()
        
        if not content:
            raise ValueError("Content not found")
        
        # Find the specific image variant
        image_variant = None
        for variant in content.image_variants:
            if variant.get("id") == str(image_id):
                image_variant = variant
                break
        
        if not image_variant:
            raise ValueError("Image variant not found in content")
        
        # Create library image
        library_image = ImageModel(
            company_id=company_id,
            content_id=content_id,
            url=image_variant.get("url"),
            thumbnail_url=image_variant.get("thumbnail_url"),
            prompt=image_variant.get("prompt_used", ""),
            tags=tags,
            aspect_ratio=image_variant.get("aspect_ratio", "1:1"),
            width=image_variant.get("width", 1024),
            height=image_variant.get("height", 1024),
            is_global=is_global,
            approved_at=datetime.now(timezone.utc),
        )
        
        # Generate and store search embedding (best-effort)
        search_text = self._generate_search_text(library_image.prompt, tags)
        try:
            library_image.search_vector = await embed_text(search_text, is_query=False)
        except Exception as e:
            logger.warning("Failed to generate embedding for image %s: %s", image_id, e)
            library_image.search_vector = None

        self.db.add(library_image)
        await self.db.commit()
        await self.db.refresh(library_image)

        return library_image
    
    def _generate_search_text(self, prompt: str, tags: List[str]) -> str:
        """Generate combined text for vector embedding input."""
        parts = [prompt or ""]
        parts.extend(tags or [])
        return " ".join(p for p in parts if p).strip()
    
    async def search_library(
        self,
        company_id: UUID,
        query: Optional[str] = None,
        tags: Optional[List[str]] = None,
        aspect_ratio: Optional[str] = None,
        is_global: Optional[bool] = None,
        page: int = 1,
        page_size: int = 20,
        use_vector_search: bool = True,
    ) -> Tuple[List[ImageModel], int]:
        """Search library with filters and optional vector similarity."""
        
        # Base query: own images + global images
        base_query = select(ImageModel).where(
            or_(
                ImageModel.company_id == company_id,
                ImageModel.is_global == True
            )
        )
        
        # Apply filters
        order_by_similarity = None
        if tags:
            for tag in tags:
                base_query = base_query.where(ImageModel.tags.op('@>')([tag]))

        if aspect_ratio:
            base_query = base_query.where(ImageModel.aspect_ratio == aspect_ratio)

        if is_global is not None:
            base_query = base_query.where(ImageModel.is_global == is_global)

        if query and use_vector_search:
            try:
                query_embedding = await embed_text(query, is_query=True)
                if query_embedding:
                    base_query = base_query.where(ImageModel.search_vector.is_not(None))
                    order_by_similarity = ImageModel.search_vector.cosine_distance(query_embedding)
                else:
                    search_term = f"%{query.lower()}%"
                    base_query = base_query.where(
                        or_(
                            ImageModel.prompt.ilike(search_term),
                            ImageModel.tags.op('&&')(func.array([query.lower()]))
                        )
                    )
            except Exception as e:
                logger.warning("Vector search failed, falling back to text search: %s", e)
                search_term = f"%{query.lower()}%"
                base_query = base_query.where(
                    or_(
                        ImageModel.prompt.ilike(search_term),
                        ImageModel.tags.op('&&')(func.array([query.lower()]))
                    )
                )
        elif query:
            # Fallback to text search
            search_term = f"%{query.lower()}%"
            base_query = base_query.where(
                or_(
                    ImageModel.prompt.ilike(search_term),
                    ImageModel.tags.op('&&')(func.array([query.lower()]))
                )
            )

        # Get total count
        count_query = select(func.count()).select_from(base_query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Get paginated results
        if order_by_similarity is not None:
            query_obj = base_query.order_by(order_by_similarity, ImageModel.approved_at.desc()).offset((page - 1) * page_size).limit(page_size)
        else:
            query_obj = base_query.order_by(ImageModel.approved_at.desc()).offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(query_obj)
        images = result.scalars().all()

        return list(images), total
    
    async def _add_vector_search(
        self, 
        query_obj, 
        query_text: str, 
        company_id: UUID
    ):
        """Add pgvector similarity search to query."""
        # This would use the embedding of the query text
        # For now, we'll use a simple approach - in production you'd:
        # 1. Generate embedding for query_text
        # 2. Use cosine similarity with search_vector column
        # 3. ORDER BY search_vector <=> query_embedding
        
        # Placeholder: fall back to text search
        search_term = f"%{query_text.lower()}%"
        return query_obj.where(
            or_(
                ImageModel.prompt.ilike(search_term),
                ImageModel.tags.op('&&')(func.array([query_text.lower()]))
            )
        )
    
    async def find_references_for_generation(
        self,
        company_id: UUID,
        image_brief: ImageBrief,
        explicit_reference_ids: List[UUID] = None,
        max_refs: int = 4,
    ) -> List[ReferenceImage]:
        """Find relevant reference images for a generation job."""
        references: List[ReferenceImage] = []
        
        # 1. Explicit references from user
        if explicit_reference_ids:
            result = await self.db.execute(
                select(ImageModel).where(
                    ImageModel.id.in_(explicit_reference_ids),
                    or_(
                        ImageModel.company_id == company_id,
                        ImageModel.is_global == True
                    )
                )
            )
            explicit = result.scalars().all()
            for img in explicit:
                references.append(ReferenceImage(
                    id=img.id,
                    url=img.url,
                    prompt=img.prompt,
                    tags=img.tags,
                    role="subject",
                ))
        
        # 2. Keyword-based search from image brief
        if len(references) < max_refs:
            # Extract keywords from prompt and style_keywords
            search_terms = []
            if image_brief.style_keywords:
                search_terms.extend(image_brief.style_keywords[:3])
            if image_brief.prompt:
                # Extract meaningful words from prompt
                words = image_brief.prompt.split()
                search_terms.extend([w for w in words if len(w) > 4][:5])
            
            for term in search_terms:
                if len(references) >= max_refs:
                    break
                
                result = await self.db.execute(
                    select(ImageModel).where(
                        or_(
                            ImageModel.tags.op('@>')([term.lower()]),
                            ImageModel.prompt.ilike(f"%{term}%")
                        ),
                        or_(
                            ImageModel.company_id == company_id,
                            ImageModel.is_global == True
                        ),
                        ~ImageModel.id.in_([r.id for r in references]) if references else True
                    ).order_by(ImageModel.approved_at.desc()).limit(2)
                )
                found = result.scalars().all()
                for img in found:
                    if len(references) < max_refs:
                        references.append(ReferenceImage(
                            id=img.id,
                            url=img.url,
                            prompt=img.prompt,
                            tags=img.tags,
                            role="style",
                        ))
        
        # 3. Add logo as reference if available (handled separately in brand kit)
        
        return references[:max_refs]
    
    async def update_tags(self, image_id: UUID, company_id: UUID, tags: List[str]) -> ImageModel:
        """Update tags for a library image (own images only)."""
        result = await self.db.execute(
            select(ImageModel).where(
                ImageModel.id == image_id,
                ImageModel.company_id == company_id
            )
        )
        image = result.scalar_one_or_none()
        
        if not image:
            raise ValueError("Image not found or access denied")
        
        image.tags = tags
        image.updated_at = datetime.now(timezone.utc)
        search_text = self._generate_search_text(image.prompt, tags)
        try:
            image.search_vector = await embed_text(search_text, is_query=False)
        except Exception as e:
            logger.warning("Failed to regenerate embedding for image %s: %s", image_id, e)
            image.search_vector = None

        await self.db.commit()
        await self.db.refresh(image)

        return image
    
    async def delete_image(self, image_id: UUID, company_id: UUID) -> bool:
        """Delete a library image (own images only)."""
        result = await self.db.execute(
            select(ImageModel).where(
                ImageModel.id == image_id,
                ImageModel.company_id == company_id
            )
        )
        image = result.scalar_one_or_none()
        
        if not image:
            return False
        
        await self.db.delete(image)
        await self.db.commit()
        return True
    
    async def get_popular_tags(self, company_id: UUID, limit: int = 20) -> List[Tuple[str, int]]:
        """Get most popular tags across own + global library."""
        result = await self.db.execute(
            select(ImageModel.tags).where(
                or_(
                    ImageModel.company_id == company_id,
                    ImageModel.is_global == True
                )
            )
        )
        all_tag_arrays = result.scalars().all()
        
        tag_counts = {}
        for tag_array in all_tag_arrays:
            for tag in tag_array:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
        
        sorted_tags = sorted(tag_counts.items(), key=lambda x: -x[1])
        return sorted_tags[:limit]
    
    async def cleanup_old_images(self) -> dict:
        """Cleanup old images based on retention policy."""
        now = datetime.now(timezone.utc)
        
        # Delete published images older than 30 days
        published_cutoff = now - timedelta(days=30)
        published_result = await self.db.execute(
            select(ImageModel).where(
                ImageModel.is_global == False,
                ImageModel.approved_at < published_cutoff
            )
        )
        published_images = published_result.scalars().all()
        published_count = len(published_images)
        
        for img in published_images:
            await self.db.delete(img)
        
        # Note: Draft/rejected images would be in a different folder/status
        # For now, we only track approved library images
        
        await self.db.commit()
        
        return {
            "published_deleted": published_count,
            "drafts_deleted": 0,
            "timestamp": now.isoformat(),
        }


# Vector search helpers
async def create_vector_index(db: AsyncSession) -> None:
    """Create HNSW index on search_vector column."""
    # Managed by Alembic migrations; keep helper for compatibility.
    await db.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_images_search_vector_hnsw
        ON images USING hnsw (search_vector vector_cosine_ops)
        WITH (m = 16, ef_construction = 64);
    """))
    await db.commit()


async def generate_embeddings_for_existing(db: AsyncSession, batch_size: int = 100) -> int:
    """Generate vector embeddings for existing images without vectors."""
    result = await db.execute(
        select(ImageModel).where(ImageModel.search_vector.is_(None)).limit(batch_size)
    )
    images = result.scalars().all()
    if not images:
        return 0

    count = 0
    for image in images:
        text_value = " ".join([image.prompt or "", " ".join(image.tags or [])]).strip()
        try:
            image.search_vector = await embed_text(text_value, is_query=False)
            if image.search_vector is not None:
                count += 1
        except Exception as e:
            logger.warning("Failed to backfill embedding for image %s: %s", image.id, e)
    await db.commit()
    return count
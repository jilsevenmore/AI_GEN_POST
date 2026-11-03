from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, List
from uuid import UUID, uuid4
from datetime import datetime
from app.db.session import get_db
from app.schemas.common import (
    RegenerateRequest, ApproveRequest, ReviewResponse,
    ContentResponse, ContentType, PlatformContent, Platform,
    ImageVariant, ImageAspectRatio, JobStatus
)

router = APIRouter()

# Mock content store (replace with real DB)
MOCK_CONTENTS = {}


@router.get("/{job_id}", response_model=ReviewResponse)
async def get_review(job_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get generated content for review (approve/regenerate)."""
    content = MOCK_CONTENTS.get(job_id)
    if not content:
        # Generate mock content for frontend testing
        content = _generate_mock_content(job_id)
        MOCK_CONTENTS[job_id] = content
    
    return ReviewResponse(
        job_id=job_id,
        content=content,
        can_regenerate=True,
        regeneration_count=0,
        max_regenerations=3,
    )


@router.post("/{job_id}/regenerate", response_model=ReviewResponse)
async def regenerate_content(
    job_id: UUID,
    request: RegenerateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Regenerate content with user feedback."""
    # TODO: Implement real regeneration with LangGraph
    # For now, return updated mock content
    content = _generate_mock_content(job_id, feedback=request.feedback)
    MOCK_CONTENTS[job_id] = content
    
    return ReviewResponse(
        job_id=job_id,
        content=content,
        can_regenerate=True,
        regeneration_count=1,
        max_regenerations=3,
    )


@router.post("/{job_id}/approve", response_model=ContentResponse)
async def approve_content(
    job_id: UUID,
    request: ApproveRequest,
    db: AsyncSession = Depends(get_db),
):
    """Approve content and move to publishing."""
    content = MOCK_CONTENTS.get(job_id)
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")
    
    # Apply text edits if provided
    if request.edited_text:
        for pc in content.platform_contents:
            if pc.platform in request.edited_text:
                pc.text = request.edited_text[pc.platform]
    
    # Set selected image as primary
    content.primary_image_id = request.selected_image_id
    
    # TODO: Trigger publishing flow (Phase 6)
    
    return content


def _generate_mock_content(job_id: UUID, feedback: str = None) -> ContentResponse:
    """Generate mock content for frontend testing."""
    platform_contents = [
        PlatformContent(
            platform=Platform.linkedin,
            text=f"🚀 Excited to share our latest insights on AI-powered content creation! {feedback or ''}\n\n#AI #ContentMarketing #Innovation",
            hashtags=["AI", "ContentMarketing", "Innovation", "Tech"],
            character_count=180,
        ),
        PlatformContent(
            platform=Platform.facebook,
            text=f"Creating engaging social content just got easier with AI! 🎨 {feedback or ''}",
            hashtags=["AI", "SocialMedia", "ContentCreation"],
            character_count=120,
        ),
        PlatformContent(
            platform=Platform.instagram,
            text=f"AI-powered creativity ✨ {feedback or ''} #AI #ContentCreation #Marketing",
            hashtags=["AI", "ContentCreation", "Marketing", "Innovation", "Tech"],
            character_count=95,
        ),
    ]
    
    image_variants = [
        ImageVariant(
            id=uuid4(),
            url="https://picsum.photos/seed/ai-gen-1/1024/1024",
            aspect_ratio=ImageAspectRatio._1_1,
            width=1024,
            height=1024,
            is_primary=True,
            prompt_used="Professional blog header image about AI content generation, modern tech aesthetic",
            reference_image_ids=[],
        ),
        ImageVariant(
            id=uuid4(),
            url="https://picsum.photos/seed/ai-gen-2/1024/1280",
            aspect_ratio=ImageAspectRatio._4_5,
            width=1024,
            height=1280,
            is_primary=False,
            prompt_used="Instagram post style image about AI content generation, vibrant colors",
            reference_image_ids=[],
        ),
    ]
    
    return ContentResponse(
        id=uuid4(),
        job_id=job_id,
        type=ContentType.social_post,
        title="AI Content Generation Blog Post",
        long_text="Full blog post content goes here... This would be the long-form version for LinkedIn and blog publishing.",
        platform_contents=platform_contents,
        image_variants=image_variants,
        primary_image_id=image_variants[0].id,
        safety_check_passed=True,
        safety_flags=[],
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
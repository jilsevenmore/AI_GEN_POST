import pytest
from uuid import uuid4
from app.services.ai.state import GenerationState, JobInput, BrandKitData
from app.services.ai.graph import should_generate_image
from app.schemas.common import ApproveRequest
from app.models.content import Content
from app.services.publisher import get_publisher


def test_should_generate_image_disabled():
    job_input = JobInput(
        job_id=uuid4(),
        company_id=uuid4(),
        type="blog",
        title="Test Blog",
        topic="CRM",
        generate_image=False,
    )
    state = GenerationState(
        job_input=job_input,
        brand_kit=BrandKitData(company_name="Test Co"),
    )
    assert should_generate_image(state) == "skip_image"


def test_should_generate_image_enabled_for_blog():
    job_input = JobInput(
        job_id=uuid4(),
        company_id=uuid4(),
        type="blog",
        title="Test Blog",
        topic="CRM",
        generate_image=True,
    )
    state = GenerationState(
        job_input=job_input,
        brand_kit=BrandKitData(company_name="Test Co"),
    )
    assert should_generate_image(state) == "generate_image"


def test_approve_request_allows_optional_image():
    req = ApproveRequest(selected_image_id=None)
    assert req.selected_image_id is None


def test_publisher_select_best_image_empty():
    publisher = get_publisher()
    content = Content(
        id=uuid4(),
        job_id=uuid4(),
        company_id=uuid4(),
        type="blog",
        title="CRM Blog",
        long_text="Text content",
        platform_contents=[],
        image_variants=[],
        primary_image_id=None,
    )
    assert publisher._select_best_image(content, "facebook") is None

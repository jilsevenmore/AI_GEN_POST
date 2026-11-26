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


def test_aspect_to_dimensions_divisible_by_16():
    from app.services.ai.nodes.generate_image import ALL_ASPECT_RATIOS, _aspect_to_dimensions

    for ratio in [*ALL_ASPECT_RATIOS, "unknown"]:
        width, height = _aspect_to_dimensions(ratio)
        assert width % 16 == 0, f"{ratio} width {width} is not divisible by 16"
        assert height % 16 == 0, f"{ratio} height {height} is not divisible by 16"


@pytest.mark.asyncio
async def test_resume_after_review_loads_job_from_db(monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, MagicMock
    from app.services.ai import graph as graph_module

    job_id = uuid4()
    company_id = uuid4()
    db_job = SimpleNamespace(id=job_id, company_id=company_id)

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = db_job
    mock_db = AsyncMock()
    mock_db.execute.return_value = mock_result

    called_with = {}

    async def fake_run_generation_job(j_id, c_id, session_factory, **kwargs):
        called_with["job_id"] = j_id
        called_with["company_id"] = c_id
        called_with.update(kwargs)
        return "ok"

    monkeypatch.setattr(graph_module, "run_generation_job", fake_run_generation_job)

    res = await graph_module.resume_after_review(
        job_id=str(job_id),
        feedback="Make it futuristic",
        regenerate_text=True,
        regenerate_image=True,
        new_reference_ids=[],
        db=mock_db,
    )

    assert res == "ok"
    assert called_with["job_id"] == str(job_id)
    assert called_with["company_id"] == str(company_id)
    assert called_with["user_feedback"] == "Make it futuristic"
    assert called_with["regenerate_image"] is True

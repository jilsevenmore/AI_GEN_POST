import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy import select
from uuid import uuid4
from datetime import datetime, timezone

from app.main import app
from app.db.session import Base, get_db
from app.core.dependencies import get_current_user, get_current_company
from app.models.job import Job
from app.models.company import Company
from app.models.user import User
from app.schemas.common import JobCreate, SourceFileUploadResponse

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

# Single shared engine so all sessions see the same in-memory SQLite database
engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

_SCHEMA_CREATED = False


async def ensure_schema():
    global _SCHEMA_CREATED
    if not _SCHEMA_CREATED:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        _SCHEMA_CREATED = True


@pytest_asyncio.fixture
async def db_session():
    await ensure_schema()
    async with TestingSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def client(db_session):
    company = Company(id=uuid4(), name="Test Co", created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc))
    user = User(id=uuid4(), email="test@example.com", hashed_password="x", company_id=company.id, is_active=True, is_superuser=False, created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc))
    db_session.add(company)
    db_session.add(user)
    job = Job(
        id=uuid4(), company_id=company.id, user_id=user.id, type="blog", title="T", topic="topic",
        tone=None, audience=None, keywords=[], image_description=None, platforms=[],
        use_references=True, reference_image_ids=[], status="pending", progress=0,
        current_step="queued", regeneration_count=0,
        created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)
    await db_session.refresh(company)
    await db_session.refresh(user)

    async def override_get_db():
        yield db_session

    def override_get_current_user():
        return user

    def override_get_current_company():
        return company

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_current_company] = override_get_current_company

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield (ac, job.id)

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_job_create_schema_accepts_source_context():
    data = JobCreate(
        type="blog", title="T", topic="topic",
        source_context="# Hello\nThis is source context.",
        source_file_name="notes.md",
        source_file_url="https://example.com/notes.md",
    )
    assert data.source_context == "# Hello\nThis is source context."
    assert data.source_file_name == "notes.md"
    assert data.source_file_url == "https://example.com/notes.md"


@pytest.mark.asyncio
async def test_source_file_upload_response_schema():
    resp = SourceFileUploadResponse(
        file_id=uuid4(),
        file_name="notes.md",
        file_url="https://example.com/notes.md",
        size_bytes=123,
        extracted_text_preview="# Hello",
        context_stored=True,
    )
    assert resp.context_stored is True
    assert resp.size_bytes == 123


@pytest.mark.asyncio
async def test_job_create_schema_accepts_instagram_fields():
    """JobCreate should accept Instagram post type and cover image URL."""
    data = JobCreate(
        type="blog", title="T", topic="Instagram marketing",
        platforms=["instagram"],
        instagram_post_type="story",
        instagram_cover_image_url="https://example.com/cover.jpg",
    )
    assert data.instagram_post_type == "story"
    assert data.instagram_cover_image_url == "https://example.com/cover.jpg"

    # Feed type
    data2 = JobCreate(
        type="blog", title="T", topic="Instagram feed",
        platforms=["instagram"],
        instagram_post_type="feed",
    )
    assert data2.instagram_post_type == "feed"
    assert data2.instagram_cover_image_url is None

    # Reel type
    data3 = JobCreate(
        type="blog", title="T", topic="Instagram reel",
        platforms=["instagram"],
        instagram_post_type="reel",
        instagram_cover_image_url="https://example.com/reel_cover.jpg",
    )
    assert data3.instagram_post_type == "reel"


# --- Endpoint tests using a fake (in-memory) session, no real database needed ---

class _FakeResult:
    def __init__(self, row):
        self._row = row

    def scalar_one_or_none(self):
        return self._row


class _FakeSession:
    """Minimal async session double: execute/commit/refresh are no-ops or return a row."""
    def __init__(self, job_row=None):
        self._job_row = job_row
        self.committed = False
        self.refreshed = None

    async def execute(self, *args, **kwargs):
        return _FakeResult(self._job_row)

    async def commit(self):
        self.committed = True

    async def refresh(self, obj):
        self.refreshed = obj


@pytest.mark.asyncio
async def test_upload_valid_md_with_fake_session():
    """Endpoint stores context + file fields and returns 201 (no real DB)."""
    from app.api.v1.endpoints.jobs import upload_source_file
    from fastapi import UploadFile
    import io

    job = Job(
        id=uuid4(), company_id=uuid4(), user_id=uuid4(), type="blog", title="T", topic="topic",
        tone=None, audience=None, keywords=[], image_description=None, platforms=[],
        use_references=True, reference_image_ids=[], status="pending", progress=0,
        current_step="queued", regeneration_count=0,
        created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
    )
    session = _FakeSession(job_row=job)

    async def fake_user():
        return User(id=uuid4(), email="t@t.com", hashed_password="x", company_id=uuid4(), is_active=True, is_superuser=False, created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc))

    async def fake_company():
        return Company(id=uuid4(), name="Co", created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc))

    app.dependency_overrides[get_db] = lambda: session
    app.dependency_overrides[get_current_user] = fake_user
    app.dependency_overrides[get_current_company] = fake_company

    try:
        md = b"# Notes\n\nsource context here"
        upload_file = UploadFile(filename="notes.md", file=io.BytesIO(md), headers={"content-type": "text/markdown"})
        response = await upload_source_file(
            job_id=job.id, file=upload_file,
            current_user=await fake_user(), current_company=await fake_company(), db=session,
        )
        assert response.context_stored is True
        assert response.file_name == "notes.md"
        assert response.size_bytes == len(md)
        assert "# Notes" in response.extracted_text_preview

        # Context persisted on the job object
        assert job.source_file_name == "notes.md"
        assert job.source_context_text == md.decode("utf-8")
        assert job.source_file_url is not None
        assert session.committed is True
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_upload_invalid_extension_with_fake_session():
    """Non-.md file -> 400 (fake session, no DB)."""
    from app.api.v1.endpoints.jobs import upload_source_file
    from fastapi import UploadFile
    from fastapi import HTTPException
    import io

    job = Job(
        id=uuid4(), company_id=uuid4(), user_id=uuid4(), type="blog", title="T", topic="topic",
        tone=None, audience=None, keywords=[], image_description=None, platforms=[],
        use_references=True, reference_image_ids=[], status="pending", progress=0,
        created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
    )
    session = _FakeSession(job_row=job)

    async def fake_user():
        return User(id=uuid4(), email="t@t.com", hashed_password="x", company_id=uuid4(), is_active=True, is_superuser=False, created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc))

    async def fake_company():
        return Company(id=uuid4(), name="Co", created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc))

    app.dependency_overrides[get_db] = lambda: session
    app.dependency_overrides[get_current_user] = fake_user
    app.dependency_overrides[get_current_company] = fake_company

    try:
        upload_file = UploadFile(filename="data.pdf", file=io.BytesIO(b"%PDF"), headers={"content-type": "application/pdf"})
        try:
            await upload_source_file(
                job_id=job.id, file=upload_file,
                current_user=await fake_user(), current_company=await fake_company(), db=session,
            )
            assert False, "Expected HTTPException"
        except HTTPException as exc:
            assert exc.status_code == 400
            assert "Unsupported file type" in exc.detail
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_upload_nonexistent_job_with_fake_session():
    """Missing job -> 404 (fake session returns None)."""
    from app.api.v1.endpoints.jobs import upload_source_file
    from fastapi import UploadFile, HTTPException
    import io

    session = _FakeSession(job_row=None)  # job not found

    async def fake_user():
        return User(id=uuid4(), email="t@t.com", hashed_password="x", company_id=uuid4(), is_active=True, is_superuser=False, created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc))

    async def fake_company():
        return Company(id=uuid4(), name="Co", created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc))

    app.dependency_overrides[get_db] = lambda: session
    app.dependency_overrides[get_current_user] = fake_user
    app.dependency_overrides[get_current_company] = fake_company

    try:
        upload_file = UploadFile(filename="notes.md", file=io.BytesIO(b"# hi"), headers={"content-type": "text/markdown"})
        try:
            await upload_source_file(
                job_id=uuid4(), file=upload_file,
                current_user=await fake_user(), current_company=await fake_company(), db=session,
            )
            assert False, "Expected HTTPException"
        except HTTPException as exc:
            assert exc.status_code == 404
    finally:
        app.dependency_overrides.clear()

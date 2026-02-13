"""Integration tests for GET /api/jobs/recent and posted_days filter.

Uses an in-process SQLite database. PostgreSQL-specific column types
(JSONB, TSVECTOR, UUID) are compiled as SQLite-compatible types via
SQLAlchemy @compiles hooks registered before any model imports.
"""

# Register PG→SQLite type compilers BEFORE any model imports
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from sqlalchemy.ext.compiler import compiles


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(type_, compiler, **kw):
    return "TEXT"


@compiles(TSVECTOR, "sqlite")
def _compile_tsvector_sqlite(type_, compiler, **kw):
    return "TEXT"


@compiles(UUID, "sqlite")
def _compile_uuid_sqlite(type_, compiler, **kw):
    return "VARCHAR(36)"


import uuid  # noqa: E402
from datetime import datetime, timedelta, timezone  # noqa: E402

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import event  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models.board import JobBoard  # noqa: E402
from app.models.job import Job  # noqa: E402

# ---------------------------------------------------------------------------
# Test DB setup (async SQLite)
# ---------------------------------------------------------------------------

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(TEST_DB_URL, echo=False)
TestSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@event.listens_for(engine.sync_engine, "connect")
def _register_sqlite_functions(dbapi_conn, _connection_record):
    dbapi_conn.create_function("now", 0, lambda: datetime.now(timezone.utc).isoformat())


async def _override_get_db():
    async with TestSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


app.dependency_overrides[get_db] = _override_get_db

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    """Create tables before each test, drop after."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session():
    async with TestSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def board(db_session: AsyncSession) -> JobBoard:
    b = JobBoard(
        id=uuid.uuid4(),
        name="Test Board",
        url="https://example.com/careers",
        scan_interval_minutes=60,
        enabled=True,
        keyword_filters=[],
        scraper_config={
            "scraper_type": "generic",
            "selectors": {},
            "pagination_type": "click",
            "max_pages": 1,
        },
    )
    db_session.add(b)
    await db_session.commit()
    await db_session.refresh(b)
    return b


async def _create_job(
    db: AsyncSession,
    board: JobBoard,
    title: str,
    posted_date: datetime | None,
    **kwargs,
) -> Job:
    job = Job(
        id=uuid.uuid4(),
        board_id=board.id,
        title=title,
        company=kwargs.get("company", "TestCo"),
        location=kwargs.get("location", "Remote"),
        url=kwargs.get("url", f"https://example.com/jobs/{uuid.uuid4().hex[:8]}"),
        posted_date=posted_date,
        description=kwargs.get("description", "A job."),
        dedup_hash=uuid.uuid4().hex,
        match_score=kwargs.get("match_score", 50.0),
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


# ---------------------------------------------------------------------------
# Tests — GET /api/jobs/recent
# ---------------------------------------------------------------------------


class TestRecentEndpoint:
    @pytest.mark.asyncio
    async def test_recent_default_7_days(self, client, db_session, board):
        now = datetime.now(timezone.utc)
        await _create_job(db_session, board, "Fresh Job", now - timedelta(days=2))
        await _create_job(db_session, board, "Old Job", now - timedelta(days=30))

        resp = await client.get("/api/jobs/recent")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["jobs"][0]["title"] == "Fresh Job"

    @pytest.mark.asyncio
    async def test_recent_custom_days(self, client, db_session, board):
        now = datetime.now(timezone.utc)
        await _create_job(db_session, board, "Today", now)
        await _create_job(db_session, board, "Last Week", now - timedelta(days=5))
        await _create_job(db_session, board, "Last Month", now - timedelta(days=20))

        resp = await client.get("/api/jobs/recent?days=3")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["jobs"][0]["title"] == "Today"

    @pytest.mark.asyncio
    async def test_recent_30_days(self, client, db_session, board):
        now = datetime.now(timezone.utc)
        await _create_job(db_session, board, "Recent", now - timedelta(days=10))
        await _create_job(db_session, board, "Ancient", now - timedelta(days=60))

        resp = await client.get("/api/jobs/recent?days=30")
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    @pytest.mark.asyncio
    async def test_recent_excludes_null_posted_date(self, client, db_session, board):
        now = datetime.now(timezone.utc)
        await _create_job(db_session, board, "Has date", now - timedelta(days=1))
        await _create_job(db_session, board, "No date", None)

        resp = await client.get("/api/jobs/recent?days=7")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["jobs"][0]["title"] == "Has date"

    @pytest.mark.asyncio
    async def test_recent_empty_result(self, client, db_session, board):
        now = datetime.now(timezone.utc)
        await _create_job(db_session, board, "Old", now - timedelta(days=100))

        resp = await client.get("/api/jobs/recent?days=7")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0
        assert resp.json()["jobs"] == []

    @pytest.mark.asyncio
    async def test_recent_pagination(self, client, db_session, board):
        now = datetime.now(timezone.utc)
        for i in range(5):
            await _create_job(db_session, board, f"Job {i}", now - timedelta(hours=i))

        resp = await client.get("/api/jobs/recent?days=7&page=1&page_size=2")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 5
        assert len(body["jobs"]) == 2
        assert body["page"] == 1

    @pytest.mark.asyncio
    async def test_recent_invalid_days(self, client):
        resp = await client.get("/api/jobs/recent?days=0")
        assert resp.status_code == 422

        resp = await client.get("/api/jobs/recent?days=-1")
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Tests — posted_days filter on GET /api/jobs
# ---------------------------------------------------------------------------


class TestPostedDaysFilter:
    @pytest.mark.asyncio
    async def test_list_with_posted_days(self, client, db_session, board):
        now = datetime.now(timezone.utc)
        await _create_job(db_session, board, "New", now - timedelta(days=1))
        await _create_job(db_session, board, "Old", now - timedelta(days=15))

        resp = await client.get("/api/jobs?posted_days=7")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["jobs"][0]["title"] == "New"

    @pytest.mark.asyncio
    async def test_list_without_posted_days_returns_all(self, client, db_session, board):
        now = datetime.now(timezone.utc)
        await _create_job(db_session, board, "New", now - timedelta(days=1))
        await _create_job(db_session, board, "Old", now - timedelta(days=15))
        await _create_job(db_session, board, "No date", None)

        resp = await client.get("/api/jobs")
        assert resp.status_code == 200
        assert resp.json()["total"] == 3

    @pytest.mark.asyncio
    async def test_posted_days_combined_with_location(self, client, db_session, board):
        now = datetime.now(timezone.utc)
        await _create_job(db_session, board, "Remote New", now - timedelta(days=1), location="Remote")
        await _create_job(db_session, board, "NYC New", now - timedelta(days=1), location="New York")
        await _create_job(db_session, board, "Remote Old", now - timedelta(days=30), location="Remote")

        resp = await client.get("/api/jobs?posted_days=7&location=Remote")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["jobs"][0]["title"] == "Remote New"

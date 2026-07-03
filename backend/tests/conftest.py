"""Shared pytest fixtures: test database, transactional sessions, seeded data, API client."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

os.environ.setdefault("CE_ENV", "test")

from seeds.demo_data import seed_minimal  # noqa: E402

from context_engine.config.settings import get_settings  # noqa: E402
from context_engine.storage.models import Base  # noqa: E402

ADMIN_KEY = "demo-admin-key"
LEAD_KEY = "demo-lead-key"
ENGINEER_KEY = "demo-engineer-key"
VIEWER_KEY = "demo-viewer-key"
MCP_TOKEN = "demo-mcp-token"


def auth_headers(raw_key: str = ADMIN_KEY) -> dict[str, str]:
    """Authorization headers for a raw demo key."""
    return {"Authorization": f"Bearer {raw_key}"}


@pytest.fixture(scope="session")
def admin_headers() -> dict[str, str]:
    return auth_headers(ADMIN_KEY)


@pytest.fixture(scope="session")
def lead_headers() -> dict[str, str]:
    return auth_headers(LEAD_KEY)


@pytest.fixture(scope="session")
def engineer_headers() -> dict[str, str]:
    return auth_headers(ENGINEER_KEY)


@pytest.fixture(scope="session")
def viewer_headers() -> dict[str, str]:
    return auth_headers(VIEWER_KEY)


@pytest.fixture(scope="session")
async def engine() -> AsyncIterator[AsyncEngine]:
    """Session-scoped engine on the test database; creates/drops the schema once."""
    settings = get_settings()
    engine = create_async_engine(settings.test_database_url)
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
        # HNSW is approximate: its recall depends on insertion history, which makes
        # vector-search assertions order-sensitive across the suite. Tests run on tiny
        # datasets — drop the ANN index so pgvector uses exact (deterministic) scans.
        await conn.execute(text("DROP INDEX IF EXISTS ix_chunks_embedding"))
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def session(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """Function-scoped session inside a rolled-back outer transaction (savepoint pattern)."""
    async with engine.connect() as connection:
        transaction = await connection.begin()
        async_session = AsyncSession(
            bind=connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
        try:
            yield async_session
        finally:
            await async_session.close()
            await transaction.rollback()


@pytest.fixture
async def seeded_session(session: AsyncSession) -> AsyncSession:
    """Session with the minimal deterministic demo data loaded."""
    await seed_minimal(session)
    return session


@pytest.fixture
async def api_client(engine: AsyncEngine, seeded_session: AsyncSession) -> AsyncIterator[object]:
    """httpx AsyncClient against the FastAPI app (skips until the api package lands).

    Sends the admin demo key by default; override headers per request for other roles.
    """
    pytest.importorskip("httpx")
    app_module = pytest.importorskip("context_engine.api.app")
    import httpx

    from context_engine.storage.db import get_session as get_session_dep

    app = app_module.create_app()

    async def _override_session() -> AsyncIterator[AsyncSession]:
        yield seeded_session

    app.dependency_overrides[get_session_dep] = _override_session
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
        headers=auth_headers(ADMIN_KEY),
    ) as client:
        yield client

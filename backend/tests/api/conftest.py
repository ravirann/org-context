"""API-test-local fixtures: an unauthenticated client (no default Authorization)."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
async def noauth_client(seeded_session: AsyncSession) -> AsyncIterator[object]:
    """httpx AsyncClient with NO default Authorization header.

    Mirrors the shared ``api_client`` wiring (same app + session override) but sends
    no bearer token, so callers can assert 401 behaviour and add headers per request.
    """
    import httpx

    from context_engine.api.app import create_app
    from context_engine.storage.db import get_session as get_session_dep

    app = create_app()

    async def _override_session() -> AsyncIterator[AsyncSession]:
        yield seeded_session

    app.dependency_overrides[get_session_dep] = _override_session
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

"""Opt-in Redis cache tests for hybrid search (retrieval/cache.py).

These tests exercise the real Redis at ``settings.redis_url`` (compose maps it to
:6380). They opt into caching by monkeypatching ``cache.enabled`` to ``True`` (the
cache is disabled under ``env == "test"`` by default so the rest of the suite stays
deterministic). Each test flushes its own keys to stay isolated from the rolled-back
DB session.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from context_engine.config.settings import get_settings
from context_engine.retrieval import cache
from context_engine.retrieval import service as service_module
from context_engine.retrieval.service import SearchFilters, search_chunks
from context_engine.storage.models import SearchEvent, User


async def get_user(session: AsyncSession, email: str) -> User:
    return (await session.execute(select(User).where(User.email == email))).scalar_one()


async def event_count(session: AsyncSession) -> int:
    return int((await session.execute(select(func.count()).select_from(SearchEvent))).scalar_one())


def _redis():  # type: ignore[no-untyped-def]
    from redis.asyncio import Redis

    return Redis.from_url(get_settings().redis_url, decode_responses=True)


@pytest.fixture
async def redis_clean() -> AsyncIterator[None]:
    """Clear cache + generation keys before and after each test."""
    r = _redis()
    keys = await r.keys("ce:search:*")
    if keys:
        await r.delete(*keys)
    await r.aclose()
    yield
    r = _redis()
    keys = await r.keys("ce:search:*")
    if keys:
        await r.delete(*keys)
    await r.aclose()


@pytest.fixture
def cache_on(monkeypatch: pytest.MonkeyPatch) -> None:
    """Opt this test into the cache (disabled by default under env==test)."""
    monkeypatch.setattr(cache, "enabled", lambda _settings: True)


async def test_second_identical_search_hits_cache(
    seeded_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    cache_on: None,
    redis_clean: None,
) -> None:
    admin = await get_user(seeded_session, "admin@demo.dev")

    # Count how many times the DB-backed search leg actually runs.
    calls = {"n": 0}
    real_search = service_module._search

    async def counting_search(*args: object, **kwargs: object) -> object:
        calls["n"] += 1
        return await real_search(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(service_module, "_search", counting_search)

    filters = SearchFilters(page_size=5)
    first = await search_chunks(seeded_session, admin, "idempotency", filters)
    second = await search_chunks(seeded_session, admin, "idempotency", filters)

    # First call runs the DB leg; the second is served from cache.
    assert calls["n"] == 1
    assert [h.document_id for h in second.items] == [h.document_id for h in first.items]
    assert second.total == first.total
    assert second.acl_blocked_count == first.acl_blocked_count

    # A cache_hit telemetry event is still recorded on the cached call.
    hit_events = (
        (
            await seeded_session.execute(
                select(SearchEvent).where(
                    SearchEvent.query == "idempotency", SearchEvent.cache_hit.is_(True)
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(hit_events) == 1


async def test_gen_bump_invalidates_cache(
    seeded_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    cache_on: None,
    redis_clean: None,
) -> None:
    admin = await get_user(seeded_session, "admin@demo.dev")

    real_search = service_module._search
    calls = {"n": 0}

    async def counting_search(*args: object, **kwargs: object) -> object:
        calls["n"] += 1
        return await real_search(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(service_module, "_search", counting_search)

    filters = SearchFilters(page_size=5)
    await search_chunks(seeded_session, admin, "webhooks", filters)
    await search_chunks(seeded_session, admin, "webhooks", filters)
    assert calls["n"] == 1  # second served from cache

    # Bump the generation counter (as a successful sync would) -> keys change -> miss.
    r = _redis()
    await r.incr("ce:search:gen")
    await r.aclose()

    await search_chunks(seeded_session, admin, "webhooks", filters)
    assert calls["n"] == 2  # cache invalidated, DB leg ran again


async def test_engineer_cache_never_served_to_viewer(
    seeded_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    cache_on: None,
    redis_clean: None,
) -> None:
    engineer = await get_user(seeded_session, "jade@demo.dev")  # engineer, Growth
    viewer = await get_user(seeded_session, "maya@demo.dev")  # viewer, Growth
    assert engineer.id != viewer.id

    real_search = service_module._search
    seen_users: list[str] = []

    async def tracking_search(session, user, q, filters):  # type: ignore[no-untyped-def]
        seen_users.append(str(user.id))
        return await real_search(session, user, q, filters)

    monkeypatch.setattr(service_module, "_search", tracking_search)

    filters = SearchFilters(page_size=5)
    # Engineer searches (populates cache under the engineer's key).
    await search_chunks(seeded_session, engineer, "credentials rotation", filters)
    # Viewer runs the identical query — must NOT be served the engineer's cache entry
    # (different identity in the key), so the DB leg runs fresh for the viewer too.
    await search_chunks(seeded_session, viewer, "credentials rotation", filters)

    # Both users triggered a fresh DB leg (no cross-user cache reuse).
    assert seen_users == [str(engineer.id), str(viewer.id)]

    # And the keys are genuinely distinct.
    gen = await cache.current_gen(get_settings())
    eng_key = cache.cache_key(gen, engineer, "credentials rotation", filters)
    viewer_key = cache.cache_key(gen, viewer, "credentials rotation", filters)
    assert eng_key != viewer_key


async def test_corrupted_cache_entry_is_graceful_miss(
    seeded_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    cache_on: None,
    redis_clean: None,
) -> None:
    admin = await get_user(seeded_session, "admin@demo.dev")
    filters = SearchFilters(page_size=5)

    # Poison the exact cache key with non-JSON garbage.
    gen = await cache.current_gen(get_settings())
    key = cache.cache_key(gen, admin, "idempotency", filters)
    r = _redis()
    await r.set(key, "{not valid json!!!")
    await r.aclose()

    # The search must succeed (graceful miss), not raise.
    page = await search_chunks(seeded_session, admin, "idempotency", filters)
    assert page.total >= 0
    assert isinstance(page.items, list)

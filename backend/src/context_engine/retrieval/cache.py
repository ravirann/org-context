"""Redis-backed result cache for hybrid search — per-user, ACL-safe, best-effort.

The cache key is derived from a monotonically increasing generation counter
(``ce:search:gen``, bumped on every successful sync so a reindex invalidates every
cached result at once), the *requesting user's identity* (id + role + team), the
normalized query, and the canonicalized filter set. Because the user identity is
part of the key, one user's cached results can never be served to a different user —
ACL isolation is preserved by construction (an engineer and a viewer produce
different keys even for an identical query).

Every Redis operation is wrapped so any connectivity or serialization error results
in a silent cache *bypass* rather than a failed search. The cache is disabled when
``settings.env == "test"`` unless a test explicitly opts in (see :func:`enabled`),
keeping the deterministic test suite hermetic.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from datetime import datetime
from typing import TYPE_CHECKING, Any

from context_engine.config.settings import Settings
from context_engine.observability.logging import get_logger
from context_engine.retrieval.service import SearchFilters, SearchHit, SearchPage
from context_engine.storage.models import User

if TYPE_CHECKING:
    from redis.asyncio import Redis

logger = get_logger(__name__)

GEN_KEY = "ce:search:gen"
DEFAULT_TTL_SECONDS = 60


def enabled(settings: Settings) -> bool:
    """Whether the cache is active for this environment.

    Disabled under ``env == "test"`` so existing integration tests stay deterministic;
    the dedicated cache tests monkeypatch this to ``True`` to opt in.
    """
    return settings.env != "test"


def _get_client(settings: Settings) -> Redis | None:
    """Construct an async Redis client, or ``None`` if the library/URL is unusable."""
    try:
        from redis.asyncio import Redis

        return Redis.from_url(settings.redis_url, decode_responses=True)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("search_cache_client_error", error=str(exc))
        return None


def _canonical_filters(filters: SearchFilters) -> str:
    """Deterministic JSON of the filter set (sorted lists, stable key order)."""
    payload = {
        "doc_types": sorted(filters.doc_types) if filters.doc_types else None,
        "source_ids": sorted(filters.source_ids) if filters.source_ids else None,
        "repo": filters.repo,
        "service": filters.service,
        "status": filters.status,
        "page": filters.page,
        "page_size": filters.page_size,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def cache_key(gen: int, user: User, query: str, filters: SearchFilters) -> str:
    """Compute the sha256 cache key for a search request."""
    raw = f"{gen}|{user.id}|{user.role.value}|{user.team_id}|{query}|{_canonical_filters(filters)}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"ce:search:{digest}"


def _hit_to_json(hit: SearchHit) -> dict[str, Any]:
    data = dataclasses.asdict(hit)
    data["last_activity_at"] = hit.last_activity_at.isoformat()
    return data


def _hit_from_json(data: dict[str, Any]) -> SearchHit:
    data = dict(data)
    data["last_activity_at"] = datetime.fromisoformat(data["last_activity_at"])
    return SearchHit(**data)


def _page_to_json(page: SearchPage) -> str:
    return json.dumps(
        {
            "items": [_hit_to_json(h) for h in page.items],
            "total": page.total,
            "acl_blocked_count": page.acl_blocked_count,
        }
    )


def _page_from_json(raw: str | bytes) -> SearchPage:
    obj = json.loads(raw)
    return SearchPage(
        items=[_hit_from_json(h) for h in obj["items"]],
        total=int(obj["total"]),
        acl_blocked_count=int(obj["acl_blocked_count"]),
    )


async def current_gen(settings: Settings) -> int:
    """Read ``ce:search:gen`` (default 0). Bypasses to 0 on any Redis error."""
    client = _get_client(settings)
    if client is None:
        return 0
    try:
        raw = await client.get(GEN_KEY)
        return int(raw) if raw is not None else 0
    except Exception as exc:
        logger.warning("search_cache_gen_error", error=str(exc))
        return 0
    finally:
        await _safe_close(client)


async def get(settings: Settings, key: str) -> SearchPage | None:
    """Return the cached page for ``key``, or ``None`` on miss/error/corruption."""
    client = _get_client(settings)
    if client is None:
        return None
    try:
        raw = await client.get(key)
        if raw is None:
            return None
        return _page_from_json(raw)
    except Exception as exc:
        # Corrupted entry or connectivity issue → graceful miss.
        logger.warning("search_cache_get_error", error=str(exc))
        return None
    finally:
        await _safe_close(client)


async def set(settings: Settings, key: str, page: SearchPage, ttl_seconds: int) -> None:
    """Store ``page`` under ``key`` with the given TTL. Best-effort; errors ignored."""
    client = _get_client(settings)
    if client is None:
        return
    try:
        await client.set(key, _page_to_json(page), ex=max(1, ttl_seconds))
    except Exception as exc:
        logger.warning("search_cache_set_error", error=str(exc))
    finally:
        await _safe_close(client)


async def _safe_close(client: Redis) -> None:
    try:
        await client.aclose()
    except Exception:  # pragma: no cover - defensive
        pass

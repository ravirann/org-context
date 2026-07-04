"""Source sync pipeline: lock -> fetch -> redact -> upsert -> index -> prune -> audit.

Each sync opens a :class:`SyncRun` telemetry row, processes connector items with
per-item isolation (one poisoned item never aborts the run), skips documents whose
content is unchanged since the last sync, prunes documents that vanished upstream,
and finalizes the run with counts and a status. A Redis lock guards against
concurrent syncs of the same source; Redis is best-effort, so an unavailable Redis
degrades gracefully (no lock, no cache-generation bump) rather than failing the sync.
"""

from __future__ import annotations

import hashlib
from dataclasses import replace
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from context_engine.config.constants import SETTINGS_PII_REDACTION
from context_engine.config.settings import get_settings
from context_engine.connectors.base import get_connector, list_active_external_ids
from context_engine.indexing.chunking import index_document
from context_engine.ingestion.normalize import upsert_raw_item
from context_engine.ingestion.pii import DEFAULT_PII_PATTERNS, redact
from context_engine.observability.logging import get_logger
from context_engine.storage.models import (
    DocStatus,
    Document,
    Source,
    SyncRun,
    SyncRunStatus,
    SyncStatus,
    SyncTrigger,
)
from context_engine.storage.repositories import count_where, get_setting, write_audit

logger = get_logger(__name__)

MAX_RECORDED_ERRORS = 50
"""SyncRun.errors is capped at this many entries."""

SYNC_LOCK_TTL_SECONDS = 600
"""How long a per-source sync lock is held before it auto-expires."""


def content_hash(title: str, content: str) -> str:
    """Stable sha256 hex of ``title + "\\n" + content`` (post-redaction content)."""
    return hashlib.sha256(f"{title}\n{content}".encode()).hexdigest()


def _redis_client() -> object | None:
    """Return an async Redis client, or ``None`` if the library/URL is unavailable."""
    try:
        import redis.asyncio as redis

        return redis.from_url(get_settings().redis_url)
    except Exception as exc:  # noqa: BLE001 — redis is best-effort
        logger.warning("redis_unavailable", error=str(exc))
        return None


async def _acquire_lock(client: object | None, source_id: str) -> bool:
    """Try to take the per-source sync lock. Returns True if acquired (or no redis)."""
    if client is None:
        return True
    try:
        acquired = await client.set(  # type: ignore[attr-defined]
            f"ce:sync-lock:{source_id}", "1", nx=True, ex=SYNC_LOCK_TTL_SECONDS
        )
        return bool(acquired)
    except Exception as exc:  # noqa: BLE001 — proceed without a lock on redis errors
        logger.warning("sync_lock_failed", source_id=source_id, error=str(exc))
        return True


async def _release_lock(client: object | None, source_id: str) -> None:
    if client is None:
        return
    try:
        await client.delete(f"ce:sync-lock:{source_id}")  # type: ignore[attr-defined]
    except Exception as exc:  # noqa: BLE001 — lock auto-expires anyway
        logger.warning("sync_unlock_failed", source_id=source_id, error=str(exc))


async def _bump_search_generation(client: object | None) -> None:
    """Invalidate the retrieval cache by bumping ``ce:search:gen`` (best-effort)."""
    if client is None:
        return
    try:
        await client.incr("ce:search:gen")  # type: ignore[attr-defined]
    except Exception as exc:  # noqa: BLE001 — cache invalidation is best-effort
        logger.warning("search_gen_bump_failed", error=str(exc))


async def _close_redis(client: object | None) -> None:
    if client is None:
        return
    try:
        await client.aclose()  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001 — teardown is best-effort
        pass


async def _prune_missing(session: AsyncSession, source: Source, active_ids: list[str]) -> int:
    """Deprecate documents of ``source`` not present in ``active_ids``; return count."""
    active = set(active_ids)
    result = await session.execute(
        select(Document).where(
            Document.source_id == source.id,
            Document.status != DocStatus.deprecated,
        )
    )
    pruned = 0
    for doc in result.scalars().all():
        if doc.external_id in active:
            continue
        doc.status = DocStatus.deprecated
        doc.updated_at = datetime.now(UTC)
        pruned += 1
        await write_audit(
            session,
            None,
            "source.prune",
            "document",
            str(doc.id),
            {"source_id": str(source.id), "external_id": doc.external_id},
        )
    return pruned


async def sync_source(session: AsyncSession, source: Source, *, trigger: str = "manual") -> int:
    """Sync one source; return the number of documents upserted (new + changed).

    Opens a :class:`SyncRun`, processes each connector item in isolation, skips
    unchanged documents, prunes vanished ones (when the connector can enumerate),
    and finalizes the run. >50% item failures mark the source (and run) errored.
    Fetch/normalize-level failures mark the source errored without propagating.
    """
    source_id = str(source.id)
    redis_client = _redis_client()
    if not await _acquire_lock(redis_client, source_id):
        logger.info("sync_source_locked", source_id=source_id, source_name=source.name)
        await _close_redis(redis_client)
        return 0

    try:
        return await _run_sync(session, source, trigger, redis_client)
    finally:
        await _release_lock(redis_client, source_id)
        await _close_redis(redis_client)


async def _run_sync(
    session: AsyncSession, source: Source, trigger: str, redis_client: object | None
) -> int:
    """Body of :func:`sync_source`, run under an acquired lock (released by caller)."""
    source_id = str(source.id)
    run = SyncRun(
        source_id=source.id,
        trigger=SyncTrigger(trigger),
        status=SyncRunStatus.running,
        started_at=datetime.now(UTC),
    )
    session.add(run)
    source.sync_status = SyncStatus.syncing
    await session.flush()

    upserted = 0
    skipped = 0
    pruned = 0
    chunks_indexed = 0
    errors: list[dict[str, str]] = []
    item_total = 0
    item_failures = 0

    try:
        connector = get_connector(str(source.type), source.config)
        items = await connector.fetch(source)

        pii_conf = await get_setting(session, SETTINGS_PII_REDACTION, {}) or {}
        pii_enabled = bool(pii_conf.get("enabled"))
        pii_patterns = list(pii_conf.get("patterns") or DEFAULT_PII_PATTERNS)

        for item in items:
            item_total += 1
            try:
                if pii_enabled:
                    clean, hits = redact(item.content, pii_patterns)
                    if hits:
                        item = replace(item, content=clean)
                new_hash = content_hash(item.title, item.content)
                doc = await upsert_raw_item(session, source, item)
                if doc.content_hash == new_hash and await _has_chunks(session, doc):
                    # Unchanged content: freshness/acl/last_activity already refreshed
                    # by the upsert; skip the expensive re-embed.
                    skipped += 1
                    continue
                chunks_indexed += await index_document(session, doc)
                # Only record the hash once indexing succeeded, so a failed item
                # is retried (not skipped) on the next sync.
                doc.content_hash = new_hash
                upserted += 1
            except Exception as exc:  # noqa: BLE001 — isolate one poisoned item
                item_failures += 1
                if len(errors) < MAX_RECORDED_ERRORS:
                    errors.append({"external_id": item.external_id, "error": str(exc)})
                logger.warning(
                    "sync_item_failed",
                    source_id=source_id,
                    external_id=item.external_id,
                    error=str(exc),
                )

        majority_failed = item_total > 0 and item_failures * 2 > item_total
        if majority_failed:
            source.sync_status = SyncStatus.error
            source.last_error = f"{item_failures}/{item_total} items failed"
        else:
            source.sync_status = SyncStatus.ok
            source.last_error = None

        # Pruning: only for LIVE sources (whose API is the source of truth), when the
        # connector can enumerate, and when the run did not error. Demo sources share
        # their source rows with the richer seeded corpus — pruning there would
        # deprecate seeded documents that the fixture connector never emitted.
        if not majority_failed and (source.config or {}).get("mode") == "live":
            active_ids = await list_active_external_ids(connector, source)
            if active_ids is not None:
                pruned = await _prune_missing(session, source, active_ids)

        # Live connectors advance cursors on source.sync_state in place; JSONB
        # mutations need an explicit dirty flag so the change is persisted.
        flag_modified(source, "sync_state")
    except Exception as exc:
        logger.error(
            "source_sync_failed", source_id=source_id, source_name=source.name, error=str(exc)
        )
        source.sync_status = SyncStatus.error
        source.last_error = str(exc)
        if len(errors) < MAX_RECORDED_ERRORS:
            errors.append({"external_id": "", "error": str(exc)})

    source.last_synced_at = datetime.now(UTC)
    source.document_count = await count_where(session, Document, Document.source_id == source.id)

    run.status = SyncRunStatus.error if source.sync_status == SyncStatus.error else SyncRunStatus.ok
    run.finished_at = datetime.now(UTC)
    run.docs_upserted = upserted
    run.docs_skipped = skipped
    run.docs_pruned = pruned
    run.chunks_indexed = chunks_indexed
    run.errors = errors[:MAX_RECORDED_ERRORS]

    await write_audit(
        session,
        None,
        "source.sync",
        "source",
        source_id,
        {
            "status": source.sync_status.value,
            "trigger": trigger,
            "documents_upserted": upserted,
            "documents_skipped": skipped,
            "documents_pruned": pruned,
            "document_count": source.document_count,
            "error": source.last_error,
        },
    )
    await session.flush()

    if run.status == SyncRunStatus.ok:
        await _bump_search_generation(redis_client)

    try:
        from context_engine.reasoning import conflicts as reasoning_conflicts

        await reasoning_conflicts.detect_and_persist_conflicts(session)
    except ImportError:
        logger.warning(
            "conflict_detection_skipped", reason="reasoning.conflicts is not available yet"
        )

    logger.info(
        "source_sync_done",
        source_id=source_id,
        source_name=source.name,
        status=source.sync_status.value,
        trigger=trigger,
        documents=upserted,
        skipped=skipped,
        pruned=pruned,
    )
    return upserted


async def _has_chunks(session: AsyncSession, doc: Document) -> bool:
    """True if the document already has chunk rows (skip re-embed only if so)."""
    from context_engine.storage.models import Chunk

    return await count_where(session, Chunk, Chunk.document_id == doc.id) > 0


async def sync_all(session: AsyncSession, *, trigger: str = "manual") -> dict[str, int]:
    """Sync every enabled source; return ``{source name: upserted doc count}``."""
    result = await session.execute(
        select(Source).where(Source.enabled.is_(True)).order_by(Source.name)
    )
    counts: dict[str, int] = {}
    for source in result.scalars().all():
        counts[source.name] = await sync_source(session, source, trigger=trigger)
    return counts

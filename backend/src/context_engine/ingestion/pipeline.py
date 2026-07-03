"""Source sync pipeline: fetch -> redact -> upsert -> index -> audit."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from context_engine.config.constants import SETTINGS_PII_REDACTION
from context_engine.connectors.base import get_connector
from context_engine.indexing.chunking import index_document
from context_engine.ingestion.normalize import upsert_raw_item
from context_engine.ingestion.pii import DEFAULT_PII_PATTERNS, redact
from context_engine.observability.logging import get_logger
from context_engine.storage.models import Document, Source, SyncStatus
from context_engine.storage.repositories import count_where, get_setting, write_audit

logger = get_logger(__name__)


async def sync_source(session: AsyncSession, source: Source) -> int:
    """Sync one source: upsert + index every connector item; return the doc count.

    Updates ``sync_status``/``last_synced_at``/``last_error``/``document_count``
    and writes a ``source.sync`` audit entry. Fetch/normalize failures mark the
    source as errored instead of propagating, so the status is persisted.
    """
    source.sync_status = SyncStatus.syncing
    await session.flush()

    upserted = 0
    try:
        connector = get_connector(str(source.type))
        items = await connector.fetch(source)

        pii_conf = await get_setting(session, SETTINGS_PII_REDACTION, {}) or {}
        pii_enabled = bool(pii_conf.get("enabled"))
        pii_patterns = list(pii_conf.get("patterns") or DEFAULT_PII_PATTERNS)

        for item in items:
            if pii_enabled:
                clean, hits = redact(item.content, pii_patterns)
                if hits:
                    item = replace(item, content=clean)
            doc = await upsert_raw_item(session, source, item)
            await index_document(session, doc)
            upserted += 1
        source.sync_status = SyncStatus.ok
        source.last_error = None
    except Exception as exc:
        logger.error(
            "source_sync_failed", source_id=str(source.id), source_name=source.name, error=str(exc)
        )
        source.sync_status = SyncStatus.error
        source.last_error = str(exc)

    source.last_synced_at = datetime.now(UTC)
    source.document_count = await count_where(session, Document, Document.source_id == source.id)
    await write_audit(
        session,
        None,
        "source.sync",
        "source",
        str(source.id),
        {
            "status": source.sync_status.value,
            "documents_upserted": upserted,
            "document_count": source.document_count,
            "error": source.last_error,
        },
    )
    await session.flush()

    try:
        from context_engine.reasoning import conflicts as reasoning_conflicts

        await reasoning_conflicts.detect_and_persist_conflicts(session)
    except ImportError:
        logger.warning(
            "conflict_detection_skipped", reason="reasoning.conflicts is not available yet"
        )

    logger.info(
        "source_sync_done",
        source_id=str(source.id),
        source_name=source.name,
        status=source.sync_status.value,
        documents=upserted,
    )
    return upserted


async def sync_all(session: AsyncSession) -> dict[str, int]:
    """Sync every enabled source; return ``{source name: upserted doc count}``."""
    result = await session.execute(
        select(Source).where(Source.enabled.is_(True)).order_by(Source.name)
    )
    counts: dict[str, int] = {}
    for source in result.scalars().all():
        counts[source.name] = await sync_source(session, source)
    return counts

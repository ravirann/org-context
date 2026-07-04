"""Dramatiq actors for source ingestion (registered on the shared broker)."""

from __future__ import annotations

import asyncio
import uuid

import dramatiq

from context_engine.observability.logging import get_logger
from context_engine.observability.worker import get_broker
from context_engine.storage.db import session_scope
from context_engine.storage.models import Source

logger = get_logger(__name__)


async def _sync_source_by_id(source_id: str, trigger: str = "manual") -> None:
    """Open a worker session and run the sync pipeline for one source."""
    from context_engine.ingestion.pipeline import sync_source

    async with session_scope() as session:
        source = await session.get(Source, uuid.UUID(source_id))
        if source is None:
            logger.warning("sync_source_actor_source_missing", source_id=source_id)
            return
        count = await sync_source(session, source, trigger=trigger)
        logger.info(
            "sync_source_actor_finished",
            source_id=source_id,
            source_name=source.name,
            status=source.sync_status.value,
            trigger=trigger,
            documents=count,
        )


@dramatiq.actor(max_retries=3, broker=get_broker())
def sync_source_actor(source_id: str, trigger: str = "manual") -> None:
    """Sync a source by id in a worker process (own session via session_scope)."""
    logger.info("sync_source_actor_started", source_id=source_id, trigger=trigger)
    try:
        asyncio.run(_sync_source_by_id(source_id, trigger))
    except Exception:
        logger.exception("sync_source_actor_failed", source_id=source_id)
        raise

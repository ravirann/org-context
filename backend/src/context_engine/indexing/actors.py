"""Dramatiq actor for full re-indexing (registered on the shared broker)."""

from __future__ import annotations

import asyncio

import dramatiq

from context_engine.observability.logging import get_logger
from context_engine.observability.worker import get_broker
from context_engine.storage.db import session_scope

logger = get_logger(__name__)


async def _reindex_all() -> int:
    """Open a worker session and re-index every active document."""
    from context_engine.indexing.reindex import reindex_all

    async with session_scope() as session:
        return await reindex_all(session)


@dramatiq.actor(max_retries=0, broker=get_broker())
def reindex_actor() -> None:
    """Re-index all documents in a worker process (own session via session_scope)."""
    logger.info("reindex_actor_started")
    try:
        count = asyncio.run(_reindex_all())
    except Exception:
        logger.exception("reindex_actor_failed")
        raise
    logger.info("reindex_actor_finished", documents=count)

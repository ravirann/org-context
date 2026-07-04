"""Ingestion scheduler: periodically enqueue due sources for a scheduled sync.

The scheduler is a lightweight long-running loop (its own process/container). Each
tick it reads every enabled source, selects those whose last sync is older than the
configured interval (or that have never synced), and sends a Dramatiq message per
source with ``trigger="scheduled"``. Actual work happens in the worker; the
scheduler only enqueues.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from context_engine.observability.logging import get_logger
from context_engine.storage.db import session_scope
from context_engine.storage.models import Source
from context_engine.storage.repositories import get_setting

logger = get_logger(__name__)

DEFAULT_SYNC_INTERVAL_MINUTES = 30
"""Fallback cadence when no ``ingestion`` app-setting override is present."""

SETTINGS_INGESTION = "ingestion"
"""App-setting key holding ``{"sync_interval_minutes": int}`` overrides."""


def due_sources(sources: list[Source], now: datetime, default_interval_min: int) -> list[Source]:
    """Return enabled sources whose next scheduled sync is due at ``now``.

    A source is due when it is enabled AND (never synced OR ``last_synced_at`` is
    older than ``default_interval_min`` before ``now``). Pure and deterministic so
    the selection logic can be unit-tested without a database or clock.
    """
    threshold = now - timedelta(minutes=max(1, default_interval_min))
    due: list[Source] = []
    for source in sources:
        if not source.enabled:
            continue
        last = source.last_synced_at
        if last is None or last <= threshold:
            due.append(source)
    return due


async def _interval_minutes() -> int:
    async with session_scope() as session:
        conf = await get_setting(session, SETTINGS_INGESTION, {}) or {}
    value = conf.get("sync_interval_minutes", DEFAULT_SYNC_INTERVAL_MINUTES)
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return DEFAULT_SYNC_INTERVAL_MINUTES


async def _enqueue_due() -> int:
    """Select due sources and enqueue a scheduled sync for each; return the count."""
    from context_engine.ingestion.actors import sync_source_actor

    interval = await _interval_minutes()
    async with session_scope() as session:
        rows = (
            (await session.execute(select(Source).where(Source.enabled.is_(True)))).scalars().all()
        )
    due = due_sources(list(rows), datetime.now(UTC), interval)
    for source in due:
        sync_source_actor.send(str(source.id), trigger="scheduled")
        logger.info("scheduler_enqueued", source_id=str(source.id), source_name=source.name)
    return len(due)


async def run_scheduler(poll_seconds: int = 60) -> None:
    """Run the scheduler loop forever, enqueueing due sources every ``poll_seconds``."""
    logger.info("scheduler_started", poll_seconds=poll_seconds)
    while True:
        try:
            enqueued = await _enqueue_due()
            logger.info("scheduler_tick", enqueued=enqueued)
        except Exception:  # noqa: BLE001 — one bad tick must not kill the loop
            logger.exception("scheduler_tick_failed")
        await asyncio.sleep(poll_seconds)


def main() -> None:
    """Entrypoint: ``python -m context_engine.ingestion.scheduler``."""
    asyncio.run(run_scheduler())


if __name__ == "__main__":
    main()

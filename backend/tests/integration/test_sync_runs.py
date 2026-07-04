"""Integration tests for sync-run robustness: isolation, skip, prune, lock, telemetry.

Exercises PHASE3_CONTRACT §B against the real test DB and the real Redis on :6380
(docker compose). Redis keys are namespaced per source id and cleaned up in teardown.
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

import pytest
import redis.asyncio as aioredis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from context_engine.config.settings import get_settings
from context_engine.connectors.github import GitHubConnector
from context_engine.ingestion import actors
from context_engine.ingestion.pipeline import sync_source
from context_engine.storage import models as m

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


async def _make_source(session: AsyncSession, name: str = "GitHub (demo-org)") -> m.Source:
    source = m.Source(
        type=m.SourceType.github,
        name=name,
        enabled=True,
        config={},
        authority_rank=75,
        freshness_window_days=90,
    )
    session.add(source)
    await session.flush()
    return source


async def _sync_runs(session: AsyncSession, source: m.Source) -> list[m.SyncRun]:
    rows = (
        (
            await session.execute(
                select(m.SyncRun)
                .where(m.SyncRun.source_id == source.id)
                .order_by(m.SyncRun.started_at.desc(), m.SyncRun.id.desc())
            )
        )
        .scalars()
        .all()
    )
    return list(rows)


async def _docs_by_external_id(session: AsyncSession, source: m.Source) -> dict[str, m.Document]:
    result = await session.execute(select(m.Document).where(m.Document.source_id == source.id))
    return {doc.external_id: doc for doc in result.scalars().all()}


# --------------------------------------------------------------------------- #
# SyncRun lifecycle + trigger                                                  #
# --------------------------------------------------------------------------- #


async def test_ok_sync_records_sync_run_and_counts(seeded_session: AsyncSession) -> None:
    source = await _make_source(seeded_session)
    upserted = await sync_source(seeded_session, source, trigger="scheduled")

    runs = await _sync_runs(seeded_session, source)
    assert len(runs) == 1
    run = runs[0]
    assert run.status == m.SyncRunStatus.ok
    assert run.trigger == m.SyncTrigger.scheduled
    assert run.docs_upserted == upserted == 10
    assert run.docs_skipped == 0
    assert run.chunks_indexed >= run.docs_upserted
    assert run.finished_at is not None
    assert run.errors == []


async def test_trigger_defaults_to_manual(seeded_session: AsyncSession) -> None:
    source = await _make_source(seeded_session)
    await sync_source(seeded_session, source)
    runs = await _sync_runs(seeded_session, source)
    assert runs[0].trigger == m.SyncTrigger.manual


# --------------------------------------------------------------------------- #
# Per-item isolation                                                           #
# --------------------------------------------------------------------------- #


async def test_one_poisoned_item_isolated(
    seeded_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = await _make_source(seeded_session)

    # Poison exactly one item by making index_document blow up for its content.
    import context_engine.ingestion.pipeline as pipeline

    real_index = pipeline.index_document
    poisoned_external = "gh-pr-801"

    async def flaky_index(session: AsyncSession, doc: m.Document) -> int:
        if doc.external_id == poisoned_external:
            raise RuntimeError("embedding blew up for this item")
        return await real_index(session, doc)

    monkeypatch.setattr(pipeline, "index_document", flaky_index)

    upserted = await sync_source(seeded_session, source)

    # One item failed; the rest landed. Status stays ok (well under 50% failures).
    assert source.sync_status == m.SyncStatus.ok
    assert upserted == 9

    # Other documents landed with chunks; the poisoned one got no chunks/hash.
    docs = await _docs_by_external_id(seeded_session, source)
    poisoned = docs[poisoned_external]
    poisoned_chunks = (
        await seeded_session.execute(
            select(func.count()).select_from(m.Chunk).where(m.Chunk.document_id == poisoned.id)
        )
    ).scalar_one()
    assert poisoned_chunks == 0
    assert poisoned.content_hash is None

    other = docs["gh-pr-803"]
    other_chunks = (
        await seeded_session.execute(
            select(func.count()).select_from(m.Chunk).where(m.Chunk.document_id == other.id)
        )
    ).scalar_one()
    assert other_chunks >= 1

    run = (await _sync_runs(seeded_session, source))[0]
    assert run.status == m.SyncRunStatus.ok
    assert run.docs_upserted == 9
    assert len(run.errors) == 1
    assert run.errors[0]["external_id"] == poisoned_external
    assert "embedding blew up" in run.errors[0]["error"]


async def test_majority_item_failures_marks_error(
    seeded_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = await _make_source(seeded_session)
    import context_engine.ingestion.pipeline as pipeline

    async def always_fail(session: AsyncSession, doc: m.Document) -> int:
        raise RuntimeError("boom")

    monkeypatch.setattr(pipeline, "index_document", always_fail)
    await sync_source(seeded_session, source)

    assert source.sync_status == m.SyncStatus.error
    run = (await _sync_runs(seeded_session, source))[0]
    assert run.status == m.SyncRunStatus.error
    assert run.docs_upserted == 0
    assert len(run.errors) == 10  # all ten items recorded (<= cap of 50)


# --------------------------------------------------------------------------- #
# Unchanged-content skip                                                       #
# --------------------------------------------------------------------------- #


async def test_unchanged_resync_skips_and_keeps_chunks(seeded_session: AsyncSession) -> None:
    source = await _make_source(seeded_session)
    await sync_source(seeded_session, source)

    docs = await _docs_by_external_id(seeded_session, source)
    probe = docs["gh-pr-803"]
    chunk_ids_before = set(
        (await seeded_session.execute(select(m.Chunk.id).where(m.Chunk.document_id == probe.id)))
        .scalars()
        .all()
    )
    created_before = (
        await seeded_session.execute(
            select(func.min(m.Chunk.created_at)).where(m.Chunk.document_id == probe.id)
        )
    ).scalar_one()

    second = await sync_source(seeded_session, source)

    # No document changed content -> every item skipped, nothing re-embedded.
    assert second == 0
    run = (await _sync_runs(seeded_session, source))[0]
    assert run.docs_skipped == 10
    assert run.docs_upserted == 0
    assert run.chunks_indexed == 0

    chunk_ids_after = set(
        (await seeded_session.execute(select(m.Chunk.id).where(m.Chunk.document_id == probe.id)))
        .scalars()
        .all()
    )
    created_after = (
        await seeded_session.execute(
            select(func.min(m.Chunk.created_at)).where(m.Chunk.document_id == probe.id)
        )
    ).scalar_one()
    assert chunk_ids_after == chunk_ids_before, "chunks must not be re-created on skip"
    assert created_after == created_before


# --------------------------------------------------------------------------- #
# Pruning                                                                      #
# --------------------------------------------------------------------------- #


async def test_pruning_deprecates_vanished_docs(
    seeded_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Pruning only runs for live-mode sources; route "live" to the demo fixture
    # connector so the test stays offline.
    import context_engine.connectors.live as live_pkg

    monkeypatch.setitem(live_pkg.LIVE_CONNECTORS, "github", GitHubConnector)
    source = await _make_source(seeded_session)
    source.config = {"mode": "live"}
    await sync_source(seeded_session, source)

    docs = await _docs_by_external_id(seeded_session, source)
    vanished = docs["gh-pr-830"]
    assert vanished.status != m.DocStatus.deprecated

    # Upstream list now excludes gh-pr-830 (it disappeared).
    async def shrunk_ids(self: GitHubConnector, src: m.Source) -> list[str]:
        return [
            item.external_id for item in await self.fetch(src) if item.external_id != "gh-pr-830"
        ]

    monkeypatch.setattr(GitHubConnector, "list_active_external_ids", shrunk_ids)
    await sync_source(seeded_session, source)

    await seeded_session.refresh(vanished)
    assert vanished.status == m.DocStatus.deprecated

    run = (await _sync_runs(seeded_session, source))[0]
    assert run.docs_pruned == 1

    # Audit entry for the prune.
    audit = (
        await seeded_session.execute(
            select(m.AuditLog).where(
                m.AuditLog.action == "source.prune",
                m.AuditLog.resource_id == str(vanished.id),
            )
        )
    ).scalar_one()
    assert audit.detail["external_id"] == "gh-pr-830"


async def test_no_prune_on_errored_run(
    seeded_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    import context_engine.connectors.live as live_pkg

    monkeypatch.setitem(live_pkg.LIVE_CONNECTORS, "github", GitHubConnector)
    source = await _make_source(seeded_session)
    source.config = {"mode": "live"}
    await sync_source(seeded_session, source)

    # A fetch failure marks the run errored; pruning must be skipped entirely even
    # though the connector could enumerate an empty (everything-vanished) list.
    async def boom(self: GitHubConnector, src: m.Source) -> list[object]:
        raise RuntimeError("upstream exploded")

    monkeypatch.setattr(GitHubConnector, "fetch", boom)
    await sync_source(seeded_session, source)

    run = (await _sync_runs(seeded_session, source))[0]
    assert run.status == m.SyncRunStatus.error
    assert run.docs_pruned == 0
    docs = await _docs_by_external_id(seeded_session, source)
    assert all(d.status != m.DocStatus.deprecated for d in docs.values())


async def test_no_prune_for_demo_mode_sources(
    seeded_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Demo sources share their rows with the seeded corpus: pruning must not run,
    even when the fixture connector can enumerate (it would deprecate seeded docs
    it never emitted)."""
    source = await _make_source(seeded_session)  # config {} -> demo mode
    await sync_source(seeded_session, source)

    async def everything_vanished(self: GitHubConnector, src: m.Source) -> list[str]:
        return []

    monkeypatch.setattr(GitHubConnector, "list_active_external_ids", everything_vanished)
    await sync_source(seeded_session, source)

    run = (await _sync_runs(seeded_session, source))[0]
    assert run.docs_pruned == 0
    docs = await _docs_by_external_id(seeded_session, source)
    assert all(d.status != m.DocStatus.deprecated for d in docs.values())


# --------------------------------------------------------------------------- #
# Redis: search-generation bump + concurrency lock                            #
# --------------------------------------------------------------------------- #


async def test_ok_sync_bumps_search_generation(seeded_session: AsyncSession) -> None:
    client = aioredis.from_url(get_settings().redis_url)
    try:
        await client.delete("ce:search:gen")
        source = await _make_source(seeded_session)
        await sync_source(seeded_session, source)
        gen = await client.get("ce:search:gen")
        assert gen is not None and int(gen) >= 1
    finally:
        await client.delete("ce:search:gen")
        await client.aclose()


async def test_locked_source_returns_without_sync_run(seeded_session: AsyncSession) -> None:
    source = await _make_source(seeded_session)
    lock_key = f"ce:sync-lock:{source.id}"
    client = aioredis.from_url(get_settings().redis_url)
    try:
        await client.set(lock_key, "1", ex=600)
        result = await sync_source(seeded_session, source)
        assert result == 0
        # No SyncRun row is created when the lock is already held.
        assert await _sync_runs(seeded_session, source) == []
        assert source.sync_status != m.SyncStatus.error
    finally:
        await client.delete(lock_key)
        await client.aclose()


async def test_actor_records_scheduled_trigger(
    seeded_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = await _make_source(seeded_session)

    @asynccontextmanager
    async def fake_scope() -> AsyncIterator[AsyncSession]:
        yield seeded_session

    monkeypatch.setattr(actors, "session_scope", fake_scope)
    await actors._sync_source_by_id(str(source.id), "scheduled")

    runs = await _sync_runs(seeded_session, source)
    assert runs[0].trigger == m.SyncTrigger.scheduled


# --------------------------------------------------------------------------- #
# sync-runs API                                                               #
# --------------------------------------------------------------------------- #


async def test_sync_runs_api_shapes(api_client: object, seeded_session: AsyncSession) -> None:
    source = await _make_source(seeded_session, name="API Sync Source")
    await sync_source(seeded_session, source)

    r = await api_client.get(f"/v1/sources/{source.id}/sync-runs")  # type: ignore[attr-defined]
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 1
    run = items[0]
    for key in (
        "id",
        "source_id",
        "trigger",
        "status",
        "started_at",
        "finished_at",
        "docs_upserted",
        "docs_skipped",
        "docs_pruned",
        "chunks_indexed",
        "errors",
        "created_at",
    ):
        assert key in run
    assert run["status"] == "ok"
    assert run["source_id"] == str(source.id)


async def test_sync_runs_api_unknown_source_404(api_client: object) -> None:
    r = await api_client.get(f"/v1/sources/{uuid.uuid4()}/sync-runs")  # type: ignore[attr-defined]
    assert r.status_code == 404


async def test_source_detail_includes_last_sync_run(
    api_client: object, seeded_session: AsyncSession
) -> None:
    source = await _make_source(seeded_session, name="Detail Sync Source")
    await sync_source(seeded_session, source)

    r = await api_client.get("/v1/sources")  # type: ignore[attr-defined]
    assert r.status_code == 200
    match = next(s for s in r.json()["items"] if s["name"] == "Detail Sync Source")
    assert match["last_sync_run"] is not None
    assert match["last_sync_run"]["status"] == "ok"

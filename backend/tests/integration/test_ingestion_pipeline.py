"""End-to-end ingestion pipeline tests against the real test database."""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from context_engine.connectors import get_connector
from context_engine.connectors.github import GitHubConnector
from context_engine.ingestion import actors
from context_engine.ingestion.pipeline import sync_all, sync_source
from context_engine.storage import models as m
from context_engine.storage.repositories import set_setting

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


async def _make_source(
    session: AsyncSession, source_type: str, name: str, rank: int = 75
) -> m.Source:
    source = m.Source(
        type=m.SourceType(source_type),
        name=name,
        enabled=True,
        config={},
        authority_rank=rank,
        freshness_window_days=90,
    )
    session.add(source)
    await session.flush()
    return source


async def _docs_by_external_id(session: AsyncSession, source: m.Source) -> dict[str, m.Document]:
    result = await session.execute(select(m.Document).where(m.Document.source_id == source.id))
    return {doc.external_id: doc for doc in result.scalars().all()}


async def _team_id(session: AsyncSession, name: str) -> uuid.UUID:
    return (await session.execute(select(m.Team.id).where(m.Team.name == name))).scalar_one()


async def _user_id(session: AsyncSession, email: str) -> uuid.UUID:
    return (await session.execute(select(m.User.id).where(m.User.email == email))).scalar_one()


async def test_sync_github_source_end_to_end(seeded_session: AsyncSession) -> None:
    source = await _make_source(seeded_session, "github", "GitHub (demo-org)")
    expected = await get_connector("github").fetch(source)

    count = await sync_source(seeded_session, source)

    assert count == len(expected) == 10
    assert source.sync_status == m.SyncStatus.ok
    assert source.last_error is None
    assert source.last_synced_at is not None
    assert source.document_count == count

    docs = await _docs_by_external_id(seeded_session, source)
    assert set(docs) == {item.external_id for item in expected}

    # ACL mapping: team name -> seeded team id.
    payments_id = await _team_id(seeded_session, "Payments")
    restricted = docs["gh-pr-818"]
    assert restricted.acl_public is False
    assert restricted.acl_team_ids == [str(payments_id)]
    assert restricted.team_id == payments_id

    # ACL mapping: user emails -> seeded user ids.
    user_restricted = docs["gh-code-authmw"]
    admin_id = await _user_id(seeded_session, "admin@demo.dev")
    priya_id = await _user_id(seeded_session, "priya@demo.dev")
    assert user_restricted.acl_public is False
    assert set(user_restricted.acl_user_ids) == {str(admin_id), str(priya_id)}

    # Unknown team names are dropped from the ACL instead of inventing rows.
    platform_restricted = docs["gh-pr-812"]
    assert platform_restricted.acl_public is False
    assert platform_restricted.acl_team_ids == []
    assert platform_restricted.team_id is None

    # Chunks with embeddings and generated tsv exist for every document.
    chunk_count = (
        await seeded_session.execute(
            select(func.count())
            .select_from(m.Chunk)
            .join(m.Document, m.Document.id == m.Chunk.document_id)
            .where(
                m.Document.source_id == source.id,
                m.Chunk.embedding.is_not(None),
                m.Chunk.tsv.is_not(None),
            )
        )
    ).scalar_one()
    assert chunk_count >= count

    # Audit trail.
    audits = (
        (
            await seeded_session.execute(
                select(m.AuditLog).where(
                    m.AuditLog.action == "source.sync",
                    m.AuditLog.resource_id == str(source.id),
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(audits) == 1
    assert audits[0].resource_type == "source"
    assert audits[0].detail["status"] == "ok"
    assert audits[0].detail["documents_upserted"] == count


async def test_resync_is_idempotent_and_bumps_updated_at(seeded_session: AsyncSession) -> None:
    source = await _make_source(seeded_session, "github", "GitHub (demo-org)")
    first_count = await sync_source(seeded_session, source)

    docs = await _docs_by_external_id(seeded_session, source)
    probe = docs["gh-pr-801"]
    first_updated_at = probe.updated_at
    first_doc_ids = {doc.id for doc in docs.values()}

    def total_chunks() -> Select[tuple[int]]:
        return (
            select(func.count())
            .select_from(m.Chunk)
            .join(m.Document, m.Document.id == m.Chunk.document_id)
            .where(m.Document.source_id == source.id)
        )

    chunks_before = (await seeded_session.execute(total_chunks())).scalar_one()

    # Re-syncing identical content skips every item (unchanged-content skip); no
    # documents are re-embedded, so nothing is upserted the second time.
    second_count = await sync_source(seeded_session, source)

    assert second_count == 0
    docs_after = await _docs_by_external_id(seeded_session, source)
    assert len(docs_after) == first_count, "re-sync must not duplicate documents"
    assert {doc.id for doc in docs_after.values()} == first_doc_ids
    assert docs_after["gh-pr-801"].updated_at > first_updated_at
    assert source.document_count == first_count

    chunks_after = (await seeded_session.execute(total_chunks())).scalar_one()
    assert chunks_after == chunks_before, "unchanged re-sync must not touch chunks"


async def test_pii_redaction_applied_when_enabled(seeded_session: AsyncSession) -> None:
    # seed_minimal enables pii_redaction with card/email/ssn patterns.
    source = await _make_source(seeded_session, "github", "GitHub (demo-org)")
    await sync_source(seeded_session, source)

    doc = (await _docs_by_external_id(seeded_session, source))["gh-pr-803"]
    assert "[REDACTED]" in doc.content
    assert "4242424242424242" not in doc.content
    assert "shopper@example.com" not in doc.content


async def test_pii_redaction_skipped_when_disabled(seeded_session: AsyncSession) -> None:
    await set_setting(seeded_session, "pii_redaction", {"enabled": False})
    source = await _make_source(seeded_session, "github", "GitHub Two")
    await sync_source(seeded_session, source)

    doc = (await _docs_by_external_id(seeded_session, source))["gh-pr-803"]
    assert "4242424242424242" in doc.content
    assert "[REDACTED]" not in doc.content


async def test_sync_adr_source_statuses_authority_and_authors(
    seeded_session: AsyncSession,
) -> None:
    source = await _make_source(seeded_session, "adr", "ADR Records", rank=95)
    count = await sync_source(seeded_session, source)
    assert count == 8

    docs = await _docs_by_external_id(seeded_session, source)
    assert all(doc.doc_type == m.DocType.adr for doc in docs.values())

    # metadata deprecated flag wins over freshness.
    assert docs["adr-0008"].status == m.DocStatus.deprecated

    # doc-level authority override vs. source rank default.
    assert docs["adr-0019"].authority_score == pytest.approx(0.99)
    assert docs["adr-0042"].authority_score == pytest.approx(0.95)

    # author + team resolution against seeded rows only.
    assert docs["adr-0042"].author_id == await _user_id(seeded_session, "priya@demo.dev")
    assert docs["adr-0042"].team_id == await _team_id(seeded_session, "Payments")
    assert docs["adr-0031"].author_id is None  # marcus@demo.dev is not seeded
    assert docs["adr-0031"].team_id is None  # Platform team is not seeded

    # stance/topic material for conflict detection survives normalization.
    assert docs["adr-0042"].topic_key == "payments-retry-policy"
    assert docs["adr-0042"].doc_metadata["stance"] == "exponential_backoff"

    # status derives from freshness for everything not explicitly deprecated.
    for doc in docs.values():
        if doc.status == m.DocStatus.deprecated:
            continue
        expected = m.DocStatus.stale if doc.freshness_score < 0.15 else m.DocStatus.active
        assert doc.status == expected
        assert 0.0 <= doc.freshness_score <= 1.0


async def test_sync_error_path_marks_source_errored(
    seeded_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = await _make_source(seeded_session, "github", "GitHub (demo-org)")

    async def boom(self: GitHubConnector, src: m.Source) -> list[object]:
        raise RuntimeError("upstream exploded")

    monkeypatch.setattr(GitHubConnector, "fetch", boom)
    count = await sync_source(seeded_session, source)

    assert count == 0
    assert source.sync_status == m.SyncStatus.error
    assert source.last_error is not None and "upstream exploded" in source.last_error
    assert source.last_synced_at is not None
    assert source.document_count == 0

    audit = (
        await seeded_session.execute(
            select(m.AuditLog).where(
                m.AuditLog.action == "source.sync",
                m.AuditLog.resource_id == str(source.id),
            )
        )
    ).scalar_one()
    assert audit.detail["status"] == "error"
    assert "upstream exploded" in audit.detail["error"]

    # A later successful sync clears the error state.
    monkeypatch.undo()
    count = await sync_source(seeded_session, source)
    assert count == 10
    assert source.sync_status == m.SyncStatus.ok
    assert source.last_error is None


async def test_sync_all_syncs_every_enabled_source(seeded_session: AsyncSession) -> None:
    github = await _make_source(seeded_session, "github", "GitHub (demo-org)")
    disabled = m.Source(type=m.SourceType.jira, name="Disabled Jira", enabled=False, config={})
    seeded_session.add(disabled)
    await seeded_session.flush()

    counts = await sync_all(seeded_session)

    # seed_minimal ships an adr + confluence source; ours joins them.
    assert set(counts) == {"ADR Repository", "Confluence Wiki", "GitHub (demo-org)"}
    assert counts["GitHub (demo-org)"] == 10
    assert counts["ADR Repository"] == 8
    assert counts["Confluence Wiki"] == 8
    assert github.sync_status == m.SyncStatus.ok
    assert disabled.sync_status == m.SyncStatus.idle


async def test_sync_survives_missing_conflict_detection_module(
    seeded_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The reasoning.conflicts import is guarded: sync must succeed without it."""
    import sys

    import context_engine.reasoning as reasoning_pkg

    monkeypatch.delattr(reasoning_pkg, "conflicts", raising=False)
    monkeypatch.setitem(sys.modules, "context_engine.reasoning.conflicts", None)  # type: ignore[arg-type]

    source = await _make_source(seeded_session, "feedback", "Agent Feedback", rank=40)
    count = await sync_source(seeded_session, source)

    assert count == 6
    assert source.sync_status == m.SyncStatus.ok


async def test_actor_helper_syncs_source_via_session_scope(
    seeded_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = await _make_source(seeded_session, "ci", "CI (Jenkins)", rank=50)

    @asynccontextmanager
    async def fake_scope() -> AsyncIterator[AsyncSession]:
        yield seeded_session

    monkeypatch.setattr(actors, "session_scope", fake_scope)
    await actors._sync_source_by_id(str(source.id))

    assert source.sync_status == m.SyncStatus.ok
    assert source.document_count == 8


async def test_actor_helper_tolerates_missing_source(
    seeded_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    @asynccontextmanager
    async def fake_scope() -> AsyncIterator[AsyncSession]:
        yield seeded_session

    monkeypatch.setattr(actors, "session_scope", fake_scope)
    await actors._sync_source_by_id(str(uuid.uuid4()))  # must not raise

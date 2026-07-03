"""Integration tests for conflict detection and persistence."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from context_engine.reasoning.conflicts import (
    conflicts_for_documents,
    detect_and_persist_conflicts,
)
from context_engine.storage.models import (
    Conflict,
    ConflictStatus,
    DocType,
    Document,
    Source,
    SourceType,
    User,
)

ADR_TITLE = "ADR-0042: Exponential backoff with jitter for payment retries"


async def get_source(session: AsyncSession, source_type: SourceType) -> Source:
    return (await session.execute(select(Source).where(Source.type == source_type))).scalar_one()


async def get_doc(session: AsyncSession, title: str) -> Document:
    return (await session.execute(select(Document).where(Document.title == title))).scalar_one()


async def make_topic_doc(
    session: AsyncSession,
    source: Source,
    *,
    topic_key: str,
    title: str,
    content: str,
    stance: str | None = None,
    repo: str = "notifications",
    service: str = "notifications",
) -> Document:
    doc = Document(
        source_id=source.id,
        external_id=f"conflict-test-{uuid.uuid4()}",
        doc_type=DocType.doc,
        title=title,
        content=content,
        url="https://demo.dev/conflict-test",
        repo=repo,
        service=service,
        topic_key=topic_key,
        authority_score=source.authority_rank / 100.0,
        freshness_score=0.8,
        acl_public=True,
        acl_team_ids=[],
        acl_user_ids=[],
        last_activity_at=datetime.now(UTC),
        doc_metadata={"stance": stance} if stance else {},
    )
    session.add(doc)
    await session.flush()
    return doc


async def test_conflicts_for_documents_intersection(seeded_session: AsyncSession) -> None:
    adr_doc = await get_doc(seeded_session, ADR_TITLE)

    found = await conflicts_for_documents(seeded_session, [str(adr_doc.id)])
    assert len(found) == 1
    assert found[0].topic_key == "payments-retry-policy"

    assert await conflicts_for_documents(seeded_session, [str(uuid.uuid4())]) == []
    assert await conflicts_for_documents(seeded_session, []) == []


async def test_detect_creates_conflict_for_divergent_stances(
    seeded_session: AsyncSession,
) -> None:
    adr_source = await get_source(seeded_session, SourceType.adr)
    wiki_source = await get_source(seeded_session, SourceType.confluence)
    a = await make_topic_doc(
        seeded_session,
        adr_source,
        topic_key="email-provider",
        title="ADR-0038: Use SES for transactional email",
        content="Decision: transactional email goes through AWS SES.",
        stance="ses",
    )
    b = await make_topic_doc(
        seeded_session,
        wiki_source,
        topic_key="email-provider",
        title="SendGrid setup guide",
        content="Setup guide for sending transactional email through SendGrid.",
        stance="sendgrid",
    )

    open_count = await detect_and_persist_conflicts(seeded_session)
    assert open_count >= 2  # seeded retry conflict + the new one

    conflict = (
        await seeded_session.execute(select(Conflict).where(Conflict.topic_key == "email-provider"))
    ).scalar_one()
    assert conflict.title == "Conflicting guidance: email-provider"
    assert conflict.status == ConflictStatus.open
    assert conflict.document_ids == sorted([str(a.id), str(b.id)])
    assert conflict.affected == {"repos": ["notifications"], "services": ["notifications"]}


async def test_detect_is_idempotent_and_preserves_resolution(
    seeded_session: AsyncSession,
) -> None:
    await detect_and_persist_conflicts(seeded_session)
    await detect_and_persist_conflicts(seeded_session)

    rows = (
        (
            await seeded_session.execute(
                select(Conflict).where(Conflict.topic_key == "payments-retry-policy")
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1  # no duplicate for the seeded topic

    # Manually resolve, then re-run detection: resolution must be preserved.
    admin = (
        await seeded_session.execute(select(User).where(User.email == "admin@demo.dev"))
    ).scalar_one()
    conflict = rows[0]
    conflict.status = ConflictStatus.resolved
    conflict.resolution_note = "ADR wins; runbook marked stale."
    conflict.resolved_by = admin.id
    conflict.resolved_at = datetime.now(UTC)
    await seeded_session.flush()

    open_count = await detect_and_persist_conflicts(seeded_session)

    refreshed = (
        await seeded_session.execute(
            select(Conflict).where(Conflict.topic_key == "payments-retry-policy")
        )
    ).scalar_one()
    assert refreshed.status == ConflictStatus.resolved
    assert refreshed.resolution_note == "ADR wins; runbook marked stale."
    assert refreshed.resolved_by == admin.id
    assert len(refreshed.document_ids) == 2
    # The resolved conflict no longer counts as open.
    open_topics = (
        (
            await seeded_session.execute(
                select(Conflict.topic_key).where(Conflict.status == ConflictStatus.open)
            )
        )
        .scalars()
        .all()
    )
    assert "payments-retry-policy" not in open_topics
    assert open_count == len(open_topics)


async def test_heuristic_dissimilar_content_without_stance(
    seeded_session: AsyncSession,
) -> None:
    adr_source = await get_source(seeded_session, SourceType.adr)
    wiki_source = await get_source(seeded_session, SourceType.confluence)
    await make_topic_doc(
        seeded_session,
        adr_source,
        topic_key="cache-strategy",
        title="Cache invalidation via pubsub",
        content="Invalidate caches through the pubsub fanout channel on every write.",
    )
    await make_topic_doc(
        seeded_session,
        wiki_source,
        topic_key="cache-strategy",
        title="TTL based cache expiry",
        content="Entries simply expire after sixty seconds; nothing else is required.",
    )
    # Similar-content group (high Jaccard) must NOT be flagged.
    shared = "Deploys ship through the canary pipeline with automatic rollback on errors."
    await make_topic_doc(
        seeded_session,
        adr_source,
        topic_key="deploy-process",
        title="Deploy process A",
        content=shared,
    )
    await make_topic_doc(
        seeded_session,
        wiki_source,
        topic_key="deploy-process",
        title="Deploy process B",
        content=shared + " Rollbacks are automatic.",
    )

    await detect_and_persist_conflicts(seeded_session)

    dissimilar = (
        await seeded_session.execute(select(Conflict).where(Conflict.topic_key == "cache-strategy"))
    ).scalar_one_or_none()
    assert dissimilar is not None
    assert dissimilar.status == ConflictStatus.open

    similar = (
        await seeded_session.execute(select(Conflict).where(Conflict.topic_key == "deploy-process"))
    ).scalar_one_or_none()
    assert similar is None


async def test_same_source_group_is_not_a_conflict(seeded_session: AsyncSession) -> None:
    wiki_source = await get_source(seeded_session, SourceType.confluence)
    await make_topic_doc(
        seeded_session,
        wiki_source,
        topic_key="single-source-topic",
        title="Guide v1",
        content="Alpha guidance completely different wording here.",
        stance="v1",
    )
    await make_topic_doc(
        seeded_session,
        wiki_source,
        topic_key="single-source-topic",
        title="Guide v2",
        content="Totally unrelated zebra text with nothing shared.",
        stance="v2",
    )
    await detect_and_persist_conflicts(seeded_session)
    row = (
        await seeded_session.execute(
            select(Conflict).where(Conflict.topic_key == "single-source-topic")
        )
    ).scalar_one_or_none()
    assert row is None

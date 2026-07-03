"""Integration tests for compile_context: full packets, conflicts, budget, ACL, counters."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from context_engine.context_compiler.compiler import compile_context
from context_engine.indexing.embeddings import embed_text
from context_engine.indexing.tokens import estimate_tokens
from context_engine.storage.models import (
    AuditLog,
    Chunk,
    ContextPacket,
    DocStatus,
    DocType,
    Document,
    Intent,
    Source,
    SourceType,
    User,
)

ADR_TITLE = "ADR-0042: Exponential backoff with jitter for payment retries"
LEGACY_TITLE = "Payments runbook: retry handling (legacy)"
TEAM_RESTRICTED_TITLE = "Payments postmortem: INC-2107 duplicate charges"
USER_RESTRICTED_TITLE = "Secret infra credentials rotation plan"

TASK = "What is the retry policy for payments?"


async def get_user(session: AsyncSession, email: str) -> User:
    return (await session.execute(select(User).where(User.email == email))).scalar_one()


async def get_doc(session: AsyncSession, title: str) -> Document:
    return (await session.execute(select(Document).where(Document.title == title))).scalar_one()


def all_doc_ids(packet: ContextPacket) -> set[str]:
    return {s["document_id"] for s in packet.selected_sources} | {
        r["document_id"] for r in packet.rejected_sources
    }


async def test_full_compile_returns_populated_packet(seeded_session: AsyncSession) -> None:
    admin = await get_user(seeded_session, "admin@demo.dev")
    packet = await compile_context(seeded_session, admin, TASK, service="payments-api")

    assert packet.id is not None
    assert await seeded_session.get(ContextPacket, packet.id) is packet
    assert packet.intent == Intent.question
    assert packet.requested_by == admin.id
    assert packet.selected_sources
    assert packet.citations
    assert packet.citations[0]["marker"] == "S1"
    assert "[S1]" in packet.compiled_context
    assert f"# Task: {TASK}" in packet.compiled_context
    assert packet.token_estimate == estimate_tokens(packet.compiled_context)
    assert 0.05 <= packet.confidence_score <= 1.0
    assert 0.0 <= packet.freshness_score <= 1.0
    assert 0.0 <= packet.authority_score <= 1.0
    assert packet.recommended_tests
    assert packet.acl_notes["blocked_count"] == 0

    # Every selected source is cited with a quote from the used chunk.
    markers = {c["marker"] for c in packet.citations}
    assert markers == {f"S{i + 1}" for i in range(len(packet.selected_sources))}
    assert all(len(c["quote"]) <= 140 for c in packet.citations)

    # Compile is audited.
    audit = (
        await seeded_session.execute(
            select(AuditLog).where(
                AuditLog.action == "context.compile",
                AuditLog.resource_id == str(packet.id),
            )
        )
    ).scalar_one()
    assert audit.actor_id == admin.id


async def test_conflict_loser_rejected_with_note(seeded_session: AsyncSession) -> None:
    admin = await get_user(seeded_session, "admin@demo.dev")
    adr_doc = await get_doc(seeded_session, ADR_TITLE)
    legacy_doc = await get_doc(seeded_session, LEGACY_TITLE)

    packet = await compile_context(seeded_session, admin, TASK, service="payments-api")

    selected_ids = {s["document_id"] for s in packet.selected_sources}
    assert str(adr_doc.id) in selected_ids

    loser = next(r for r in packet.rejected_sources if r["document_id"] == str(legacy_doc.id))
    assert loser["reason"] == f"conflict: superseded by {ADR_TITLE}"

    assert len(packet.conflict_notes) == 1
    note = packet.conflict_notes[0]
    assert note["topic_key"] == "payments-retry-policy"
    assert note["chosen_document_id"] == str(adr_doc.id)
    assert note["conflict_id"]
    # An open conflict surfaces as a risk and dents confidence.
    assert any("payments-retry-policy" in risk for risk in packet.risks)


async def test_token_budget_respected(seeded_session: AsyncSession) -> None:
    admin = await get_user(seeded_session, "admin@demo.dev")
    full = await compile_context(seeded_session, admin, TASK, service="payments-api")
    tight = await compile_context(
        seeded_session, admin, TASK, service="payments-api", max_tokens=150
    )

    assert len(full.selected_sources) > 1
    assert len(tight.selected_sources) < len(full.selected_sources)
    assert any(r["reason"] == "token budget" for r in tight.rejected_sources)
    # Only the sections are budgeted; the packet skeleton adds a small overhead.
    assert tight.token_estimate < full.token_estimate


async def test_deprecated_documents_always_rejected(seeded_session: AsyncSession) -> None:
    admin = await get_user(seeded_session, "admin@demo.dev")
    source = (
        await seeded_session.execute(select(Source).where(Source.type == SourceType.confluence))
    ).scalar_one()
    content = (
        "Deprecated guidance: the retry policy for payments used to be three fixed "
        "attempts. This document is retained for history only."
    )
    doc = Document(
        source_id=source.id,
        external_id=f"deprecated-{uuid.uuid4()}",
        doc_type=DocType.doc,
        title="Old payments retry guidance (deprecated)",
        content=content,
        url="https://demo.dev/deprecated",
        repo="payments-api",
        service="payments-api",
        status=DocStatus.deprecated,
        authority_score=0.9,
        freshness_score=0.9,
        acl_public=True,
        acl_team_ids=[],
        acl_user_ids=[],
        last_activity_at=datetime.now(UTC),
    )
    seeded_session.add(doc)
    await seeded_session.flush()
    seeded_session.add(
        Chunk(
            document_id=doc.id,
            ord=0,
            content=content,
            token_count=estimate_tokens(content),
            embedding=embed_text(content),
        )
    )
    await seeded_session.flush()

    packet = await compile_context(seeded_session, admin, TASK, service="payments-api")
    rejection = next(r for r in packet.rejected_sources if r["document_id"] == str(doc.id))
    assert rejection["reason"] == "deprecated"
    assert str(doc.id) not in {s["document_id"] for s in packet.selected_sources}


async def test_acl_blocked_docs_never_leak_into_packet(seeded_session: AsyncSession) -> None:
    engineer = await get_user(seeded_session, "jade@demo.dev")  # Growth team
    restricted_team = await get_doc(seeded_session, TEAM_RESTRICTED_TITLE)
    restricted_user = await get_doc(seeded_session, USER_RESTRICTED_TITLE)

    packet = await compile_context(seeded_session, engineer, TASK, service="payments-api")

    assert packet.acl_notes["blocked_count"] >= 2
    assert "hidden by ACL" in packet.acl_notes["note"]
    leaked = {str(restricted_team.id), str(restricted_user.id)} & all_doc_ids(packet)
    assert leaked == set()
    assert TEAM_RESTRICTED_TITLE not in packet.compiled_context
    assert any("not accessible" in risk for risk in packet.risks)


async def test_usage_and_rejection_counters_bumped(seeded_session: AsyncSession) -> None:
    admin = await get_user(seeded_session, "admin@demo.dev")
    adr_doc = await get_doc(seeded_session, ADR_TITLE)
    legacy_doc = await get_doc(seeded_session, LEGACY_TITLE)
    usage_before = adr_doc.usage_count
    rejection_before = legacy_doc.rejection_count

    packet = await compile_context(seeded_session, admin, TASK, service="payments-api")
    assert str(adr_doc.id) in {s["document_id"] for s in packet.selected_sources}
    assert str(legacy_doc.id) in {r["document_id"] for r in packet.rejected_sources}

    await seeded_session.refresh(adr_doc)
    await seeded_session.refresh(legacy_doc)
    assert adr_doc.usage_count == usage_before + 1
    assert legacy_doc.rejection_count == rejection_before + 1


async def test_zero_candidates_yields_low_confidence_packet(
    seeded_session: AsyncSession,
) -> None:
    admin = await get_user(seeded_session, "admin@demo.dev")
    packet = await compile_context(
        seeded_session, admin, "Fix the flux capacitor", repo="does-not-exist"
    )

    assert packet.id is not None
    assert packet.intent == Intent.bugfix
    assert packet.selected_sources == []
    assert packet.rejected_sources == []
    assert packet.citations == []
    assert packet.confidence_score == 0.05
    assert "no relevant context found" in packet.risks
    assert "No relevant context found" in packet.compiled_context
    assert packet.acl_notes["blocked_count"] == 0


async def test_intent_boost_prefers_matching_doc_types(seeded_session: AsyncSession) -> None:
    admin = await get_user(seeded_session, "admin@demo.dev")
    # A "question" task boosts doc/adr types; the top selected source must be one.
    packet = await compile_context(seeded_session, admin, TASK, service="payments-api")
    assert packet.selected_sources[0]["doc_type"] in {"doc", "adr"}
    reasons = [r for s in packet.selected_sources for r in s["reasons"]]
    assert any("matches intent 'question'" in r for r in reasons)

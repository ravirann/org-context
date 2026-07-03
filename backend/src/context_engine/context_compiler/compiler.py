"""Context packet compiler.

Algorithm (see docs/ARCHITECTURE.md and docs/INTERFACES.md):
    a. Classify the task intent (rule-based, deterministic).
    b. Retrieve up to 40 hybrid-search candidates via ``search_chunks`` (ACL enforced
       in SQL; the blocked-document count is carried into ``acl_notes``).
    c. Rerank: boost doc_types matching the intent (+0.08), penalize stale docs
       (-0.05). Deprecated documents are always rejected ("deprecated").
    d. Conflict handling: for each open conflict touching the candidates, pick the
       winner by authority x freshness; losers are rejected
       ("conflict: superseded by <winner title>") and a conflict note is recorded.
    e. Low-relevance cutoff: adjusted score < 0.25 -> rejected ("low relevance").
    f. Diversity: at most 4 documents per doc_type ("doc_type diversity cap").
    g. Token budget: ``max_tokens`` or app_settings ``token_budget.max_packet_tokens``
       (default 6000). Sections are packed greedily in score order via
       :func:`pack_budget`; overflow docs are rejected ("token budget").
    h. Compile markdown with [S{i}] citation markers, derive risks and recommended
       tests, compute freshness/authority means and :func:`packet_confidence`.
    i. Persist the ContextPacket (flushed, not committed), bump usage/rejection
       counters on the involved documents, audit ``context.compile``, and wrap the
       whole compile in a Langfuse span (no-op without keys).

Zero candidates still yield a packet: empty selection, confidence 0.05 and the
risk "no relevant context found".
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from context_engine.config.constants import SETTINGS_TOKEN_BUDGET
from context_engine.indexing.tokens import estimate_tokens
from context_engine.observability.langfuse_client import get_langfuse
from context_engine.observability.logging import get_logger
from context_engine.reasoning.conflicts import conflicts_for_documents
from context_engine.reasoning.intent import IntentType, classify_intent
from context_engine.reasoning.scoring import packet_confidence
from context_engine.retrieval.service import SearchFilters, SearchHit, search_chunks
from context_engine.storage.models import Chunk, ConflictStatus, ContextPacket, Document, User
from context_engine.storage.repositories import get_setting, write_audit

logger = get_logger(__name__)

DEFAULT_MAX_PACKET_TOKENS = 6000
CANDIDATE_PAGE_SIZE = 40
INTENT_BOOST = 0.08
STALE_PENALTY = 0.05
LOW_RELEVANCE_CUTOFF = 0.25
MAX_PER_DOC_TYPE = 4
CITATION_QUOTE_CHARS = 140
LOW_FRESHNESS_RISK_CUTOFF = 0.3

INTENT_DOC_TYPE_BOOSTS: dict[IntentType, frozenset[str]] = {
    IntentType.bugfix: frozenset({"incident", "pr", "ci_run"}),
    IntentType.feature: frozenset({"adr", "doc"}),
    IntentType.incident_response: frozenset({"incident", "adr"}),
    IntentType.refactor: frozenset({"adr", "code"}),
    IntentType.question: frozenset({"doc", "adr"}),
    IntentType.unknown: frozenset(),
}

INTENT_TESTS: dict[IntentType, str] = {
    IntentType.bugfix: "Write a failing test reproducing the bug before fixing it.",
    IntentType.feature: "Add unit tests for the new behavior plus a contract test for consumers.",
    IntentType.refactor: "Ensure the existing suite passes before and after the refactor.",
    IntentType.incident_response: "Add a regression check capturing the incident condition.",
    IntentType.question: "Verify the cited guidance against the current code before relying on it.",
    IntentType.unknown: "Cover the changed paths with unit tests.",
}


@dataclass
class _Candidate:
    hit: SearchHit
    adjusted: float
    boosted: bool


def pack_budget(token_costs: Sequence[int], budget: int) -> tuple[list[int], list[int]]:
    """Greedy budget packing: returns (kept_indices, overflow_indices).

    Items are considered in the given (score-descending) order; an item that does
    not fit is skipped, later smaller items may still fit.
    """
    kept: list[int] = []
    overflow: list[int] = []
    used = 0
    for i, cost in enumerate(token_costs):
        if cost <= budget - used:
            kept.append(i)
            used += cost
        else:
            overflow.append(i)
    return kept, overflow


def _rejection(hit: SearchHit, score: float, reason: str) -> dict[str, Any]:
    return {
        "document_id": hit.document_id,
        "title": hit.title,
        "doc_type": hit.doc_type,
        "score": round(score, 4),
        "reason": reason,
    }


def _selection_reasons(cand: _Candidate, intent: IntentType) -> list[str]:
    reasons = [f"hybrid retrieval score {cand.hit.score:.2f}"]
    if cand.boosted:
        reasons.append(f"doc_type '{cand.hit.doc_type}' matches intent '{intent.value}'")
    if cand.hit.authority_score >= 0.8:
        reasons.append("authoritative source")
    if cand.hit.freshness_score >= 0.7:
        reasons.append("recent activity")
    return reasons


def _section(index: int, hit: SearchHit, excerpt: str) -> str:
    where = hit.repo or hit.service or "org"
    return f"### [S{index}] {hit.title} ({hit.doc_type}, {where})\n\n{excerpt}\n\nSource: {hit.url}"


async def _resolve_budget(session: AsyncSession, max_tokens: int | None) -> int:
    if max_tokens is not None:
        return max_tokens
    setting = await get_setting(session, SETTINGS_TOKEN_BUDGET, None)
    if isinstance(setting, dict):
        value = setting.get("max_packet_tokens")
        if isinstance(value, int | float):
            return int(value)
    return DEFAULT_MAX_PACKET_TOKENS


async def _chunk_contents(session: AsyncSession, candidates: list[_Candidate]) -> dict[str, str]:
    chunk_ids = [uuid.UUID(c.hit.chunk_id) for c in candidates]
    if not chunk_ids:
        return {}
    rows = await session.execute(select(Chunk.id, Chunk.content).where(Chunk.id.in_(chunk_ids)))
    return {str(cid): content for cid, content in rows.all()}


def _derive_risks(
    selected: list[_Candidate],
    open_conflict_topics: list[str],
    acl_blocked_count: int,
) -> list[str]:
    risks: list[str] = []
    for topic in open_conflict_topics:
        risks.append(
            f"Open conflict on '{topic}': guidance is contradicted; verify the chosen source."
        )
    if selected:
        mean_freshness = sum(c.hit.freshness_score for c in selected) / len(selected)
        if mean_freshness < LOW_FRESHNESS_RISK_CUTOFF:
            risks.append("guidance may be stale")
    if acl_blocked_count > 0:
        risks.append("some relevant docs were not accessible")
    if not selected:
        risks.append("no relevant context found")
    return risks


def _recommended_tests(intent: IntentType, task: str, service: str | None) -> list[str]:
    tests = [INTENT_TESTS[intent]]
    if service:
        tests.append(f"Run the {service} integration suite.")
    keywords = " ".join(task.split()[:6])
    if keywords:
        tests.append(f"Add a regression test covering: {keywords}")
    return tests


async def compile_context(
    session: AsyncSession,
    user: User,
    task: str,
    repo: str | None = None,
    service: str | None = None,
    max_tokens: int | None = None,
) -> ContextPacket:
    """Compile, persist (flush) and return a ContextPacket for ``task``."""
    langfuse = get_langfuse()
    span = langfuse.span(
        name="context.compile",
        input={"task": task, "repo": repo, "service": service, "user": str(user.id)},
    )
    try:
        packet = await _compile(session, user, task, repo, service, max_tokens)
        span.end(
            output={
                "packet_id": str(packet.id),
                "intent": packet.intent.value,
                "selected": len(packet.selected_sources),
                "rejected": len(packet.rejected_sources),
                "token_estimate": packet.token_estimate,
                "confidence": packet.confidence_score,
            }
        )
        return packet
    except Exception:
        span.end(level="ERROR")
        raise


async def _compile(
    session: AsyncSession,
    user: User,
    task: str,
    repo: str | None,
    service: str | None,
    max_tokens: int | None,
) -> ContextPacket:
    # a. + b. — intent and hybrid retrieval.
    intent = classify_intent(task)
    page = await search_chunks(
        session,
        user,
        task,
        SearchFilters(repo=repo, service=service, page=1, page_size=CANDIDATE_PAGE_SIZE),
    )

    # c. — rerank with intent boosts and status penalties.
    boosted_types = INTENT_DOC_TYPE_BOOSTS[intent]
    candidates: list[_Candidate] = []
    rejected: list[dict[str, Any]] = []
    for hit in page.items:
        boosted = hit.doc_type in boosted_types
        adjusted = hit.score + (INTENT_BOOST if boosted else 0.0)
        if hit.status == "stale":
            adjusted -= STALE_PENALTY
        if hit.status == "deprecated":
            rejected.append(_rejection(hit, adjusted, "deprecated"))
            continue
        candidates.append(_Candidate(hit=hit, adjusted=adjusted, boosted=boosted))
    candidates.sort(key=lambda c: c.adjusted, reverse=True)

    # d. — conflict handling among the surviving candidates.
    conflicts = await conflicts_for_documents(session, [c.hit.document_id for c in candidates])
    open_conflicts = [c for c in conflicts if c.status == ConflictStatus.open]
    conflict_notes: list[dict[str, Any]] = []
    conflict_losers: set[str] = set()
    open_conflict_topics: list[str] = []
    for conflict in open_conflicts:
        involved = [c for c in candidates if c.hit.document_id in set(conflict.document_ids)]
        if not involved:
            continue
        open_conflict_topics.append(conflict.topic_key)
        winner = max(involved, key=lambda c: c.hit.authority_score * c.hit.freshness_score)
        for loser in involved:
            if loser is winner:
                continue
            conflict_losers.add(loser.hit.document_id)
            rejected.append(
                _rejection(
                    loser.hit,
                    loser.adjusted,
                    f"conflict: superseded by {winner.hit.title}",
                )
            )
        conflict_notes.append(
            {
                "conflict_id": str(conflict.id),
                "topic_key": conflict.topic_key,
                "chosen_document_id": winner.hit.document_id,
                "note": (
                    f"Open conflict '{conflict.topic_key}': chose '{winner.hit.title}' "
                    "by authority x freshness."
                ),
            }
        )
    candidates = [c for c in candidates if c.hit.document_id not in conflict_losers]

    # e. — low-relevance cutoff.
    relevant: list[_Candidate] = []
    for cand in candidates:
        if cand.adjusted < LOW_RELEVANCE_CUTOFF:
            rejected.append(_rejection(cand.hit, cand.adjusted, "low relevance"))
        else:
            relevant.append(cand)

    # f. — doc_type diversity cap.
    per_type: dict[str, int] = {}
    diverse: list[_Candidate] = []
    for cand in relevant:
        per_type[cand.hit.doc_type] = per_type.get(cand.hit.doc_type, 0) + 1
        if per_type[cand.hit.doc_type] > MAX_PER_DOC_TYPE:
            rejected.append(_rejection(cand.hit, cand.adjusted, "doc_type diversity cap"))
        else:
            diverse.append(cand)

    # g. — token budget over the rendered sections.
    budget = await _resolve_budget(session, max_tokens)
    contents = await _chunk_contents(session, diverse)
    excerpts = [contents.get(c.hit.chunk_id, c.hit.snippet) for c in diverse]
    costs = [
        estimate_tokens(_section(i + 1, c.hit, excerpt))
        for i, (c, excerpt) in enumerate(zip(diverse, excerpts, strict=True))
    ]
    kept_idx, overflow_idx = pack_budget(costs, budget)
    for i in overflow_idx:
        rejected.append(_rejection(diverse[i].hit, diverse[i].adjusted, "token budget"))
    selected = [diverse[i] for i in kept_idx]
    selected_excerpts = [excerpts[i] for i in kept_idx]

    # h. — markdown, citations, risks, tests, scores.
    sections: list[str] = []
    citations: list[dict[str, Any]] = []
    selected_sources: list[dict[str, Any]] = []
    for i, (cand, excerpt) in enumerate(zip(selected, selected_excerpts, strict=True), start=1):
        sections.append(_section(i, cand.hit, excerpt))
        citations.append(
            {
                "marker": f"S{i}",
                "document_id": cand.hit.document_id,
                "title": cand.hit.title,
                "url": cand.hit.url,
                "quote": excerpt[:CITATION_QUOTE_CHARS],
            }
        )
        selected_sources.append(
            {
                "document_id": cand.hit.document_id,
                "title": cand.hit.title,
                "doc_type": cand.hit.doc_type,
                "score": round(cand.adjusted, 4),
                "reasons": _selection_reasons(cand, intent),
            }
        )

    risks = _derive_risks(selected, open_conflict_topics, page.acl_blocked_count)
    recommended_tests = _recommended_tests(intent, task, service)

    context_body = "\n\n".join(sections) if sections else "_No relevant context found._"
    risk_lines = "\n".join(f"- {r}" for r in risks) if risks else "- None identified."
    compiled_context = (
        f"# Task: {task}\n\n"
        f"Intent: {intent.value}\n\n"
        f"## Context\n\n{context_body}\n\n"
        f"## Open questions / risks\n\n{risk_lines}\n"
    )

    selected_hits = [c.hit for c in selected]
    freshness = (
        sum(h.freshness_score for h in selected_hits) / len(selected_hits) if selected_hits else 0.0
    )
    authority = (
        sum(h.authority_score for h in selected_hits) / len(selected_hits) if selected_hits else 0.0
    )
    confidence = packet_confidence(selected_hits, len(open_conflict_topics))

    # i. — persist, bump counters, audit.
    acl_note = (
        f"{page.acl_blocked_count} matching document(s) were hidden by ACL"
        if page.acl_blocked_count
        else "No documents were blocked by ACL"
    )
    packet = ContextPacket(
        task=task,
        intent=intent,
        repo=repo,
        service=service,
        requested_by=user.id,
        compiled_context=compiled_context,
        selected_sources=selected_sources,
        rejected_sources=rejected,
        citations=citations,
        conflict_notes=conflict_notes,
        acl_notes={"blocked_count": page.acl_blocked_count, "note": acl_note},
        token_estimate=estimate_tokens(compiled_context),
        confidence_score=confidence,
        freshness_score=freshness,
        authority_score=authority,
        risks=risks,
        recommended_tests=recommended_tests,
    )
    session.add(packet)
    await session.flush()

    selected_ids = [uuid.UUID(s["document_id"]) for s in selected_sources]
    rejected_ids = [uuid.UUID(r["document_id"]) for r in rejected]
    if selected_ids:
        await session.execute(
            update(Document)
            .where(Document.id.in_(selected_ids))
            .values(usage_count=Document.usage_count + 1)
            .execution_options(synchronize_session=False)
        )
    if rejected_ids:
        await session.execute(
            update(Document)
            .where(Document.id.in_(rejected_ids))
            .values(rejection_count=Document.rejection_count + 1)
            .execution_options(synchronize_session=False)
        )

    await write_audit(
        session,
        user.id,
        "context.compile",
        resource_type="context_packet",
        resource_id=str(packet.id),
        detail={
            "task": task,
            "intent": intent.value,
            "selected": len(selected_sources),
            "rejected": len(rejected),
            "acl_blocked": page.acl_blocked_count,
        },
    )
    await session.flush()
    logger.info(
        "context_compiled",
        packet_id=str(packet.id),
        intent=intent.value,
        selected=len(selected_sources),
        rejected=len(rejected),
        confidence=confidence,
    )
    return packet

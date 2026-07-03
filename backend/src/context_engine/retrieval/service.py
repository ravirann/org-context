"""Hybrid retrieval: vector + FTS + freshness + authority, ACL-filtered in SQL.

Scoring (see docs/ARCHITECTURE.md):
    score = w_vec * (1 - cosine_distance)
          + w_fts * ts_rank_normalized
          + w_fresh * documents.freshness_score
          + w_auth * documents.authority_score

Weights come from the ``retrieval_weights`` app setting (defaults below when missing).
Candidate set = chunks matching the FTS query OR ranking in the top-N by vector
distance; scored in SQL, deduped to the best chunk per document in Python, then
paginated (``total`` counts deduped documents). ACL is enforced in SQL via
``repositories.acl_filter_clause``; hidden-but-matching documents are counted in
``acl_blocked_count`` (and audited) without ever being returned.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy import ColumnElement, Float, Select, cast, func, literal, or_, select, true
from sqlalchemy.ext.asyncio import AsyncSession

from context_engine.config.constants import SETTINGS_RETRIEVAL_WEIGHTS
from context_engine.indexing.embeddings import embed_text
from context_engine.observability.logging import get_logger
from context_engine.storage.models import Chunk, Document, Source, User
from context_engine.storage.repositories import acl_filter_clause, get_setting, write_audit

logger = get_logger(__name__)

DEFAULT_WEIGHTS: dict[str, float] = {
    "vector": 0.45,
    "fts": 0.25,
    "freshness": 0.15,
    "authority": 0.15,
}

VECTOR_CANDIDATE_LIMIT = 200
"""How many chunks the vector leg contributes to the candidate set."""

MAX_SCAN_ROWS = 1000
"""Upper bound on scored rows fetched before dedupe/pagination."""

SNIPPET_WIDTH = 240


@dataclass
class SearchFilters:
    doc_types: list[str] | None = None
    source_ids: list[str] | None = None
    repo: str | None = None
    service: str | None = None
    status: str | None = None
    page: int = 1
    page_size: int = 20


@dataclass
class SearchHit:
    document_id: str
    chunk_id: str
    title: str
    doc_type: str
    source_name: str
    snippet: str
    score: float
    url: str
    repo: str | None
    service: str | None
    status: str
    freshness_score: float
    authority_score: float
    last_activity_at: datetime


@dataclass
class SearchPage:
    items: list[SearchHit] = field(default_factory=list)
    total: int = 0
    acl_blocked_count: int = 0


def build_snippet(content: str, query: str, width: int = SNIPPET_WIDTH) -> str:
    """Trim ``content`` to roughly ``width`` chars around the first query-term hit."""
    text = " ".join(content.split())
    if len(text) <= width:
        return text
    terms = [t for t in re.findall(r"\w+", query.lower()) if len(t) > 2]
    lowered = text.lower()
    pos = -1
    for term in terms:
        found = lowered.find(term)
        if found != -1 and (pos == -1 or found < pos):
            pos = found
    if pos <= 0:
        return text[:width].rstrip() + "…"
    start = max(0, pos - width // 3)
    end = min(len(text), start + width)
    snippet = text[start:end].strip()
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(text) else ""
    return f"{prefix}{snippet}{suffix}"


async def _load_weights(session: AsyncSession) -> dict[str, float]:
    raw = await get_setting(session, SETTINGS_RETRIEVAL_WEIGHTS, None)
    weights = dict(DEFAULT_WEIGHTS)
    if isinstance(raw, dict):
        for key in weights:
            value = raw.get(key)
            if isinstance(value, int | float):
                weights[key] = float(value)
    return weights


def _filter_clauses(filters: SearchFilters) -> list[ColumnElement[bool]]:
    clauses: list[ColumnElement[bool]] = []
    if filters.doc_types:
        clauses.append(Document.doc_type.in_(filters.doc_types))
    if filters.source_ids:
        clauses.append(Document.source_id.in_([uuid.UUID(s) for s in filters.source_ids]))
    if filters.repo:
        clauses.append(Document.repo == filters.repo)
    if filters.service:
        clauses.append(Document.service == filters.service)
    if filters.status:
        clauses.append(Document.status == filters.status)
    return clauses


def _count_documents_stmt(clauses: list[ColumnElement[bool]]) -> Select[tuple[int]]:
    return (
        select(func.count(func.distinct(Document.id)))
        .select_from(Chunk)
        .join(Document, Chunk.document_id == Document.id)
        .where(*clauses)
    )


async def search_chunks(
    session: AsyncSession, user: User, query: str, filters: SearchFilters
) -> SearchPage:
    """Hybrid ACL-enforced search over chunks, one hit per document."""
    weights = await _load_weights(session)
    q = query.strip()
    filter_clauses = _filter_clauses(filters)
    acl_clause = acl_filter_clause(user)

    vec_score: ColumnElement[float]
    fts_score: ColumnElement[float]
    match_clause: ColumnElement[bool]
    if q:
        qvec = embed_text(q)
        tsq = func.plainto_tsquery("english", q)
        vector_candidates = (
            select(Chunk.id)
            .where(Chunk.embedding.is_not(None))
            .order_by(Chunk.embedding.cosine_distance(qvec))
            .limit(VECTOR_CANDIDATE_LIMIT)
            .correlate(None)
        )
        match_clause = or_(Chunk.tsv.op("@@")(tsq), Chunk.id.in_(vector_candidates))
        vec_score = func.coalesce(literal(1.0) - Chunk.embedding.cosine_distance(qvec), 0.0)
        rank = func.coalesce(func.ts_rank(Chunk.tsv, tsq), 0.0)
        fts_score = cast(rank / (rank + literal(1.0)), Float)
    else:
        # Empty/whitespace query: no FTS/vector legs; recent + authoritative docs win.
        match_clause = true()
        vec_score = literal(0.0)
        fts_score = literal(0.0)

    score_expr = (
        weights["vector"] * vec_score
        + weights["fts"] * fts_score
        + weights["freshness"] * Document.freshness_score
        + weights["authority"] * Document.authority_score
    ).label("score")

    stmt = (
        select(
            Chunk.id.label("chunk_id"),
            Chunk.content.label("chunk_content"),
            Document.id.label("document_id"),
            Document.title,
            Document.doc_type,
            Document.url,
            Document.repo,
            Document.service,
            Document.status,
            Document.freshness_score,
            Document.authority_score,
            Document.last_activity_at,
            Source.name.label("source_name"),
            score_expr,
        )
        .join(Document, Chunk.document_id == Document.id)
        .join(Source, Document.source_id == Source.id)
        .where(match_clause, acl_clause, *filter_clauses)
        .order_by(score_expr.desc(), Document.last_activity_at.desc(), Chunk.id)
        .limit(MAX_SCAN_ROWS)
    )
    rows = (await session.execute(stmt)).all()

    # Dedupe: keep the best-scored chunk per document (rows are score-desc ordered).
    best_per_doc: dict[uuid.UUID, Any] = {}
    for row in rows:
        if row.document_id not in best_per_doc:
            best_per_doc[row.document_id] = row
    deduped = list(best_per_doc.values())
    total = len(deduped)

    page = max(1, filters.page)
    page_size = max(1, filters.page_size)
    start = (page - 1) * page_size
    items = [
        SearchHit(
            document_id=str(row.document_id),
            chunk_id=str(row.chunk_id),
            title=row.title,
            doc_type=row.doc_type.value,
            source_name=row.source_name,
            snippet=build_snippet(row.chunk_content, q),
            score=float(row.score),
            url=row.url,
            repo=row.repo,
            service=row.service,
            status=row.status.value,
            freshness_score=float(row.freshness_score),
            authority_score=float(row.authority_score),
            last_activity_at=row.last_activity_at,
        )
        for row in deduped[start : start + page_size]
    ]

    # ACL-blocked count: identical match predicate with vs without the ACL clause.
    match_clauses = [match_clause, *filter_clauses]
    all_count = (await session.execute(_count_documents_stmt(match_clauses))).scalar_one()
    visible_count = (
        await session.execute(_count_documents_stmt([*match_clauses, acl_clause]))
    ).scalar_one()
    blocked = max(0, int(all_count) - int(visible_count))
    if blocked > 0:
        await write_audit(
            session,
            user.id,
            "acl.blocked",
            resource_type="search",
            detail={"query": query, "blocked": blocked},
        )
        logger.info("acl_blocked", user=str(user.id), blocked=blocked)

    return SearchPage(items=items, total=total, acl_blocked_count=blocked)

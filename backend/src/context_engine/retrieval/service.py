"""Hybrid retrieval: vector + FTS + freshness + authority, ACL-filtered in SQL.

Scoring pipeline (see docs/RETRIEVAL.md):
    1. Candidates — chunks matching ``websearch_to_tsquery`` OR ranking in the vector
       top-N. When the websearch query matches fewer than ``page_size`` documents and
       the query has ≥2 lexemes, an OR-of-lexemes ``to_tsquery`` recall fallback is
       merged in.
    2. SQL pre-cut — rows are scored with the *raw* weighted sum and the top
       ``MAX_SCAN_ROWS`` are fetched (keeps behavior sane on large tables).
    3. Python re-scoring — the vector and FTS legs are min–max normalized across the
       candidate set (zero-range guarded), weighted, summed with the freshness and
       authority legs, then a phrase/title boost (+0.08, capped at 1.0) is applied.
    4. Dedupe — the best-scored chunk per document is kept.
    5. MMR — the top ``3 * page_size`` candidates are reordered for diversity.
    6. Paginate + snippet.

Weights come from the ``retrieval_weights`` app setting; MMR lambda and cache TTL from
``retrieval_extras``. ACL is enforced in SQL via ``repositories.acl_filter_clause``;
hidden-but-matching documents are counted in ``acl_blocked_count`` (and audited)
without ever being returned. Results are cached per-user in Redis (see cache.py); a
``SearchEvent`` telemetry row is recorded for every search (including cache hits).
"""

from __future__ import annotations

import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy import ColumnElement, Float, Select, cast, func, literal, or_, select, true
from sqlalchemy.ext.asyncio import AsyncSession

from context_engine.config.constants import (
    SETTINGS_RETRIEVAL_EXTRAS,
    SETTINGS_RETRIEVAL_WEIGHTS,
)
from context_engine.config.settings import get_settings
from context_engine.indexing.embeddings import embed_query
from context_engine.observability.logging import get_logger
from context_engine.storage.models import Chunk, Document, SearchEvent, Source, User
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

PHRASE_TITLE_BOOST = 0.08
"""Post-normalization boost when the title/chunk contains the exact query phrase."""

DEFAULT_MMR_LAMBDA = 0.7
DEFAULT_CACHE_TTL_SECONDS = 60
MMR_WINDOW_MULTIPLIER = 3
"""MMR is applied over the top ``multiplier * page_size`` deduped candidates."""

TOP_DOCUMENT_IDS_CAP = 10


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


@dataclass
class _Scored:
    """A candidate row carried through Python scoring."""

    row: Any
    vec_raw: float
    fts_raw: float
    embedding: list[float]
    score: float = 0.0


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


def _lexemes(query: str) -> list[str]:
    """Distinct alphanumeric tokens (>1 char), lowercased — used for OR fallback."""
    seen: dict[str, None] = {}
    for token in re.findall(r"\w+", query.lower()):
        if len(token) > 1:
            seen.setdefault(token, None)
    return list(seen)


async def _load_weights(session: AsyncSession) -> dict[str, float]:
    raw = await get_setting(session, SETTINGS_RETRIEVAL_WEIGHTS, None)
    weights = dict(DEFAULT_WEIGHTS)
    if isinstance(raw, dict):
        for key in weights:
            value = raw.get(key)
            if isinstance(value, int | float):
                weights[key] = float(value)
    return weights


async def _load_extras(session: AsyncSession) -> tuple[float, int]:
    """Return ``(mmr_lambda, cache_ttl_seconds)`` from the ``retrieval_extras`` setting."""
    raw = await get_setting(session, SETTINGS_RETRIEVAL_EXTRAS, None)
    mmr_lambda = DEFAULT_MMR_LAMBDA
    cache_ttl = DEFAULT_CACHE_TTL_SECONDS
    if isinstance(raw, dict):
        lam = raw.get("mmr_lambda")
        if isinstance(lam, int | float):
            mmr_lambda = float(lam)
        ttl = raw.get("cache_ttl_seconds")
        if isinstance(ttl, int | float):
            cache_ttl = int(ttl)
    return mmr_lambda, cache_ttl


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


def _minmax(values: list[float]) -> list[float]:
    """Min–max normalize to ``[0, 1]``; zero-range → all zeros (guarded)."""
    if not values:
        return []
    lo = min(values)
    hi = max(values)
    span = hi - lo
    if span <= 0.0:
        return [0.0 for _ in values]
    return [(v - lo) / span for v in values]


def _phrase_boost_applies(row: Any, query: str) -> bool:
    """True when the title or chunk contains the exact query phrase (≥2 words)."""
    phrase = query.strip().lower()
    if len(phrase.split()) < 2:
        return False
    if phrase in (row.title or "").lower():
        return True
    return phrase in (row.chunk_content or "").lower()


async def search_chunks(
    session: AsyncSession, user: User, query: str, filters: SearchFilters
) -> SearchPage:
    """Hybrid ACL-enforced search over chunks, one hit per document.

    Signature is stable; all normalization/MMR/cache/telemetry behavior is internal.
    """
    from context_engine.retrieval import cache

    settings = get_settings()
    started = time.perf_counter()
    q = query.strip()

    cache_on = cache.enabled(settings)
    key: str | None = None
    if cache_on:
        gen = await cache.current_gen(settings)
        key = cache.cache_key(gen, user, q, filters)
        cached = await cache.get(settings, key)
        if cached is not None:
            await _record_event(session, user, query, cached, started, cache_hit=True)
            return cached

    page = await _search(session, user, q, filters)

    if cache_on and key is not None:
        _, cache_ttl = await _load_extras(session)
        await cache.set(settings, key, page, cache_ttl)

    await _record_event(session, user, query, page, started, cache_hit=False)
    return page


async def _search(session: AsyncSession, user: User, q: str, filters: SearchFilters) -> SearchPage:
    weights = await _load_weights(session)
    mmr_lambda, _ = await _load_extras(session)
    filter_clauses = _filter_clauses(filters)
    acl_clause = acl_filter_clause(user)
    page_size = max(1, filters.page_size)

    vec_score: ColumnElement[float]
    fts_score: ColumnElement[float]
    match_clause: ColumnElement[bool]
    if q:
        qvec = await embed_query(q)
        websearch = func.websearch_to_tsquery("english", q)
        vector_candidates = (
            select(Chunk.id)
            .where(Chunk.embedding.is_not(None))
            .order_by(Chunk.embedding.cosine_distance(qvec))
            .limit(VECTOR_CANDIDATE_LIMIT)
            .correlate(None)
        )
        # FTS recall: start from the websearch query. When it matches fewer than
        # page_size documents and the query has ≥2 lexemes, UNION an OR-of-lexemes
        # to_tsquery so multi-term queries still recall partial matches.
        tsq: ColumnElement[Any] = websearch
        fts_clause: ColumnElement[bool] = Chunk.tsv.op("@@")(websearch)
        lexemes = _lexemes(q)
        if len(lexemes) >= 2:
            matched_docs = (
                await session.execute(
                    _count_documents_stmt([fts_clause, acl_clause, *filter_clauses])
                )
            ).scalar_one()
            if int(matched_docs) < page_size:
                or_query = func.to_tsquery("english", " | ".join(lexemes))
                # ts_rank against the combined query so recalled rows get a real leg.
                tsq = websearch.op("||")(or_query)
                fts_clause = or_(fts_clause, Chunk.tsv.op("@@")(or_query))

        match_clause = or_(fts_clause, Chunk.id.in_(vector_candidates))
        vec_score = func.coalesce(literal(1.0) - Chunk.embedding.cosine_distance(qvec), 0.0)
        rank = func.coalesce(func.ts_rank(Chunk.tsv, tsq), 0.0)
        fts_score = cast(rank / (rank + literal(1.0)), Float)
    else:
        # Empty/whitespace query: no FTS/vector legs; recent + authoritative docs win.
        match_clause = true()
        vec_score = literal(0.0)
        fts_score = literal(0.0)

    return await _finish(
        session,
        user,
        q,
        filters,
        weights,
        mmr_lambda,
        match_clause,
        vec_score,
        fts_score,
        acl_clause,
        filter_clauses,
    )


async def _finish(
    session: AsyncSession,
    user: User,
    q: str,
    filters: SearchFilters,
    weights: dict[str, float],
    mmr_lambda: float,
    match_clause: ColumnElement[bool],
    vec_score: ColumnElement[float],
    fts_score: ColumnElement[float],
    acl_clause: ColumnElement[bool],
    filter_clauses: list[ColumnElement[bool]],
) -> SearchPage:
    from context_engine.retrieval.mmr import mmr_order

    page_size = max(1, filters.page_size)

    # Raw weighted score used only as the SQL pre-cut ordering (keeps big tables sane).
    raw_score_expr = (
        weights["vector"] * vec_score
        + weights["fts"] * fts_score
        + weights["freshness"] * Document.freshness_score
        + weights["authority"] * Document.authority_score
    ).label("raw_score")

    stmt = (
        select(
            Chunk.id.label("chunk_id"),
            Chunk.content.label("chunk_content"),
            Chunk.embedding.label("embedding"),
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
            vec_score.label("vec_raw"),
            fts_score.label("fts_raw"),
            raw_score_expr,
        )
        .join(Document, Chunk.document_id == Document.id)
        .join(Source, Document.source_id == Source.id)
        .where(match_clause, acl_clause, *filter_clauses)
        .order_by(raw_score_expr.desc(), Document.last_activity_at.desc(), Chunk.id)
        .limit(MAX_SCAN_ROWS)
    )
    rows = (await session.execute(stmt)).all()

    scored = [
        _Scored(
            row=row,
            vec_raw=float(row.vec_raw),
            fts_raw=float(row.fts_raw),
            embedding=[float(x) for x in row.embedding] if row.embedding is not None else [],
        )
        for row in rows
    ]

    # Min–max normalize the vector and FTS legs across the candidate set, then re-score.
    vec_norm = _minmax([s.vec_raw for s in scored])
    fts_norm = _minmax([s.fts_raw for s in scored])
    for s, vn, fn in zip(scored, vec_norm, fts_norm, strict=True):
        score = (
            weights["vector"] * vn
            + weights["fts"] * fn
            + weights["freshness"] * float(s.row.freshness_score)
            + weights["authority"] * float(s.row.authority_score)
        )
        if _phrase_boost_applies(s.row, q):
            score = min(1.0, score + PHRASE_TITLE_BOOST)
        s.score = score

    scored.sort(
        key=lambda s: (s.score, s.row.last_activity_at, str(s.row.chunk_id)),
        reverse=True,
    )

    # Dedupe: keep the best-scored chunk per document (already score-desc ordered).
    best_per_doc: dict[uuid.UUID, _Scored] = {}
    for s in scored:
        if s.row.document_id not in best_per_doc:
            best_per_doc[s.row.document_id] = s
    deduped = list(best_per_doc.values())
    total = len(deduped)

    # MMR reorder over the top window (relevance vs diversity on stored embeddings).
    window = min(len(deduped), MMR_WINDOW_MULTIPLIER * page_size)
    if window > 1:
        head = deduped[:window]
        order = mmr_order(
            [(str(s.row.chunk_id), s.score, s.embedding) for s in head],
            mmr_lambda,
            window,
        )
        by_chunk = {str(s.row.chunk_id): s for s in head}
        reordered = [by_chunk[cid] for cid in order]
        deduped = reordered + deduped[window:]

    page = max(1, filters.page)
    start = (page - 1) * page_size
    items = [
        SearchHit(
            document_id=str(s.row.document_id),
            chunk_id=str(s.row.chunk_id),
            title=s.row.title,
            doc_type=s.row.doc_type.value,
            source_name=s.row.source_name,
            snippet=build_snippet(s.row.chunk_content, q),
            score=float(s.score),
            url=s.row.url,
            repo=s.row.repo,
            service=s.row.service,
            status=s.row.status.value,
            freshness_score=float(s.row.freshness_score),
            authority_score=float(s.row.authority_score),
            last_activity_at=s.row.last_activity_at,
        )
        for s in deduped[start : start + page_size]
    ]

    blocked = await _acl_blocked_count(session, user, q, match_clause, acl_clause, filter_clauses)
    return SearchPage(items=items, total=total, acl_blocked_count=blocked)


async def _acl_blocked_count(
    session: AsyncSession,
    user: User,
    query: str,
    match_clause: ColumnElement[bool],
    acl_clause: ColumnElement[bool],
    filter_clauses: list[ColumnElement[bool]],
) -> int:
    """Documents matching the query+filters but hidden by ACL; audited when > 0."""
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
    return blocked


async def _record_event(
    session: AsyncSession,
    user: User,
    query: str,
    page: SearchPage,
    started: float,
    *,
    cache_hit: bool,
) -> None:
    """Insert a ``SearchEvent`` telemetry row (flushed, not committed)."""
    took_ms = (time.perf_counter() - started) * 1000.0
    top_ids = [hit.document_id for hit in page.items[:TOP_DOCUMENT_IDS_CAP]]
    event = SearchEvent(
        user_id=user.id,
        query=query,
        result_count=page.total,
        acl_blocked_count=page.acl_blocked_count,
        took_ms=took_ms,
        cache_hit=cache_hit,
        top_document_ids=top_ids,
    )
    session.add(event)
    await session.flush()

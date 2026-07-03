"""Deliberately naive FTS-only retrieval used as the eval comparison baseline.

This is the strawman the context engine must beat: pure Postgres full-text
search (``plainto_tsquery`` + ``ts_rank``) over chunks joined to documents.
No authority or freshness weighting, no conflict handling, no diversity and
no ACL audit trail — but ACL filtering itself IS applied, we never leak
documents a user may not read.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from context_engine.storage.models import Chunk, Document, User
from context_engine.storage.repositories import acl_filter_clause

BASELINE_CONTEXT_MAX_CHARS = 8000
"""Cap for the concatenated baseline context string (~8k chars)."""


@dataclass
class BaselineHit:
    """A single naive-retrieval hit (one chunk)."""

    document_id: str
    title: str
    content: str
    score: float


async def baseline_retrieve(
    session: AsyncSession, user: User, query: str, limit: int = 8
) -> list[BaselineHit]:
    """Naive FTS retrieval: ``plainto_tsquery`` ranked by ``ts_rank`` only."""
    tsquery = func.plainto_tsquery("english", query)
    rank = func.ts_rank(Chunk.tsv, tsquery).label("score")
    stmt = (
        select(Chunk.document_id, Document.title, Chunk.content, rank)
        .join(Document, Chunk.document_id == Document.id)
        .where(Chunk.tsv.op("@@")(tsquery), acl_filter_clause(user))
        .order_by(rank.desc(), Chunk.document_id, Chunk.ord)
        .limit(limit)
    )
    rows = (await session.execute(stmt)).all()
    return [
        BaselineHit(
            document_id=str(row.document_id),
            title=row.title,
            content=row.content,
            score=float(row.score),
        )
        for row in rows
    ]


def build_baseline_context(
    hits: list[BaselineHit], max_chars: int = BASELINE_CONTEXT_MAX_CHARS
) -> str:
    """Concatenate top chunks into a plain baseline context string, capped."""
    parts: list[str] = []
    total = 0
    for hit in hits:
        block = f"## {hit.title}\n{hit.content}"
        parts.append(block)
        total += len(block)
        if total >= max_chars:
            break
    return "\n\n".join(parts)[:max_chars]

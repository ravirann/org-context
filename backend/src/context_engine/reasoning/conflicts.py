"""Conflict detection over topic-keyed documents.

Two documents conflict when they share a ``topic_key``, come from different
sources, and either declare divergent ``doc_metadata['stance']`` values or —
absent any stance metadata — have dissimilar content (token Jaccard < 0.3).
Detected conflicts are upserted by ``topic_key``: existing rows keep their
status/resolution while ``document_ids`` and ``affected`` are refreshed.
"""

from __future__ import annotations

import re
from collections import defaultdict
from itertools import combinations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from context_engine.observability.logging import get_logger
from context_engine.storage.models import Conflict, ConflictStatus, DocStatus, Document

logger = get_logger(__name__)

JACCARD_DISSIMILARITY_THRESHOLD = 0.3


async def conflicts_for_documents(session: AsyncSession, document_ids: list[str]) -> list[Conflict]:
    """Return conflicts whose ``document_ids`` intersect the given document ids."""
    if not document_ids:
        return []
    wanted = set(document_ids)
    rows = (await session.execute(select(Conflict))).scalars().all()
    return [c for c in rows if wanted & set(c.document_ids)]


def token_jaccard(a: str, b: str) -> float:
    """Jaccard similarity of the lowercase word sets of two texts."""
    tokens_a = set(re.findall(r"\w+", a.lower()))
    tokens_b = set(re.findall(r"\w+", b.lower()))
    if not tokens_a and not tokens_b:
        return 1.0
    union = tokens_a | tokens_b
    return len(tokens_a & tokens_b) / len(union)


def _group_conflicts(docs: list[Document]) -> bool:
    """Whether a same-topic document group is internally conflicting."""
    if len({d.source_id for d in docs}) < 2:
        return False
    stances = {d.doc_metadata.get("stance") for d in docs if isinstance(d.doc_metadata, dict)} - {
        None,
        "",
    }
    if stances:
        return len(stances) >= 2
    # No stance metadata: fall back to a content-dissimilarity heuristic.
    return any(
        a.source_id != b.source_id
        and token_jaccard(a.content, b.content) < JACCARD_DISSIMILARITY_THRESHOLD
        for a, b in combinations(docs, 2)
    )


async def detect_and_persist_conflicts(session: AsyncSession) -> int:
    """Scan topic-keyed documents, upsert Conflict rows, return the open-conflict count.

    Deprecated documents are ignored. Dedupe is by ``topic_key``: an existing
    conflict keeps its status/resolution/title while its ``document_ids`` and
    ``affected`` repos/services are refreshed.
    """
    stmt = select(Document).where(
        Document.topic_key.is_not(None), Document.status != DocStatus.deprecated
    )
    docs = (await session.execute(stmt)).scalars().all()
    groups: dict[str, list[Document]] = defaultdict(list)
    for doc in docs:
        if doc.topic_key:
            groups[doc.topic_key].append(doc)

    for topic_key, group in groups.items():
        if len(group) < 2 or not _group_conflicts(group):
            continue
        document_ids = sorted(str(d.id) for d in group)
        affected = {
            "repos": sorted({d.repo for d in group if d.repo}),
            "services": sorted({d.service for d in group if d.service}),
        }
        existing = (
            await session.execute(select(Conflict).where(Conflict.topic_key == topic_key).limit(1))
        ).scalar_one_or_none()
        if existing is not None:
            existing.document_ids = document_ids
            existing.affected = affected
        else:
            session.add(
                Conflict(
                    topic_key=topic_key,
                    title=f"Conflicting guidance: {topic_key}",
                    document_ids=document_ids,
                    status=ConflictStatus.open,
                    affected=affected,
                )
            )
            logger.info("conflict_detected", topic_key=topic_key, documents=len(group))
    await session.flush()

    open_count = (
        await session.execute(
            select(func.count()).select_from(Conflict).where(Conflict.status == ConflictStatus.open)
        )
    ).scalar_one()
    return int(open_count)

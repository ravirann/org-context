"""GET /v1/documents/{id} — ACL-gated document detail with graph/conflict context.

ACL-denied or absent documents return 404 (no existence leak). The ACL block resolves
team ids to team NAMES and exposes only a user_count (never raw user ids) per contract.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from context_engine.api.deps import SessionDep, UserDep
from context_engine.api.routes._common import team_name_map
from context_engine.api.schemas import (
    DocumentAcl,
    DocumentChunk,
    DocumentConflictRef,
    DocumentDetail,
    DocumentSourceRef,
    PacketUsage,
    RelatedDocument,
)
from context_engine.storage.models import (
    Conflict,
    ContextPacket,
    Document,
    Edge,
    Entity,
)
from context_engine.storage.repositories import acl_filter_clause

router = APIRouter(tags=["documents"])

RELATED_LIMIT = 10
PACKET_SCAN_LIMIT = 200


async def _related_documents(session: SessionDep, doc_id: uuid.UUID) -> list[RelatedDocument]:
    """Neighbours reachable via entity edges whose external_ref is a document id."""
    self_ref = str(doc_id)
    self_entities = (
        (await session.execute(select(Entity.id).where(Entity.external_ref == self_ref)))
        .scalars()
        .all()
    )
    if not self_entities:
        return []
    entity_ids = set(self_entities)

    edges = (
        (
            await session.execute(
                select(Edge).where(
                    (Edge.source_entity_id.in_(entity_ids))
                    | (Edge.target_entity_id.in_(entity_ids))
                )
            )
        )
        .scalars()
        .all()
    )
    # neighbour entity id -> relation type
    neighbours: dict[uuid.UUID, str] = {}
    for edge in edges:
        if edge.source_entity_id in entity_ids and edge.target_entity_id not in entity_ids:
            neighbours.setdefault(edge.target_entity_id, edge.type.value)
        elif edge.target_entity_id in entity_ids and edge.source_entity_id not in entity_ids:
            neighbours.setdefault(edge.source_entity_id, edge.type.value)
    if not neighbours:
        return []

    neighbour_entities = (
        (await session.execute(select(Entity).where(Entity.id.in_(neighbours.keys()))))
        .scalars()
        .all()
    )
    # Map neighbour document-ref -> relation.
    ref_to_relation: dict[str, str] = {}
    for ent in neighbour_entities:
        if ent.external_ref:
            ref_to_relation.setdefault(ent.external_ref, neighbours[ent.id])

    doc_ids: list[uuid.UUID] = []
    for ref in ref_to_relation:
        try:
            doc_ids.append(uuid.UUID(ref))
        except ValueError:
            continue
    if not doc_ids:
        return []

    docs = (
        await session.execute(
            select(Document.id, Document.title, Document.doc_type).where(Document.id.in_(doc_ids))
        )
    ).all()
    related: list[RelatedDocument] = []
    for row in docs:
        related.append(
            RelatedDocument(
                id=str(row.id),
                title=row.title,
                doc_type=row.doc_type.value,
                relation=ref_to_relation.get(str(row.id), "references"),
            )
        )
    return related[:RELATED_LIMIT]


async def _conflicts_touching(session: SessionDep, doc_id: uuid.UUID) -> list[DocumentConflictRef]:
    rows = (await session.execute(select(Conflict))).scalars().all()
    ref = str(doc_id)
    return [
        DocumentConflictRef(
            id=str(c.id),
            topic_key=c.topic_key,
            title=c.title,
            status=c.status.value,
        )
        for c in rows
        if ref in (c.document_ids or [])
    ]


async def _packet_usage(session: SessionDep, doc_id: uuid.UUID) -> list[PacketUsage]:
    """Scan recent packets (python-side) for selected/rejected mentions of this doc."""
    ref = str(doc_id)
    packets = (
        (
            await session.execute(
                select(ContextPacket)
                .order_by(ContextPacket.created_at.desc())
                .limit(PACKET_SCAN_LIMIT)
            )
        )
        .scalars()
        .all()
    )
    usage: list[PacketUsage] = []
    for p in packets:
        selected_ids = {s.get("document_id") for s in (p.selected_sources or [])}
        rejected_ids = {r.get("document_id") for r in (p.rejected_sources or [])}
        if ref in selected_ids:
            usage.append(
                PacketUsage(
                    packet_id=str(p.id), task=p.task, created_at=p.created_at, was_selected=True
                )
            )
        elif ref in rejected_ids:
            usage.append(
                PacketUsage(
                    packet_id=str(p.id), task=p.task, created_at=p.created_at, was_selected=False
                )
            )
    return usage


@router.get("/documents/{document_id}", response_model=DocumentDetail)
async def get_document(
    document_id: uuid.UUID, session: SessionDep, user: UserDep
) -> DocumentDetail:
    doc = (
        await session.execute(
            select(Document)
            .where(Document.id == document_id, acl_filter_clause(user))
            .options(
                selectinload(Document.source),
                selectinload(Document.author),
                selectinload(Document.team),
                selectinload(Document.chunks),
            )
        )
    ).scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    team_ids: set[uuid.UUID] = set()
    for raw in doc.acl_team_ids or []:
        try:
            team_ids.add(uuid.UUID(raw))
        except (ValueError, TypeError):
            continue
    team_names_map = await team_name_map(session, team_ids)
    acl = DocumentAcl(
        public=doc.acl_public,
        team_names=[team_names_map[tid] for tid in team_ids if tid in team_names_map],
        user_count=len(doc.acl_user_ids or []),
    )

    chunks = [
        DocumentChunk(id=str(c.id), ord=c.ord, content=c.content, token_count=c.token_count)
        for c in sorted(doc.chunks, key=lambda c: c.ord)
    ]

    related = await _related_documents(session, document_id)
    conflicts = await _conflicts_touching(session, document_id)
    packet_usage = await _packet_usage(session, document_id)

    return DocumentDetail(
        id=str(doc.id),
        title=doc.title,
        content=doc.content,
        doc_type=doc.doc_type.value,
        url=doc.url or None,
        status=doc.status.value,
        repo=doc.repo,
        service=doc.service,
        source=DocumentSourceRef(
            id=str(doc.source.id), name=doc.source.name, type=doc.source.type.value
        ),
        author_name=doc.author.name if doc.author else None,
        team_name=doc.team.name if doc.team else None,
        topic_key=doc.topic_key,
        authority_score=doc.authority_score,
        freshness_score=doc.freshness_score,
        last_activity_at=doc.last_activity_at,
        acl=acl,
        chunks=chunks,
        citations_of=doc.usage_count,
        related=related,
        conflicts=conflicts,
        packet_usage=packet_usage,
    )

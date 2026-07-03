"""Conflict endpoints: list, detail, and resolve."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select

from context_engine.api.deps import SessionDep, UserDep, require_roles
from context_engine.api.routes._common import page_bounds
from context_engine.api.schemas import (
    ConflictAffected,
    ConflictDetail,
    ConflictDocument,
    ConflictOut,
    ConflictResolveRequest,
    Page,
)
from context_engine.storage.models import (
    Conflict,
    ConflictStatus,
    Document,
    Source,
    User,
    UserRole,
)
from context_engine.storage.repositories import write_audit

router = APIRouter(tags=["conflicts"])

EXCERPT_CHARS = 300


def _affected(raw: dict | None) -> ConflictAffected:
    data = raw or {}
    return ConflictAffected(
        repos=list(data.get("repos", [])), services=list(data.get("services", []))
    )


@router.get("/conflicts", response_model=Page[ConflictOut])
async def list_conflicts(
    session: SessionDep,
    user: UserDep,
    status_filter: str | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> Page[ConflictOut]:
    clauses = []
    if status_filter:
        clauses.append(Conflict.status == status_filter)

    total = (
        await session.execute(select(func.count()).select_from(Conflict).where(*clauses))
    ).scalar_one()
    offset, limit = page_bounds(page, page_size)
    rows = (
        (
            await session.execute(
                select(Conflict)
                .where(*clauses)
                .order_by(Conflict.created_at.desc(), Conflict.id)
                .offset(offset)
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    items = [
        ConflictOut(
            id=str(c.id),
            topic_key=c.topic_key,
            title=c.title,
            status=c.status.value,
            document_count=len(c.document_ids or []),
            affected=_affected(c.affected),
            created_at=c.created_at,
        )
        for c in rows
    ]
    return Page(items=items, total=int(total), page=page, page_size=page_size)


async def _conflict_documents(
    session: SessionDep, document_ids: list[str]
) -> list[ConflictDocument]:
    ids: list[uuid.UUID] = []
    for raw in document_ids:
        try:
            ids.append(uuid.UUID(raw))
        except (ValueError, TypeError):
            continue
    if not ids:
        return []
    rows = (
        await session.execute(
            select(Document, Source.name)
            .join(Source, Document.source_id == Source.id)
            .where(Document.id.in_(ids))
        )
    ).all()
    docs: list[ConflictDocument] = []
    for doc, source_name in rows:
        docs.append(
            ConflictDocument(
                id=str(doc.id),
                title=doc.title,
                doc_type=doc.doc_type.value,
                source_name=source_name,
                freshness_score=doc.freshness_score,
                authority_score=doc.authority_score,
                last_activity_at=doc.last_activity_at,
                excerpt=(doc.content or "")[:EXCERPT_CHARS],
            )
        )
    return docs


@router.get("/conflicts/{conflict_id}", response_model=ConflictDetail)
async def get_conflict(
    conflict_id: uuid.UUID, session: SessionDep, user: UserDep
) -> ConflictDetail:
    conflict = await session.get(Conflict, conflict_id)
    if conflict is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    documents = await _conflict_documents(session, conflict.document_ids or [])

    recommended = (
        str(conflict.recommended_document_id) if conflict.recommended_document_id else None
    )
    if recommended is None and documents:
        best = max(documents, key=lambda d: d.authority_score * d.freshness_score)
        recommended = best.id

    resolver_name: str | None = None
    if conflict.resolved_by is not None:
        resolver = await session.get(User, conflict.resolved_by)
        resolver_name = resolver.name if resolver else None

    return ConflictDetail(
        id=str(conflict.id),
        topic_key=conflict.topic_key,
        title=conflict.title,
        status=conflict.status.value,
        affected=_affected(conflict.affected),
        resolution_note=conflict.resolution_note,
        resolved_by_name=resolver_name,
        resolved_at=conflict.resolved_at,
        linked_adr_url=conflict.linked_adr_url,
        recommended_document_id=recommended,
        documents=documents,
    )


@router.post(
    "/conflicts/{conflict_id}/resolve",
    response_model=ConflictDetail,
    dependencies=[Depends(require_roles(UserRole.admin, UserRole.lead))],
)
async def resolve_conflict(
    conflict_id: uuid.UUID,
    body: ConflictResolveRequest,
    session: SessionDep,
    user: UserDep,
) -> ConflictDetail:
    conflict = await session.get(Conflict, conflict_id)
    if conflict is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    conflict.status = ConflictStatus.resolved
    conflict.resolution_note = body.note
    conflict.resolved_by = user.id
    conflict.resolved_at = datetime.now(UTC)
    if body.recommended_document_id:
        conflict.recommended_document_id = uuid.UUID(body.recommended_document_id)
    if body.linked_adr_url is not None:
        conflict.linked_adr_url = body.linked_adr_url

    await write_audit(
        session,
        user.id,
        "conflict.resolve",
        resource_type="conflict",
        resource_id=str(conflict_id),
        detail={"note": body.note},
    )
    await session.flush()
    return await get_conflict(conflict_id, session, user)

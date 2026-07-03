"""Source management endpoints (list/create/delete/sync/patch) with RBAC."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from context_engine.api.deps import SessionDep, UserDep, require_roles
from context_engine.api.schemas import (
    Items,
    SourceCreate,
    SourceOut,
    SourceUpdate,
    SyncEnqueued,
)
from context_engine.ingestion.actors import sync_source_actor
from context_engine.storage.models import Source, SourceType, UserRole
from context_engine.storage.repositories import write_audit

router = APIRouter(tags=["sources"])


def _source_out(source: Source) -> SourceOut:
    return SourceOut.model_validate(
        {
            "id": str(source.id),
            "type": source.type.value,
            "name": source.name,
            "enabled": source.enabled,
            "sync_status": source.sync_status.value,
            "last_synced_at": source.last_synced_at,
            "last_error": source.last_error,
            "document_count": source.document_count,
            "acl_sync_status": source.acl_sync_status.value,
            "authority_rank": source.authority_rank,
            "freshness_window_days": source.freshness_window_days,
        }
    )


@router.get("/sources", response_model=Items[SourceOut])
async def list_sources(session: SessionDep, user: UserDep) -> Items[SourceOut]:
    rows = (await session.execute(select(Source).order_by(Source.name))).scalars().all()
    return Items(items=[_source_out(s) for s in rows])


@router.post(
    "/sources",
    response_model=SourceOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(UserRole.admin))],
)
async def create_source(body: SourceCreate, session: SessionDep, user: UserDep) -> SourceOut:
    source = Source(
        type=SourceType(body.type),
        name=body.name,
        config=body.config or {},
    )
    session.add(source)
    await session.flush()
    await write_audit(
        session, user.id, "source.create", "source", str(source.id), {"name": body.name}
    )
    return _source_out(source)


@router.delete(
    "/sources/{source_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_roles(UserRole.admin))],
)
async def delete_source(source_id: uuid.UUID, session: SessionDep, user: UserDep) -> None:
    source = await session.get(Source, source_id)
    if source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    await session.delete(source)
    await write_audit(session, user.id, "source.delete", "source", str(source_id), {})
    await session.flush()


@router.post(
    "/sources/{source_id}/sync",
    response_model=SyncEnqueued,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_roles(UserRole.admin, UserRole.lead))],
)
async def sync_source(source_id: uuid.UUID, session: SessionDep, user: UserDep) -> SyncEnqueued:
    source = await session.get(Source, source_id)
    if source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    sync_source_actor.send(str(source_id))
    await write_audit(session, user.id, "source.sync", "source", str(source_id), {})
    await session.flush()
    return SyncEnqueued(status="queued")


@router.patch(
    "/sources/{source_id}",
    response_model=SourceOut,
    dependencies=[Depends(require_roles(UserRole.admin))],
)
async def update_source(
    source_id: uuid.UUID, body: SourceUpdate, session: SessionDep, user: UserDep
) -> SourceOut:
    source = await session.get(Source, source_id)
    if source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(source, field, value)
    await write_audit(
        session, user.id, "source.update", "source", str(source_id), {"fields": list(updates)}
    )
    await session.flush()
    return _source_out(source)

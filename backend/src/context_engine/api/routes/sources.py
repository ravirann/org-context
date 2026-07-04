"""Source management endpoints (list/create/delete/sync/patch) with RBAC.

Responses extend the shared ``SourceOut`` shape (additively) with the source's
``config`` (secrets masked) and read-only ``sync_state`` cursors, so live-mode
credentials are never returned in the clear. PATCH accepts a full config; masked
sentinel secret values are ignored so the stored secret survives an edit that did
not intend to rotate it.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

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

SECRET_KEYS = frozenset({"token", "api_token", "client_secret", "password"})
"""Config keys whose values are masked in every response."""

MASK_PREFIX = "•••"
"""Sentinel prefix marking a masked secret (echoed back unchanged on PATCH)."""


def mask_secret(value: str) -> str:
    """Mask a secret to ``•••`` plus its last four characters."""
    tail = value[-4:] if len(value) >= 4 else value
    return f"{MASK_PREFIX}{tail}"


def mask_config(config: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of ``config`` with all secret-key values masked."""
    masked: dict[str, Any] = {}
    for key, val in config.items():
        if key in SECRET_KEYS and isinstance(val, str) and val:
            masked[key] = mask_secret(val)
        else:
            masked[key] = val
    return masked


def merge_config(stored: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    """Merge an incoming config over the stored one, preserving masked secrets.

    A secret value that still carries the mask sentinel means the client did not
    change it, so the stored value is kept; any other value replaces the stored one.
    """
    merged = dict(incoming)
    for key in SECRET_KEYS:
        if key in merged and isinstance(merged[key], str) and merged[key].startswith(MASK_PREFIX):
            if key in stored:
                merged[key] = stored[key]
            else:
                merged.pop(key, None)
    return merged


class SourceDetail(SourceOut):
    """SourceOut plus masked ``config`` and read-only ``sync_state`` (additive)."""

    config: dict[str, Any] = {}
    sync_state: dict[str, Any] = {}


def _source_out(source: Source) -> SourceDetail:
    return SourceDetail.model_validate(
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
            "config": mask_config(source.config or {}),
            "sync_state": dict(source.sync_state or {}),
        }
    )


@router.get("/sources", response_model=Items[SourceDetail])
async def list_sources(session: SessionDep, user: UserDep) -> Items[SourceDetail]:
    from sqlalchemy import select

    rows = (await session.execute(select(Source).order_by(Source.name))).scalars().all()
    return Items(items=[_source_out(s) for s in rows])


@router.post(
    "/sources",
    response_model=SourceDetail,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(UserRole.admin))],
)
async def create_source(body: SourceCreate, session: SessionDep, user: UserDep) -> SourceDetail:
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
    response_model=SourceDetail,
    dependencies=[Depends(require_roles(UserRole.admin))],
)
async def update_source(
    source_id: uuid.UUID, body: SourceUpdate, session: SessionDep, user: UserDep
) -> SourceDetail:
    source = await session.get(Source, source_id)
    if source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    updates = body.model_dump(exclude_unset=True)
    if "config" in updates:
        incoming = updates.pop("config") or {}
        source.config = merge_config(source.config or {}, incoming)
    for field, value in updates.items():
        setattr(source, field, value)
    await write_audit(
        session,
        user.id,
        "source.update",
        "source",
        str(source_id),
        {"fields": list(body.model_dump(exclude_unset=True))},
    )
    await session.flush()
    return _source_out(source)

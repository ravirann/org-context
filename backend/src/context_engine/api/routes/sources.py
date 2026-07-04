"""Source management endpoints (list/create/delete/sync/patch) with RBAC.

Responses extend the shared ``SourceOut`` shape (additively) with the source's
``config`` (secrets masked) and read-only ``sync_state`` cursors, so live-mode
credentials are never returned in the clear. PATCH accepts a full config; masked
sentinel secret values are ignored so the stored secret survives an edit that did
not intend to rotate it.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
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
from context_engine.storage.models import Source, SourceType, SyncRun, UserRole
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


class SyncRunOut(BaseModel):
    """One ingestion sync run: trigger, status, counts, timing, and errors."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    source_id: str
    trigger: str
    status: str
    started_at: datetime
    finished_at: datetime | None = None
    docs_upserted: int
    docs_skipped: int
    docs_pruned: int
    chunks_indexed: int
    errors: list[dict[str, Any]]
    created_at: datetime


class SourceDetail(SourceOut):
    """SourceOut plus masked ``config``, ``sync_state``, and last run (additive)."""

    config: dict[str, Any] = {}
    sync_state: dict[str, Any] = {}
    last_sync_run: SyncRunOut | None = None


def _sync_run_out(run: SyncRun) -> SyncRunOut:
    return SyncRunOut.model_validate(
        {
            "id": str(run.id),
            "source_id": str(run.source_id),
            "trigger": run.trigger.value,
            "status": run.status.value,
            "started_at": run.started_at,
            "finished_at": run.finished_at,
            "docs_upserted": run.docs_upserted,
            "docs_skipped": run.docs_skipped,
            "docs_pruned": run.docs_pruned,
            "chunks_indexed": run.chunks_indexed,
            "errors": list(run.errors or []),
            "created_at": run.created_at,
        }
    )


def _source_out(source: Source, last_sync_run: SyncRun | None = None) -> SourceDetail:
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
            "last_sync_run": _sync_run_out(last_sync_run) if last_sync_run else None,
        }
    )


async def _last_sync_runs(
    session: SessionDep, source_ids: list[uuid.UUID]
) -> dict[uuid.UUID, SyncRun]:
    """Return the newest SyncRun per source id (empty when none exist)."""
    if not source_ids:
        return {}
    rows = (
        (
            await session.execute(
                select(SyncRun)
                .where(SyncRun.source_id.in_(source_ids))
                .order_by(SyncRun.source_id, SyncRun.started_at.desc(), SyncRun.id.desc())
            )
        )
        .scalars()
        .all()
    )
    latest: dict[uuid.UUID, SyncRun] = {}
    for run in rows:
        latest.setdefault(run.source_id, run)
    return latest


@router.get("/sources", response_model=Items[SourceDetail])
async def list_sources(session: SessionDep, user: UserDep) -> Items[SourceDetail]:
    rows = (await session.execute(select(Source).order_by(Source.name))).scalars().all()
    latest = await _last_sync_runs(session, [s.id for s in rows])
    return Items(items=[_source_out(s, latest.get(s.id)) for s in rows])


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


@router.get("/sources/{source_id}/sync-runs", response_model=Items[SyncRunOut])
async def list_sync_runs(
    source_id: uuid.UUID, session: SessionDep, user: UserDep
) -> Items[SyncRunOut]:
    """Return the 20 newest sync runs for a source (any authenticated user)."""
    source = await session.get(Source, source_id)
    if source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    rows = (
        (
            await session.execute(
                select(SyncRun)
                .where(SyncRun.source_id == source_id)
                .order_by(SyncRun.started_at.desc(), SyncRun.id.desc())
                .limit(20)
            )
        )
        .scalars()
        .all()
    )
    return Items(items=[_sync_run_out(r) for r in rows])


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

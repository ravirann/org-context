"""Admin endpoints [admin]: users, teams, api-keys, audit-logs."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from context_engine.api.deps import SessionDep, UserDep, require_roles
from context_engine.api.routes._common import page_bounds
from context_engine.api.schemas import (
    AdminTeam,
    AdminUser,
    ApiKeyOut,
    AuditLogOut,
    Items,
    Page,
)
from context_engine.storage.models import ApiKey, AuditLog, Team, User, UserRole

router = APIRouter(tags=["admin"], dependencies=[Depends(require_roles(UserRole.admin))])


@router.get("/admin/users", response_model=Items[AdminUser])
async def list_users(session: SessionDep, user: UserDep) -> Items[AdminUser]:
    rows = (
        (await session.execute(select(User).options(selectinload(User.team)).order_by(User.name)))
        .scalars()
        .all()
    )
    items = [
        AdminUser(
            id=str(u.id),
            email=u.email,
            name=u.name,
            role=u.role.value,
            team_name=u.team.name if u.team else None,
            is_active=u.is_active,
        )
        for u in rows
    ]
    return Items(items=items)


@router.get("/admin/teams", response_model=Items[AdminTeam])
async def list_teams(session: SessionDep, user: UserDep) -> Items[AdminTeam]:
    count_rows = (
        await session.execute(select(User.team_id, func.count()).group_by(User.team_id))
    ).all()
    counts: dict[uuid.UUID | None, int] = {row[0]: int(row[1]) for row in count_rows}
    rows = (await session.execute(select(Team).order_by(Team.name))).scalars().all()
    items = [
        AdminTeam(id=str(t.id), name=t.name, member_count=int(counts.get(t.id, 0))) for t in rows
    ]
    return Items(items=items)


@router.get("/admin/api-keys", response_model=Items[ApiKeyOut])
async def list_api_keys(session: SessionDep, user: UserDep) -> Items[ApiKeyOut]:
    rows = (
        (
            await session.execute(
                select(ApiKey).options(selectinload(ApiKey.user)).order_by(ApiKey.label)
            )
        )
        .scalars()
        .all()
    )
    items = [
        ApiKeyOut(
            id=str(k.id),
            label=k.label,
            kind=k.kind.value,
            user_name=k.user.name if k.user else "",
            is_active=k.is_active,
            last_used_at=k.last_used_at,
        )
        for k in rows
    ]
    return Items(items=items)


@router.get("/admin/audit-logs", response_model=Page[AuditLogOut])
async def list_audit_logs(
    session: SessionDep,
    user: UserDep,
    action: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> Page[AuditLogOut]:
    clauses = []
    if action:
        clauses.append(AuditLog.action == action)
    total = (
        await session.execute(select(func.count()).select_from(AuditLog).where(*clauses))
    ).scalar_one()
    offset, limit = page_bounds(page, page_size)
    rows = (
        (
            await session.execute(
                select(AuditLog)
                .where(*clauses)
                .options(selectinload(AuditLog.actor))
                .order_by(AuditLog.created_at.desc(), AuditLog.id)
                .offset(offset)
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    items = [
        AuditLogOut(
            id=str(a.id),
            actor_name=a.actor.name if a.actor else None,
            action=a.action,
            resource_type=a.resource_type,
            resource_id=a.resource_id,
            detail=a.detail or {},
            created_at=a.created_at,
        )
        for a in rows
    ]
    return Page(items=items, total=int(total), page=page, page_size=page_size)

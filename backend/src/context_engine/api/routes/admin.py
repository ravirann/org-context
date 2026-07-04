"""Admin endpoints [admin]: users, teams, api-keys, audit-logs."""

from __future__ import annotations

import secrets
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
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
from context_engine.storage.models import ApiKey, ApiKeyKind, AuditLog, Team, User, UserRole
from context_engine.storage.repositories import (
    get_team_by_id,
    get_user_by_email_ci,
    get_user_with_team,
    hash_api_key,
    nullify_team_members,
    write_audit,
)

router = APIRouter(tags=["admin"], dependencies=[Depends(require_roles(UserRole.admin))])


# --------------------------------------------------------------------------- #
# Request / response models local to this module (contract §2, §7: do not add
# these to api/schemas.py — colocate here to avoid parallel-agent conflicts).
# --------------------------------------------------------------------------- #


class UserCreate(BaseModel):
    email: str
    name: str
    role: str
    team_id: str | None = None


class UserUpdate(BaseModel):
    name: str | None = None
    role: str | None = None
    team_id: str | None = None
    is_active: bool | None = None


class TeamCreate(BaseModel):
    name: str
    description: str | None = None


class TeamUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class ApiKeyCreate(BaseModel):
    label: str
    kind: str
    user_id: str
    role_hint: str | None = None


class ApiKeyCreateOut(BaseModel):
    id: str
    label: str
    kind: str
    user_name: str
    raw_key: str


def _admin_user_out(u: User) -> AdminUser:
    return AdminUser(
        id=str(u.id),
        email=u.email,
        name=u.name,
        role=u.role.value,
        team_name=u.team.name if u.team else None,
        is_active=u.is_active,
    )


def _api_key_out(k: ApiKey) -> ApiKeyOut:
    return ApiKeyOut(
        id=str(k.id),
        label=k.label,
        kind=k.kind.value,
        user_name=k.user.name if k.user else "",
        is_active=k.is_active,
        last_used_at=k.last_used_at,
    )


@router.get("/admin/users", response_model=Items[AdminUser])
async def list_users(session: SessionDep, user: UserDep) -> Items[AdminUser]:
    rows = (
        (await session.execute(select(User).options(selectinload(User.team)).order_by(User.name)))
        .scalars()
        .all()
    )
    return Items(items=[_admin_user_out(u) for u in rows])


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
    return Items(items=[_api_key_out(k) for k in rows])


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


# --------------------------------------------------------------------------- #
# Users: create / update                                                       #
# --------------------------------------------------------------------------- #


@router.post("/admin/users", response_model=AdminUser, status_code=status.HTTP_201_CREATED)
async def create_user(body: UserCreate, session: SessionDep, user: UserDep) -> AdminUser:
    existing = await get_user_by_email_ci(session, body.email)
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already in use")
    team_id: uuid.UUID | None = None
    if body.team_id is not None:
        team = await get_team_by_id(session, uuid.UUID(body.team_id))
        if team is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")
        team_id = team.id
    new_user = User(
        email=body.email,
        name=body.name,
        role=UserRole(body.role),
        team_id=team_id,
        is_active=True,
    )
    session.add(new_user)
    await session.flush()
    await write_audit(
        session,
        user.id,
        "user.create",
        "user",
        str(new_user.id),
        {
            "after": {
                "email": new_user.email,
                "name": new_user.name,
                "role": new_user.role.value,
                "team_id": str(team_id) if team_id else None,
            }
        },
    )
    loaded = await get_user_with_team(session, new_user.id)
    assert loaded is not None
    return _admin_user_out(loaded)


@router.patch("/admin/users/{user_id}", response_model=AdminUser)
async def update_user(
    user_id: uuid.UUID, body: UserUpdate, session: SessionDep, user: UserDep
) -> AdminUser:
    target = await get_user_with_team(session, user_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    updates = body.model_dump(exclude_unset=True)

    if target.id == user.id:
        if updates.get("is_active") is False:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Admins cannot deactivate themselves",
            )
        if "role" in updates and updates["role"] != UserRole.admin.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Admins cannot demote themselves",
            )

    before = {
        "name": target.name,
        "role": target.role.value,
        "team_id": str(target.team_id) if target.team_id else None,
        "is_active": target.is_active,
    }

    if "team_id" in updates:
        raw_team_id = updates.pop("team_id")
        if raw_team_id is None:
            target.team_id = None
        else:
            team = await get_team_by_id(session, uuid.UUID(raw_team_id))
            if team is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")
            target.team_id = team.id
        session.expire(target, ["team"])
    if "name" in updates:
        target.name = updates["name"]
    if "role" in updates:
        target.role = UserRole(updates["role"])
    if "is_active" in updates:
        target.is_active = updates["is_active"]

    await session.flush()
    after = {
        "name": target.name,
        "role": target.role.value,
        "team_id": str(target.team_id) if target.team_id else None,
        "is_active": target.is_active,
    }
    await write_audit(
        session, user.id, "user.update", "user", str(target.id), {"before": before, "after": after}
    )
    loaded = await get_user_with_team(session, target.id)
    assert loaded is not None
    return _admin_user_out(loaded)


# --------------------------------------------------------------------------- #
# Teams: create / update / delete                                             #
# --------------------------------------------------------------------------- #


@router.post("/admin/teams", response_model=AdminTeam, status_code=status.HTTP_201_CREATED)
async def create_team(body: TeamCreate, session: SessionDep, user: UserDep) -> AdminTeam:
    team = Team(name=body.name, description=body.description or "")
    session.add(team)
    await session.flush()
    await write_audit(
        session, user.id, "team.create", "team", str(team.id), {"after": {"name": team.name}}
    )
    return AdminTeam(id=str(team.id), name=team.name, member_count=0)


@router.patch("/admin/teams/{team_id}", response_model=AdminTeam)
async def update_team(
    team_id: uuid.UUID, body: TeamUpdate, session: SessionDep, user: UserDep
) -> AdminTeam:
    team = await get_team_by_id(session, team_id)
    if team is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    updates = body.model_dump(exclude_unset=True)
    before = {"name": team.name, "description": team.description}
    if "name" in updates:
        team.name = updates["name"]
    if "description" in updates:
        team.description = updates["description"] or ""
    await session.flush()
    after = {"name": team.name, "description": team.description}
    await write_audit(
        session, user.id, "team.update", "team", str(team.id), {"before": before, "after": after}
    )
    count = (
        await session.execute(select(func.count()).select_from(User).where(User.team_id == team.id))
    ).scalar_one()
    return AdminTeam(id=str(team.id), name=team.name, member_count=int(count))


@router.delete("/admin/teams/{team_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_team(team_id: uuid.UUID, session: SessionDep, user: UserDep) -> None:
    team = await get_team_by_id(session, team_id)
    if team is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    await nullify_team_members(session, team_id)
    await session.delete(team)
    await write_audit(session, user.id, "team.delete", "team", str(team_id), {"name": team.name})
    await session.flush()


# --------------------------------------------------------------------------- #
# API keys: create / revoke                                                   #
# --------------------------------------------------------------------------- #


@router.post("/admin/api-keys", response_model=ApiKeyCreateOut, status_code=status.HTTP_201_CREATED)
async def create_api_key(body: ApiKeyCreate, session: SessionDep, user: UserDep) -> ApiKeyCreateOut:
    try:
        target_user_id = uuid.UUID(body.user_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user_id"
        ) from exc
    target_user = await get_user_with_team(session, target_user_id)
    if target_user is None or not target_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="user_id must exist and be active"
        )
    kind = ApiKeyKind(body.kind)
    raw_key = f"ce_{kind.value}_{secrets.token_hex(16)}"
    api_key = ApiKey(
        key_hash=hash_api_key(raw_key),
        label=body.label,
        kind=kind,
        user_id=target_user.id,
        is_active=True,
    )
    session.add(api_key)
    await session.flush()
    await write_audit(
        session,
        user.id,
        "api_key.create",
        "api_key",
        str(api_key.id),
        {"after": {"label": api_key.label, "kind": kind.value, "user_id": str(target_user.id)}},
    )
    return ApiKeyCreateOut(
        id=str(api_key.id),
        label=api_key.label,
        kind=kind.value,
        user_name=target_user.name,
        raw_key=raw_key,
    )


@router.post("/admin/api-keys/{key_id}/revoke", response_model=ApiKeyOut)
async def revoke_api_key(key_id: uuid.UUID, session: SessionDep, user: UserDep) -> ApiKeyOut:
    stmt = select(ApiKey).where(ApiKey.id == key_id).options(selectinload(ApiKey.user))
    api_key = (await session.execute(stmt)).scalar_one_or_none()
    if api_key is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    was_active = api_key.is_active
    api_key.is_active = False
    await session.flush()
    if was_active:
        await write_audit(session, user.id, "api_key.revoke", "api_key", str(api_key.id), {})
        await session.flush()
    return _api_key_out(api_key)

"""Small typed persistence helpers shared across modules."""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import ColumnElement, func, or_, select, true
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from context_engine.storage.models import (
    ApiKey,
    AppSetting,
    AuditLog,
    Document,
    User,
    UserRole,
)


def hash_api_key(raw_key: str) -> str:
    """Return the sha256 hex digest stored in api_keys.key_hash."""
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


async def get_user_by_api_key(session: AsyncSession, raw_key: str) -> User | None:
    """Resolve a raw bearer key to its active user (with team loaded).

    Updates ``api_keys.last_used_at`` on a successful match.
    """
    key_hash = hash_api_key(raw_key)
    stmt = (
        select(ApiKey)
        .where(ApiKey.key_hash == key_hash, ApiKey.is_active.is_(True))
        .options(selectinload(ApiKey.user).selectinload(User.team))
    )
    api_key = (await session.execute(stmt)).scalar_one_or_none()
    if api_key is None or not api_key.user.is_active:
        return None
    api_key.last_used_at = datetime.now(UTC)
    await session.flush()
    return api_key.user


def acl_filter_clause(user: User) -> ColumnElement[bool]:
    """SQL boolean clause restricting documents to what ``user`` may read.

    Admins see everything; everyone else needs public OR team grant OR direct grant.
    JSONB containment (``@>``) is used against the acl id lists.
    """
    if user.role == UserRole.admin:
        return true()
    clauses: list[ColumnElement[bool]] = [Document.acl_public.is_(True)]
    if user.team_id is not None:
        clauses.append(Document.acl_team_ids.contains([str(user.team_id)]))
    clauses.append(Document.acl_user_ids.contains([str(user.id)]))
    return or_(*clauses)


async def get_setting(session: AsyncSession, key: str, default: Any = None) -> Any:
    """Return the JSON value of an app setting, or ``default`` when missing."""
    row = await session.get(AppSetting, key)
    return default if row is None else row.value


async def set_setting(session: AsyncSession, key: str, value: Any) -> None:
    """Upsert an app setting."""
    row = await session.get(AppSetting, key)
    if row is None:
        session.add(AppSetting(key=key, value=value))
    else:
        row.value = value
        row.updated_at = datetime.now(UTC)
    await session.flush()


async def write_audit(
    session: AsyncSession,
    actor_id: uuid.UUID | None,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    detail: dict[str, Any] | None = None,
) -> AuditLog:
    """Append an audit log entry (flushed, not committed)."""
    entry = AuditLog(
        actor_id=actor_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        detail=detail or {},
    )
    session.add(entry)
    await session.flush()
    return entry


async def count_rows(session: AsyncSession, model: type[Any]) -> int:
    """Return the total row count of a mapped model."""
    result = await session.execute(select(func.count()).select_from(model))
    return int(result.scalar_one())


async def count_where(session: AsyncSession, model: type[Any], *clauses: Any) -> int:
    """Return the row count of a mapped model matching the given clauses."""
    result = await session.execute(select(func.count()).select_from(model).where(*clauses))
    return int(result.scalar_one())

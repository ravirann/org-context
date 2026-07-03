"""Shared helpers for API routers: pagination and name resolution."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from context_engine.storage.models import Team, User


def page_bounds(page: int, page_size: int) -> tuple[int, int]:
    """Return (offset, limit) for a 1-based page and page size."""
    page = max(1, page)
    page_size = max(1, page_size)
    return (page - 1) * page_size, page_size


async def user_name_map(session: AsyncSession, ids: set[uuid.UUID]) -> dict[uuid.UUID, str]:
    """Map user id -> name for the given ids."""
    if not ids:
        return {}
    rows = await session.execute(select(User.id, User.name).where(User.id.in_(ids)))
    return {row.id: row.name for row in rows}


async def team_name_map(session: AsyncSession, ids: set[uuid.UUID]) -> dict[uuid.UUID, str]:
    """Map team id -> name for the given ids."""
    if not ids:
        return {}
    rows = await session.execute(select(Team.id, Team.name).where(Team.id.in_(ids)))
    return {row.id: row.name for row in rows}

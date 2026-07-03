"""Async engine and session management for the context engine."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from context_engine.config.settings import get_settings
from context_engine.storage.models import Base


@lru_cache
def get_engine() -> AsyncEngine:
    """Return the cached application engine bound to settings.database_url."""
    settings = get_settings()
    return create_async_engine(settings.database_url, pool_pre_ping=True)


@lru_cache
def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    """Return the cached session factory bound to the application engine."""
    return async_sessionmaker(get_engine(), expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency yielding a transactional session (commits on success)."""
    factory = get_sessionmaker()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """Context manager for scripts and workers: commit on success, rollback on error.

    Uses a private NullPool engine per scope rather than the cached application
    engine: Dramatiq actors call asyncio.run() per message, and connections pooled
    on a cached engine stay bound to the (dead) loop of a previous invocation,
    raising "attached to a different loop" on reuse. The API path (get_session)
    keeps the cached pooled engine — uvicorn runs a single long-lived loop.
    """
    engine = create_async_engine(get_settings().database_url, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
    finally:
        await engine.dispose()


async def create_all(engine: AsyncEngine | None = None) -> None:
    """Create all tables (test helper; production uses alembic)."""
    engine = engine or get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_all(engine: AsyncEngine | None = None) -> None:
    """Drop all tables (test helper)."""
    engine = engine or get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


def reset_engine_cache() -> None:
    """Clear cached engine/sessionmaker (used when settings change, e.g. in tests)."""
    get_engine.cache_clear()
    get_sessionmaker.cache_clear()

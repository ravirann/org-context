"""FastAPI dependencies: authentication (Bearer key OR session cookie) and role gating."""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from context_engine.api.oidc import SessionError, verify_session_token
from context_engine.config.settings import Settings, get_settings
from context_engine.storage.db import get_session
from context_engine.storage.models import User, UserRole
from context_engine.storage.repositories import get_user_by_api_key

_bearer = HTTPBearer(auto_error=False)

SESSION_COOKIE = "ce_session"

SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def _user_from_cookie(session: AsyncSession, settings: Settings, token: str) -> User | None:
    """Resolve a ``ce_session`` cookie JWT to its active user, or ``None``."""
    try:
        claims = verify_session_token(settings, token)
    except SessionError:
        return None
    try:
        user_id = uuid.UUID(claims.sub)
    except ValueError:
        return None
    stmt = select(User).where(User.id == user_id).options(selectinload(User.team))
    user = (await session.execute(stmt)).scalar_one_or_none()
    if user is None or not user.is_active:
        return None
    return user


async def _resolve_user(
    request: Request,
    session: AsyncSession,
    credentials: HTTPAuthorizationCredentials | None,
) -> User | None:
    """Resolve the request principal from a Bearer key first, then the session cookie."""
    if credentials is not None and credentials.credentials:
        user = await get_user_by_api_key(session, credentials.credentials)
        if user is not None:
            return user
    cookie = request.cookies.get(SESSION_COOKIE)
    if cookie:
        return await _user_from_cookie(session, get_settings(), cookie)
    return None


async def get_current_user(
    request: Request,
    session: SessionDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> User:
    """Resolve the Bearer API key or session cookie to its active user, or raise 401."""
    user = await _resolve_user(request, session, credentials)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user


async def get_optional_user(
    request: Request,
    session: SessionDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> User | None:
    """Resolve the request principal if any valid credentials are present, else ``None``."""
    return await _resolve_user(request, session, credentials)


UserDep = Annotated[User, Depends(get_current_user)]
OptionalUserDep = Annotated[User | None, Depends(get_optional_user)]


def require_roles(*roles: UserRole) -> Callable[[User], Awaitable[User]]:
    """Dependency factory: allow only users whose role is in ``roles`` (else 403)."""
    allowed = set(roles)

    async def _guard(user: UserDep) -> User:
        if user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return user

    return _guard

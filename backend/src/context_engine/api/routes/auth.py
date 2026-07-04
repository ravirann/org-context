"""Authentication endpoints: OIDC login/callback/logout and session bootstrap.

Mode-gated by ``settings.auth_mode`` (see docs/HARDENING_CONTRACT.md §1):

* ``demo`` — the historical Bearer-key world. ``/login`` 409s, ``/session`` reports
  ``auth_mode="demo"`` and whether the request carried valid credentials.
* ``oidc`` — Authorization Code flow via this confidential backend client. ``/login``
  returns the provider ``authorization_url``; the SPA redirects itself. ``/callback``
  exchanges the code, validates the ID token, JIT-provisions, and sets ``ce_session``.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from context_engine.api.app_config import ui_origin
from context_engine.api.deps import SESSION_COOKIE, OptionalUserDep, SessionDep
from context_engine.api.oidc import (
    SessionError,
    build_authorization_url,
    exchange_code_for_tokens,
    issue_session_token,
    issue_state_token,
    validate_id_token,
    verify_state_token,
)
from context_engine.api.schemas import MeOut
from context_engine.config.settings import Settings, get_settings
from context_engine.storage.models import User, UserRole
from context_engine.storage.repositories import write_audit

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginOut(BaseModel):
    authorization_url: str


class SessionOut(BaseModel):
    auth_mode: Literal["demo", "oidc"]
    authenticated: bool
    user: MeOut | None = None


def _me_out(user: User) -> MeOut:
    return MeOut(
        id=str(user.id),
        email=user.email,
        name=user.name,
        role=user.role.value,
        team_name=user.team.name if user.team is not None else None,
    )


@router.get("/login", response_model=LoginOut)
async def login(redirect_after: str | None = None) -> LoginOut:
    """Return the provider authorization URL (oidc) or 409 (demo)."""
    settings = get_settings()
    if settings.auth_mode == "demo":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="auth_mode is demo")
    state = issue_state_token(settings, redirect_after=redirect_after)
    url = await build_authorization_url(settings, state=state)
    return LoginOut(authorization_url=url)


async def _jit_provision(session: SessionDep, settings: Settings, email: str, sub: str) -> User:
    """Create a viewer for a new allowlisted email (contract §1), or raise 403."""
    domain = email.rsplit("@", 1)[-1].lower() if "@" in email else ""
    allowed = settings.allowed_email_domains
    if allowed and domain not in {d.lower() for d in allowed}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="email domain not allowed"
        )
    user = User(
        email=email,
        name=email.split("@", 1)[0],
        role=UserRole.viewer,
        team_id=None,
        is_active=True,
        external_subject=sub,
    )
    session.add(user)
    await session.flush()
    await write_audit(
        session, user.id, "auth.jit_provision", "user", str(user.id), {"email": email}
    )
    return user


@router.get("/callback")
async def callback(request: Request, session: SessionDep, code: str, state: str) -> Response:
    """Exchange the code, validate the ID token, provision, set the cookie, redirect."""
    settings = get_settings()
    if settings.auth_mode == "demo":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="auth_mode is demo")

    try:
        verify_state_token(settings, state)
    except SessionError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"invalid state: {exc}"
        ) from exc

    try:
        tokens = await exchange_code_for_tokens(settings, code=code)
        id_token = tokens["id_token"]
        claims = await validate_id_token(settings, id_token)
    except (SessionError, KeyError, HTTPException) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="token validation failed"
        ) from exc

    email = claims.get("email")
    sub = claims.get("sub")
    if not isinstance(email, str) or not isinstance(sub, str):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="id_token missing claims"
        )

    stmt = select(User).where(User.email == email).options(selectinload(User.team))
    user = (await session.execute(stmt)).scalar_one_or_none()
    if user is None:
        user = await _jit_provision(session, settings, email, sub)
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user is inactive")

    from datetime import UTC, datetime

    user.last_login_at = datetime.now(UTC)
    user.external_subject = sub
    await write_audit(session, user.id, "auth.login", "user", str(user.id), {"email": email})
    await session.flush()

    token = issue_session_token(settings, user_id=str(user.id), email=user.email)
    verified = verify_state_token(settings, state)
    target = verified.get("redirect_after") or ui_origin()
    response = RedirectResponse(url=target, status_code=status.HTTP_302_FOUND)
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        max_age=settings.session_ttl_hours * 3600,
        path="/",
    )
    return response


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout() -> Response:
    """Clear the session cookie."""
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie(key=SESSION_COOKIE, path="/")
    return response


@router.get("/session", response_model=SessionOut)
async def get_session_state(user: OptionalUserDep) -> SessionOut:
    """Bootstrap endpoint: current auth mode and whether the caller is authenticated."""
    settings = get_settings()
    return SessionOut(
        auth_mode=settings.auth_mode,
        authenticated=user is not None,
        user=_me_out(user) if user is not None else None,
    )

"""OIDC auth flow: callback, JIT provisioning, session bootstrap, cookie sessions.

No network: the OIDC provider (discovery, JWKS, token exchange, ID-token validation) is
monkeypatched at the ``routes.auth`` import site. ``CE_AUTH_MODE`` is flipped by clearing
the ``get_settings`` lru_cache with an env override and restoring it afterwards.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Iterator

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from context_engine.api import oidc as oidc_mod
from context_engine.api.routes import auth as auth_route
from context_engine.config.settings import get_settings
from context_engine.storage.models import AuditLog, User, UserRole
from tests.conftest import ADMIN_KEY, auth_headers


def _client(seeded_session: AsyncSession) -> httpx.AsyncClient:
    """A cookie-capable client (no default auth header) against a fresh app."""
    from context_engine.api.app import create_app
    from context_engine.storage.db import get_session as get_session_dep

    app = create_app()

    async def _override_session() -> AsyncIterator[AsyncSession]:
        yield seeded_session

    app.dependency_overrides[get_session_dep] = _override_session
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


@pytest.fixture
def oidc_env() -> Iterator[None]:
    """Flip settings into oidc mode for the duration of a test, then restore."""
    saved = {
        k: os.environ.get(k)
        for k in (
            "CE_AUTH_MODE",
            "CE_OIDC_ISSUER",
            "CE_OIDC_CLIENT_ID",
            "CE_OIDC_CLIENT_SECRET",
            "CE_ALLOWED_EMAIL_DOMAINS",
        )
    }
    os.environ["CE_AUTH_MODE"] = "oidc"
    os.environ["CE_OIDC_ISSUER"] = "https://issuer.test/realms/org-context"
    os.environ["CE_OIDC_CLIENT_ID"] = "org-context-api"
    os.environ["CE_OIDC_CLIENT_SECRET"] = "test-secret"
    os.environ.pop("CE_ALLOWED_EMAIL_DOMAINS", None)
    get_settings.cache_clear()
    try:
        yield
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        get_settings.cache_clear()
        oidc_mod.reset_oidc_cache()


def _mock_provider(monkeypatch: pytest.MonkeyPatch, *, email: str, sub: str = "kc-sub-1") -> None:
    """Patch token exchange + ID-token validation to succeed for ``email``."""

    async def _fake_exchange(settings: object, *, code: str) -> dict[str, str]:
        return {"id_token": f"fake-id-token-for-{email}"}

    async def _fake_validate(settings: object, id_token: str) -> dict[str, str]:
        return {"email": email, "sub": sub}

    async def _fake_authz(
        settings: object, *, state: str, scope: str = "openid email profile"
    ) -> str:
        return f"https://issuer.test/realms/org-context/protocol/openid-connect/auth?state={state}"

    monkeypatch.setattr(auth_route, "exchange_code_for_tokens", _fake_exchange)
    monkeypatch.setattr(auth_route, "validate_id_token", _fake_validate)
    monkeypatch.setattr(auth_route, "build_authorization_url", _fake_authz)


def _valid_state() -> str:
    from context_engine.api.oidc import issue_state_token

    return issue_state_token(get_settings())


# --------------------------------------------------------------------------- #
# demo mode                                                                    #
# --------------------------------------------------------------------------- #


async def test_session_demo_mode_unauthenticated(seeded_session: AsyncSession) -> None:
    async with _client(seeded_session) as client:
        r = await client.get("/v1/auth/session")
    assert r.status_code == 200
    body = r.json()
    assert body == {"auth_mode": "demo", "authenticated": False, "user": None}


async def test_session_demo_mode_with_key(seeded_session: AsyncSession) -> None:
    async with _client(seeded_session) as client:
        r = await client.get("/v1/auth/session", headers=auth_headers(ADMIN_KEY))
    assert r.status_code == 200
    body = r.json()
    assert body["authenticated"] is True
    assert body["user"]["role"] == "admin"


async def test_login_409_in_demo_mode(seeded_session: AsyncSession) -> None:
    async with _client(seeded_session) as client:
        r = await client.get("/v1/auth/login")
    assert r.status_code == 409
    assert r.json() == {"detail": "auth_mode is demo"}


# --------------------------------------------------------------------------- #
# oidc mode                                                                    #
# --------------------------------------------------------------------------- #


async def test_login_returns_authorization_url(
    seeded_session: AsyncSession, oidc_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    _mock_provider(monkeypatch, email="ava@demo.dev")
    async with _client(seeded_session) as client:
        r = await client.get("/v1/auth/login")
    assert r.status_code == 200
    assert (
        "issuer.test/realms/org-context/protocol/openid-connect/auth"
        in (r.json()["authorization_url"])
    )


async def test_session_shape_oidc_unauthenticated(
    seeded_session: AsyncSession, oidc_env: None
) -> None:
    async with _client(seeded_session) as client:
        r = await client.get("/v1/auth/session")
    assert r.status_code == 200
    assert r.json() == {"auth_mode": "oidc", "authenticated": False, "user": None}


async def test_callback_happy_path_sets_cookie(
    seeded_session: AsyncSession, oidc_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    _mock_provider(monkeypatch, email="admin@demo.dev")
    state = _valid_state()
    async with _client(seeded_session) as client:
        r = await client.get("/v1/auth/callback", params={"code": "abc", "state": state})
        assert r.status_code == 302
        assert "ce_session" in r.cookies
        # A subsequent request carrying the cookie resolves the user.
        me = await client.get("/v1/me")
    assert me.status_code == 200
    assert me.json()["email"] == "admin@demo.dev"

    user = (
        await seeded_session.execute(select(User).where(User.email == "admin@demo.dev"))
    ).scalar_one()
    assert user.last_login_at is not None
    assert user.external_subject == "kc-sub-1"


async def test_callback_jit_provisions_viewer_and_audits(
    seeded_session: AsyncSession, oidc_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    _mock_provider(monkeypatch, email="brand.new@demo.dev", sub="kc-new")
    state = _valid_state()
    async with _client(seeded_session) as client:
        r = await client.get("/v1/auth/callback", params={"code": "abc", "state": state})
    assert r.status_code == 302

    user = (
        await seeded_session.execute(select(User).where(User.email == "brand.new@demo.dev"))
    ).scalar_one()
    assert user.role == UserRole.viewer
    audits = (
        (
            await seeded_session.execute(
                select(AuditLog).where(AuditLog.action == "auth.jit_provision")
            )
        )
        .scalars()
        .all()
    )
    assert any(a.detail.get("email") == "brand.new@demo.dev" for a in audits)


async def test_callback_domain_allowlist_403(
    seeded_session: AsyncSession, oidc_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    os.environ["CE_ALLOWED_EMAIL_DOMAINS"] = '["allowed.dev"]'
    get_settings.cache_clear()
    _mock_provider(monkeypatch, email="outsider@evil.dev")
    state = _valid_state()
    async with _client(seeded_session) as client:
        r = await client.get("/v1/auth/callback", params={"code": "abc", "state": state})
    assert r.status_code == 403


async def test_callback_invalid_state_400(
    seeded_session: AsyncSession, oidc_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    _mock_provider(monkeypatch, email="admin@demo.dev")
    async with _client(seeded_session) as client:
        r = await client.get(
            "/v1/auth/callback", params={"code": "abc", "state": "not-a-valid-state"}
        )
    assert r.status_code == 400


async def test_callback_invalid_id_token_400(
    seeded_session: AsyncSession, oidc_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from context_engine.api.oidc import SessionError

    async def _fake_exchange(settings: object, *, code: str) -> dict[str, str]:
        return {"id_token": "bad"}

    async def _fake_validate(settings: object, id_token: str) -> dict[str, str]:
        raise SessionError("bad signature")

    monkeypatch.setattr(auth_route, "exchange_code_for_tokens", _fake_exchange)
    monkeypatch.setattr(auth_route, "validate_id_token", _fake_validate)
    state = _valid_state()
    async with _client(seeded_session) as client:
        r = await client.get("/v1/auth/callback", params={"code": "abc", "state": state})
    assert r.status_code == 400


async def test_expired_cookie_401(seeded_session: AsyncSession, oidc_env: None) -> None:
    import time

    from context_engine.api.oidc import issue_session_token

    admin = (
        await seeded_session.execute(select(User).where(User.email == "admin@demo.dev"))
    ).scalar_one()
    past = int(time.time()) - 13 * 3600
    token = issue_session_token(get_settings(), user_id=str(admin.id), email=admin.email, now=past)
    async with _client(seeded_session) as client:
        client.cookies.set("ce_session", token)
        r = await client.get("/v1/me")
    assert r.status_code == 401
    assert r.json() == {"detail": "Not authenticated"}


async def test_inactive_user_with_valid_cookie_rejected(
    seeded_session: AsyncSession, oidc_env: None
) -> None:
    from context_engine.api.oidc import issue_session_token

    admin = (
        await seeded_session.execute(select(User).where(User.email == "admin@demo.dev"))
    ).scalar_one()
    admin.is_active = False
    await seeded_session.flush()
    token = issue_session_token(get_settings(), user_id=str(admin.id), email=admin.email)
    async with _client(seeded_session) as client:
        client.cookies.set("ce_session", token)
        r = await client.get("/v1/me")
    assert r.status_code == 401


async def test_logout_clears_cookie(seeded_session: AsyncSession, oidc_env: None) -> None:
    async with _client(seeded_session) as client:
        r = await client.post("/v1/auth/logout")
    assert r.status_code == 204
    # Set-Cookie clears ce_session (empty value / expiry in the past).
    set_cookie = r.headers.get("set-cookie", "")
    assert "ce_session=" in set_cookie


async def test_bearer_key_still_works_in_oidc_mode(
    seeded_session: AsyncSession, oidc_env: None
) -> None:
    async with _client(seeded_session) as client:
        r = await client.get("/v1/me", headers=auth_headers(ADMIN_KEY))
    assert r.status_code == 200
    assert r.json()["role"] == "admin"

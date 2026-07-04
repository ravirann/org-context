"""OIDC client helpers and session/state JWT handling.

Two token families are minted here, both HS256-signed with ``settings.secret_key``:

* **session** — the ``ce_session`` cookie ``{sub, email, iat, exp}`` proving a browser
  login (validated on every request in :mod:`context_engine.api.deps`).
* **state** — the OIDC ``state`` param ``{nonce, redirect_after?, exp}`` (10 min) that
  ties the ``/login`` redirect to its ``/callback`` to prevent CSRF.

OIDC discovery + JWKS are fetched with an ``httpx.AsyncClient`` and cached in-process with
a TTL; :func:`reset_oidc_cache` clears the cache for tests.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from typing import Any

import httpx
import jwt
from jwt import InvalidTokenError, PyJWKClient

from context_engine.config.settings import Settings

_ALGO = "HS256"
_DISCOVERY_TTL_SECONDS = 300.0


class SessionError(Exception):
    """Raised when a session or state JWT is missing, expired, or tampered with."""


@dataclass(frozen=True)
class SessionClaims:
    """Decoded ``ce_session`` cookie payload."""

    sub: str
    email: str


# --------------------------------------------------------------------------- #
# Session JWT (ce_session cookie)                                              #
# --------------------------------------------------------------------------- #


def issue_session_token(
    settings: Settings, *, user_id: str, email: str, now: int | None = None
) -> str:
    """Mint an HS256 session JWT for ``user_id`` valid for ``session_ttl_hours``."""
    issued = int(time.time()) if now is None else now
    payload = {
        "sub": user_id,
        "email": email,
        "iat": issued,
        "exp": issued + settings.session_ttl_hours * 3600,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=_ALGO)


def verify_session_token(settings: Settings, token: str) -> SessionClaims:
    """Decode and validate a session JWT, or raise :class:`SessionError`."""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[_ALGO])
    except InvalidTokenError as exc:  # includes ExpiredSignatureError
        raise SessionError(str(exc)) from exc
    sub = payload.get("sub")
    email = payload.get("email")
    if not isinstance(sub, str) or not isinstance(email, str):
        raise SessionError("malformed session claims")
    return SessionClaims(sub=sub, email=email)


# --------------------------------------------------------------------------- #
# State JWT (OIDC CSRF protection)                                            #
# --------------------------------------------------------------------------- #


def issue_state_token(
    settings: Settings, *, redirect_after: str | None = None, now: int | None = None
) -> str:
    """Mint a short-lived (10 min) signed ``state`` token for the auth-code flow."""
    issued = int(time.time()) if now is None else now
    payload: dict[str, Any] = {"nonce": uuid.uuid4().hex, "exp": issued + 600}
    if redirect_after is not None:
        payload["redirect_after"] = redirect_after
    return jwt.encode(payload, settings.secret_key, algorithm=_ALGO)


def verify_state_token(settings: Settings, token: str) -> dict[str, Any]:
    """Decode and validate a ``state`` token, or raise :class:`SessionError`."""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[_ALGO])
    except InvalidTokenError as exc:
        raise SessionError(str(exc)) from exc
    return dict(payload)


# --------------------------------------------------------------------------- #
# OIDC provider metadata (discovery + JWKS), cached with TTL                  #
# --------------------------------------------------------------------------- #

_discovery_cache: dict[str, tuple[float, dict[str, Any]]] = {}


def reset_oidc_cache() -> None:
    """Clear the in-process discovery cache (used by tests)."""
    _discovery_cache.clear()


async def get_discovery_document(settings: Settings) -> dict[str, Any]:
    """Fetch and cache ``{issuer}/.well-known/openid-configuration`` (TTL-bounded)."""
    issuer = settings.oidc_issuer.rstrip("/")
    cached = _discovery_cache.get(issuer)
    now = time.monotonic()
    if cached is not None and now - cached[0] < _DISCOVERY_TTL_SECONDS:
        return cached[1]
    url = f"{issuer}/.well-known/openid-configuration"
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        document: dict[str, Any] = resp.json()
    _discovery_cache[issuer] = (now, document)
    return document


async def build_authorization_url(
    settings: Settings, *, state: str, scope: str = "openid email profile"
) -> str:
    """Compose the provider ``authorization_endpoint`` URL for the SPA to redirect to."""
    document = await get_discovery_document(settings)
    endpoint = document["authorization_endpoint"]
    params = httpx.QueryParams(
        {
            "response_type": "code",
            "client_id": settings.oidc_client_id,
            "redirect_uri": settings.oidc_redirect_url,
            "scope": scope,
            "state": state,
        }
    )
    return f"{endpoint}?{params}"


async def exchange_code_for_tokens(settings: Settings, *, code: str) -> dict[str, Any]:
    """Exchange an authorization ``code`` at the ``token_endpoint`` (confidential client)."""
    document = await get_discovery_document(settings)
    endpoint = document["token_endpoint"]
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": settings.oidc_redirect_url,
        "client_id": settings.oidc_client_id,
        "client_secret": settings.oidc_client_secret,
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(endpoint, data=data)
        resp.raise_for_status()
        tokens: dict[str, Any] = resp.json()
    return tokens


async def validate_id_token(settings: Settings, id_token: str) -> dict[str, Any]:
    """Validate an ID token's RS256 signature (via JWKS), ``aud``, ``iss``, and ``exp``.

    Returns the verified claims, or raises :class:`SessionError` on any failure.
    """
    document = await get_discovery_document(settings)
    jwks_uri = document["jwks_uri"]
    issuer = document.get("issuer", settings.oidc_issuer.rstrip("/"))
    try:
        signing_key = PyJWKClient(jwks_uri).get_signing_key_from_jwt(id_token)
        claims: dict[str, Any] = jwt.decode(
            id_token,
            signing_key.key,
            algorithms=["RS256"],
            audience=settings.oidc_client_id,
            issuer=issuer,
        )
    except (InvalidTokenError, Exception) as exc:  # noqa: BLE001 — any JWKS/decode failure → 400
        raise SessionError(str(exc)) from exc
    return claims

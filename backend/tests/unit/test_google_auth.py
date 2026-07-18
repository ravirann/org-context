"""Unit tests for the shared Google service-account JWT-bearer auth helper.

No real network: the token exchange goes through an ``httpx.MockTransport`` whose
handler asserts on the outgoing form data. A throwaway RSA key is generated in-test
via ``cryptography`` (which ships with ``pyjwt[crypto]``) so the signed assertion can
be decoded and its claims verified with the matching public key.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from urllib.parse import parse_qs

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from context_engine.connectors.live.google import JWT_GRANT_TYPE, GoogleServiceAccountAuth
from context_engine.connectors.live.http import (
    ConnectorAuthError,
    ConnectorError,
    build_client,
)

Handler = Callable[[httpx.Request], httpx.Response]

TOKEN_URI = "https://oauth2.example.test/token"
CLIENT_EMAIL = "svc@proj.iam.gserviceaccount.com"
SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/gmail.readonly",
]


def _rsa_keypair() -> tuple[str, str]:
    """Generate a throwaway 2048-bit RSA key, returning (private_pem, public_pem)."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_pem = (
        key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )
    return private_pem, public_pem


def _sa_json(private_pem: str, *, token_uri: str | None = TOKEN_URI) -> str:
    """Serialize a minimal service-account JSON key around ``private_pem``."""
    key: dict[str, str] = {
        "type": "service_account",
        "client_email": CLIENT_EMAIL,
        "private_key": private_pem,
    }
    if token_uri is not None:
        key["token_uri"] = token_uri
    return json.dumps(key)


def _capturing_handler(seen: dict, *, expires_in: int = 3600) -> Handler:
    """Return a handler that records the form payload and returns a fresh token."""
    counter = {"n": 0}

    def handler(req: httpx.Request) -> httpx.Response:
        counter["n"] += 1
        seen["url"] = str(req.url)
        form = {k: v[0] for k, v in parse_qs(req.content.decode()).items()}
        seen["grant_type"] = form.get("grant_type")
        seen["assertion"] = form.get("assertion")
        seen["calls"] = counter["n"]
        return httpx.Response(
            200,
            json={"access_token": f"ya29.token-{counter['n']}", "expires_in": expires_in},
            request=req,
        )

    return handler


async def test_access_token_mints_and_posts_signed_jwt() -> None:
    private_pem, public_pem = _rsa_keypair()
    seen: dict = {}
    auth = GoogleServiceAccountAuth(_sa_json(private_pem), scopes=SCOPES, subject="user@corp.dev")

    transport = httpx.MockTransport(_capturing_handler(seen))
    async with build_client(transport=transport) as client:
        token = await auth.access_token(client)

    assert token == "ya29.token-1"
    assert seen["url"] == TOKEN_URI
    assert seen["grant_type"] == JWT_GRANT_TYPE

    claims = jwt.decode(seen["assertion"], public_pem, algorithms=["RS256"], audience=TOKEN_URI)
    assert claims["iss"] == CLIENT_EMAIL
    assert claims["scope"] == " ".join(SCOPES)
    assert claims["sub"] == "user@corp.dev"
    assert claims["aud"] == TOKEN_URI
    assert claims["exp"] > claims["iat"]


async def test_default_token_uri_used_when_key_omits_it() -> None:
    private_pem, public_pem = _rsa_keypair()
    seen: dict = {}
    auth = GoogleServiceAccountAuth(_sa_json(private_pem, token_uri=None), scopes=SCOPES)

    transport = httpx.MockTransport(_capturing_handler(seen))
    async with build_client(transport=transport) as client:
        await auth.access_token(client)

    assert seen["url"] == "https://oauth2.googleapis.com/token"
    claims = jwt.decode(
        seen["assertion"],
        public_pem,
        algorithms=["RS256"],
        audience="https://oauth2.googleapis.com/token",
    )
    assert claims["aud"] == "https://oauth2.googleapis.com/token"


async def test_subject_omitted_produces_no_sub_claim() -> None:
    private_pem, public_pem = _rsa_keypair()
    seen: dict = {}
    auth = GoogleServiceAccountAuth(_sa_json(private_pem), scopes=SCOPES)

    transport = httpx.MockTransport(_capturing_handler(seen))
    async with build_client(transport=transport) as client:
        await auth.access_token(client)

    claims = jwt.decode(seen["assertion"], public_pem, algorithms=["RS256"], audience=TOKEN_URI)
    assert "sub" not in claims


async def test_token_cached_then_reminted_after_expiry() -> None:
    private_pem, _ = _rsa_keypair()
    seen: dict = {}
    auth = GoogleServiceAccountAuth(_sa_json(private_pem), scopes=SCOPES)

    transport = httpx.MockTransport(_capturing_handler(seen))
    async with build_client(transport=transport) as client:
        first = await auth.access_token(client)
        second = await auth.access_token(client)  # served from cache, no new request
        assert first == second == "ya29.token-1"
        assert seen["calls"] == 1

        # Simulate the cached token nearing expiry: forces a re-mint.
        auth._expires_at = time.time()
        third = await auth.access_token(client)

    assert third == "ya29.token-2"
    assert seen["calls"] == 2


async def test_token_endpoint_401_raises_auth_error() -> None:
    private_pem, _ = _rsa_keypair()
    auth = GoogleServiceAccountAuth(_sa_json(private_pem), scopes=SCOPES)

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            401,
            json={"error": "invalid_grant", "error_description": "Invalid JWT signature."},
            request=req,
        )

    transport = httpx.MockTransport(handler)
    async with build_client(transport=transport) as client:
        with pytest.raises(ConnectorAuthError) as excinfo:
            await auth.access_token(client)
    assert "invalid_grant" in str(excinfo.value)


async def test_invalid_json_key_raises_on_access_not_construction() -> None:
    # Construction with a masked/placeholder secret must NOT raise.
    auth = GoogleServiceAccountAuth("•••abcd not json{", scopes=SCOPES)

    transport = httpx.MockTransport(
        lambda req: httpx.Response(200, json={"access_token": "x"}, request=req)
    )
    async with build_client(transport=transport) as client:
        with pytest.raises(ConnectorAuthError):
            await auth.access_token(client)


async def test_missing_private_key_raises_auth_error() -> None:
    auth = GoogleServiceAccountAuth(
        json.dumps({"client_email": CLIENT_EMAIL, "token_uri": TOKEN_URI}), scopes=SCOPES
    )
    transport = httpx.MockTransport(
        lambda req: httpx.Response(200, json={"access_token": "x"}, request=req)
    )
    async with build_client(transport=transport) as client:
        with pytest.raises(ConnectorAuthError):
            await auth.access_token(client)


async def test_200_without_access_token_raises_connector_error() -> None:
    private_pem, _ = _rsa_keypair()
    auth = GoogleServiceAccountAuth(_sa_json(private_pem), scopes=SCOPES)

    transport = httpx.MockTransport(
        lambda req: httpx.Response(200, json={"token_type": "Bearer"}, request=req)
    )
    async with build_client(transport=transport) as client:
        with pytest.raises(ConnectorError):
            await auth.access_token(client)

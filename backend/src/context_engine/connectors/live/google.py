"""Shared Google service-account auth for the live Drive/Gmail/Calendar connectors.

Google service accounts authenticate to Google APIs with the OAuth 2.0 *JWT-bearer*
flow (RFC 7523): we sign a short-lived JWT with the service account's RSA private
key, then exchange it at the token endpoint for a bearer access token.

Flow (per :meth:`GoogleServiceAccountAuth.access_token`):

1. Build a JWT whose claims name the service account (``iss``), the requested
   ``scope``, the token endpoint (``aud``), and — for domain-wide delegation — the
   end user to impersonate (``sub``). Sign it ``RS256`` with the private key.
2. POST the assertion to ``token_uri`` as
   ``grant_type=urn:ietf:params:oauth:grant-type:jwt-bearer``.
3. Cache the returned ``access_token`` until shortly before it expires so a burst
   of connector requests mints only one token.

The service-account JSON key is parsed lazily on first :meth:`access_token` call
rather than in ``__init__`` so a source can be configured with a masked/placeholder
secret without exploding. A malformed key or a token-endpoint config rejection
(400/401/403) surfaces as :class:`ConnectorAuthError` (non-retryable); transient
token-endpoint failures (429/5xx) surface as :class:`ConnectorError`.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass

import httpx
import jwt

from context_engine.connectors.live.http import ConnectorAuthError, ConnectorError
from context_engine.observability.logging import get_logger

logger = get_logger(__name__)

DEFAULT_TOKEN_URI = "https://oauth2.googleapis.com/token"
"""Google's OAuth 2.0 token endpoint, used when the key omits ``token_uri``."""

JWT_GRANT_TYPE = "urn:ietf:params:oauth:grant-type:jwt-bearer"
"""RFC 7523 grant type for the JWT-bearer token exchange."""

_JWT_LIFETIME_SECONDS = 3600
"""Signed-assertion lifetime; Google caps this at one hour."""

_EXPIRY_SKEW_SECONDS = 60
"""Re-mint this many seconds before the cached token actually expires."""

_DEFAULT_EXPIRES_IN = 3600
"""Assumed token lifetime when the response omits ``expires_in``."""


@dataclass(frozen=True)
class _ServiceAccountKey:
    """The three fields of a Google service-account JSON key we rely on."""

    client_email: str
    private_key: str
    token_uri: str


class GoogleServiceAccountAuth:
    """Mint and cache Google API access tokens from a service-account key.

    Construct once per source with the raw JSON key, the OAuth ``scopes`` to
    request, and (for domain-wide delegation) the ``subject`` user to impersonate.
    Pass a shared :class:`httpx.AsyncClient` to :meth:`access_token`; the same
    client should carry the minted bearer token on subsequent API calls.
    """

    def __init__(
        self,
        service_account_json: str,
        scopes: list[str],
        subject: str | None = None,
    ) -> None:
        self._service_account_json = service_account_json
        self._scopes = scopes
        self._subject = subject
        self._key: _ServiceAccountKey | None = None
        self._token: str | None = None
        self._expires_at: float = 0.0

    async def access_token(self, client: httpx.AsyncClient) -> str:
        """Return a valid bearer access token, minting and caching a new one lazily.

        Reuses the cached token until ``_EXPIRY_SKEW_SECONDS`` before it expires;
        otherwise signs a fresh JWT and exchanges it at the token endpoint using the
        provided ``client`` (so tests can inject an ``httpx.MockTransport``).

        Raises :class:`ConnectorAuthError` for a malformed key or a 400/401/403 from
        the token endpoint (config errors, non-retryable), and :class:`ConnectorError`
        for a transient 429/5xx or a 200 response with no ``access_token``.
        """
        key = self._load_key()
        now = time.time()
        if self._token is not None and now < self._expires_at - _EXPIRY_SKEW_SECONDS:
            return self._token

        assertion = self._build_assertion(key, now)
        try:
            response = await client.post(
                key.token_uri,
                data={"grant_type": JWT_GRANT_TYPE, "assertion": assertion},
            )
        except httpx.HTTPError as exc:
            raise ConnectorError(f"token request to {key.token_uri} failed: {exc}") from exc

        token, expires_in = self._parse_token_response(response, key.token_uri)
        self._token = token
        self._expires_at = time.time() + expires_in
        return token

    def _load_key(self) -> _ServiceAccountKey:
        """Parse and cache the service-account JSON, raising on invalid config."""
        if self._key is not None:
            return self._key

        try:
            data = json.loads(self._service_account_json)
        except (json.JSONDecodeError, TypeError) as exc:
            raise ConnectorAuthError(f"service account key is not valid JSON: {exc}") from exc
        if not isinstance(data, dict):
            raise ConnectorAuthError("service account key must be a JSON object")

        client_email = data.get("client_email")
        private_key = data.get("private_key")
        if not client_email or not private_key:
            raise ConnectorAuthError(
                "service account key missing required client_email/private_key"
            )

        self._key = _ServiceAccountKey(
            client_email=str(client_email),
            private_key=str(private_key),
            token_uri=str(data.get("token_uri") or DEFAULT_TOKEN_URI),
        )
        return self._key

    def _build_assertion(self, key: _ServiceAccountKey, now: float) -> str:
        """Sign the RS256 JWT-bearer assertion for ``key`` at wall-clock ``now``."""
        issued = int(now)
        claims: dict[str, object] = {
            "iss": key.client_email,
            "scope": " ".join(self._scopes),
            "aud": key.token_uri,
            "iat": issued,
            "exp": issued + _JWT_LIFETIME_SECONDS,
        }
        if self._subject is not None:
            claims["sub"] = self._subject
        try:
            return jwt.encode(claims, key.private_key, algorithm="RS256")
        except (ValueError, TypeError) as exc:
            raise ConnectorAuthError(f"could not sign JWT with service account key: {exc}") from exc

    def _parse_token_response(self, response: httpx.Response, token_uri: str) -> tuple[str, float]:
        """Extract ``(access_token, expires_in)`` from the token endpoint response."""
        status = response.status_code
        if status in (400, 401, 403):
            raise ConnectorAuthError(
                f"token endpoint {token_uri} rejected credentials ({status}): "
                f"{self._error_detail(response)}"
            )
        if status == 429 or status >= 500:
            raise ConnectorError(f"token endpoint {token_uri} returned {status} (transient)")
        if status >= 400:
            raise ConnectorError(
                f"token endpoint {token_uri} returned {status}: {response.text[:200]}"
            )

        try:
            body = response.json()
        except (ValueError, json.JSONDecodeError) as exc:
            raise ConnectorError(f"token endpoint {token_uri} returned non-JSON body") from exc

        token = body.get("access_token") if isinstance(body, dict) else None
        if not token:
            raise ConnectorError(f"token endpoint {token_uri} response missing access_token")
        expires_in = body.get("expires_in", _DEFAULT_EXPIRES_IN)
        try:
            expires_in = float(expires_in)
        except (TypeError, ValueError):
            expires_in = float(_DEFAULT_EXPIRES_IN)
        return str(token), expires_in

    @staticmethod
    def _error_detail(response: httpx.Response) -> str:
        """Best-effort ``error``/``error_description`` from an OAuth error body."""
        try:
            body = response.json()
        except (ValueError, json.JSONDecodeError):
            return response.text[:200]
        if not isinstance(body, dict):
            return response.text[:200]
        error = body.get("error")
        description = body.get("error_description")
        if error and description:
            return f"{error}: {description}"
        return str(error or description or response.text[:200])

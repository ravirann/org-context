"""Shared async HTTP helper for live connectors.

Builds an :class:`httpx.AsyncClient` with bearer or basic auth and a 30s timeout,
and exposes :func:`request_json` which retries transient failures (429 / 5xx) with
exponential backoff, honoring ``Retry-After``. Auth failures (401/403) raise
:class:`ConnectorAuthError`; any other non-2xx raises :class:`ConnectorError`.

Tests inject an ``httpx.MockTransport`` via the ``transport`` argument so no real
network is ever touched.
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

from context_engine.observability.logging import get_logger

logger = get_logger(__name__)

DEFAULT_TIMEOUT = 30.0
"""Seconds before an upstream request is aborted."""

MAX_RETRIES = 3
"""Attempts beyond the first for retryable (429 / 5xx) responses."""

_BACKOFF_SCHEDULE = (0.5, 2.0, 8.0)
"""Exponential backoff delays (seconds), capped, one per retry."""

_RETRYABLE_STATUS = {429, 500, 502, 503, 504}
_AUTH_STATUS = {401, 403}


class ConnectorError(RuntimeError):
    """A live connector could not complete an upstream request."""


class ConnectorAuthError(ConnectorError):
    """Upstream rejected our credentials (401/403) — not retryable."""


def build_client(
    *,
    base_url: str = "",
    bearer_token: str | None = None,
    basic_auth: tuple[str, str] | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
    timeout: float = DEFAULT_TIMEOUT,
    headers: dict[str, str] | None = None,
) -> httpx.AsyncClient:
    """Return an ``AsyncClient`` configured with auth, timeout, and JSON headers.

    Exactly one of ``bearer_token`` / ``basic_auth`` is expected in practice, but
    both are optional so unauthenticated public endpoints still work. ``transport``
    is dependency-injectable so tests can pass an ``httpx.MockTransport``.
    """
    request_headers: dict[str, str] = {"Accept": "application/json"}
    if headers:
        request_headers.update(headers)
    if bearer_token:
        request_headers["Authorization"] = f"Bearer {bearer_token}"

    auth = httpx.BasicAuth(*basic_auth) if basic_auth is not None else None
    return httpx.AsyncClient(
        base_url=base_url,
        auth=auth,
        headers=request_headers,
        timeout=timeout,
        transport=transport,
    )


def _retry_after_seconds(response: httpx.Response, fallback: float) -> float:
    """Parse a ``Retry-After`` header (delta-seconds only); fall back otherwise."""
    raw = response.headers.get("Retry-After")
    if raw is None:
        return fallback
    try:
        return max(0.0, float(raw))
    except ValueError:
        return fallback


async def request_json(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    max_retries: int = MAX_RETRIES,
    **kwargs: Any,
) -> Any:
    """Perform an HTTP request and return the decoded JSON body.

    Retries up to ``max_retries`` times on 429 and 5xx responses using exponential
    backoff (``0.5/2/8s`` capped), honoring ``Retry-After`` when present. Raises
    :class:`ConnectorAuthError` on 401/403 and :class:`ConnectorError` on any other
    non-2xx status or transport error once retries are exhausted.
    """
    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            response = await client.request(method, url, **kwargs)
        except httpx.HTTPError as exc:
            last_exc = exc
            logger.warning(
                "connector_http_transport_error",
                url=url,
                attempt=attempt,
                error=str(exc),
            )
            if attempt < max_retries:
                await asyncio.sleep(_BACKOFF_SCHEDULE[min(attempt, len(_BACKOFF_SCHEDULE) - 1)])
                continue
            raise ConnectorError(f"request to {url} failed: {exc}") from exc

        status = response.status_code
        logger.info("connector_http_request", url=url, status=status, attempt=attempt)

        if status in _AUTH_STATUS:
            raise ConnectorAuthError(f"{method} {url} returned {status} (authentication failed)")

        if status in _RETRYABLE_STATUS and attempt < max_retries:
            fallback = _BACKOFF_SCHEDULE[min(attempt, len(_BACKOFF_SCHEDULE) - 1)]
            delay = _retry_after_seconds(response, fallback)
            logger.warning(
                "connector_http_retry",
                url=url,
                status=status,
                attempt=attempt,
                delay=delay,
            )
            await asyncio.sleep(delay)
            continue

        if status >= 400:
            raise ConnectorError(f"{method} {url} returned {status}: {response.text[:200]}")

        return response.json()

    # Only reached if the loop exits without returning (retries exhausted on 5xx/429).
    raise ConnectorError(f"request to {url} exhausted retries") from last_exc

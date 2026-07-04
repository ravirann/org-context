"""Shared app-level CORS/origin config without importing the app factory.

Kept in its own module so routers (e.g. auth) can read the UI origin for redirects
without a circular import back through :mod:`context_engine.api.app`.
"""

from __future__ import annotations

import os

_DEFAULT_ORIGINS = "http://localhost:5173,http://localhost:8080"


def cors_origins() -> list[str]:
    """Allowed browser origins, comma-separated via CE_CORS_ORIGINS.

    Configurable because responses carry credentials (session cookies): the UI's
    actual origin must be listed explicitly or every browser call is blocked.
    """
    raw = os.environ.get("CE_CORS_ORIGINS", _DEFAULT_ORIGINS)
    return [origin.strip().rstrip("/") for origin in raw.split(",") if origin.strip()]


# Backwards-compatible constant for existing imports; evaluated at import time.
CORS_ORIGINS: list[str] = cors_origins()


def ui_origin() -> str:
    """Return the UI origin OIDC callbacks redirect to (the first CORS origin)."""
    return cors_origins()[0]

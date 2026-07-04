"""FastAPI application factory for the Org Context Engineering Platform.

``create_app()`` wires CORS, the observability request middleware, structlog config,
an unauthenticated ``/healthz`` probe, and every ``/v1`` router. ``app`` is bound to the
factory (not called) for ``uvicorn --factory``; tests call ``create_app()`` directly.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from context_engine.api.app_config import cors_origins
from context_engine.api.routes import ALL_ROUTERS
from context_engine.observability.logging import configure_logging
from context_engine.observability.middleware import RequestContextMiddleware


def create_app() -> FastAPI:
    """Build and return the configured FastAPI application."""
    configure_logging()

    app = FastAPI(title="Org Context API")

    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/healthz", tags=["health"])
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    for router in ALL_ROUTERS:
        app.include_router(router, prefix="/v1")

    return app


app: Any = create_app

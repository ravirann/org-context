"""ASGI middleware adding a request id and per-request timing logs."""

from __future__ import annotations

import time
import uuid
from typing import Any

import structlog

from context_engine.observability.logging import get_logger

logger = get_logger("context_engine.request")

REQUEST_ID_HEADER = b"x-request-id"


class RequestContextMiddleware:
    """Pure ASGI middleware: binds request_id to structlog and logs timing."""

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers") or [])
        request_id = (headers.get(REQUEST_ID_HEADER) or b"").decode() or uuid.uuid4().hex
        structlog.contextvars.bind_contextvars(request_id=request_id)
        start = time.perf_counter()
        status_holder = {"status": 500}

        async def send_wrapper(message: dict[str, Any]) -> None:
            if message["type"] == "http.response.start":
                status_holder["status"] = message["status"]
                raw_headers = list(message.get("headers") or [])
                raw_headers.append((REQUEST_ID_HEADER, request_id.encode()))
                message["headers"] = raw_headers
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            logger.info(
                "request_completed",
                method=scope.get("method"),
                path=scope.get("path"),
                status=status_holder["status"],
                duration_ms=duration_ms,
            )
            structlog.contextvars.unbind_contextvars("request_id")

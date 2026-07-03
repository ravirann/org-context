"""Langfuse shim: a real client when keys are configured, otherwise a safe no-op."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from context_engine.config.settings import get_settings
from context_engine.observability.logging import get_logger

logger = get_logger(__name__)


class _NoopSpan:
    """No-op span/trace object: accepts any method call and returns itself."""

    def __getattr__(self, name: str) -> Any:
        def _noop(*args: Any, **kwargs: Any) -> _NoopSpan:
            return self

        return _noop

    def __enter__(self) -> _NoopSpan:
        return self

    def __exit__(self, *exc: Any) -> None:
        return None


class NoopLangfuse:
    """Drop-in stand-in for the Langfuse client when no keys are configured."""

    enabled = False

    def trace(self, *args: Any, **kwargs: Any) -> _NoopSpan:
        return _NoopSpan()

    def span(self, *args: Any, **kwargs: Any) -> _NoopSpan:
        return _NoopSpan()

    def generation(self, *args: Any, **kwargs: Any) -> _NoopSpan:
        return _NoopSpan()

    def event(self, *args: Any, **kwargs: Any) -> _NoopSpan:
        return _NoopSpan()

    def flush(self) -> None:
        return None

    def shutdown(self) -> None:
        return None

    def __getattr__(self, name: str) -> Any:
        def _noop(*args: Any, **kwargs: Any) -> _NoopSpan:
            return _NoopSpan()

        return _noop


def _langfuse_configured() -> bool:
    settings = get_settings()
    return bool(settings.langfuse_public_key and settings.langfuse_secret_key)


@lru_cache
def get_langfuse() -> Any:
    """Return a Langfuse client if CE_LANGFUSE_* keys are set, else a no-op shim."""
    if not _langfuse_configured():
        return NoopLangfuse()
    settings = get_settings()
    try:
        from langfuse import Langfuse

        client: Any = Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
        )
        client.enabled = True
        return client
    except Exception:  # pragma: no cover - import/config problems must never break the app
        logger.warning("langfuse_init_failed", exc_info=True)
        return NoopLangfuse()


def trace_url(trace_id: str | None) -> str | None:
    """Return the Langfuse UI URL for a trace id, or None when Langfuse is not configured."""
    if not trace_id or not _langfuse_configured():
        return None
    settings = get_settings()
    return f"{settings.langfuse_host.rstrip('/')}/trace/{trace_id}"

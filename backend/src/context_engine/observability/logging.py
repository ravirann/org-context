"""structlog JSON logging configuration."""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog

from context_engine.config.settings import get_settings

_configured = False


def configure_logging() -> None:
    """Configure structlog for JSON output (idempotent)."""
    global _configured
    if _configured:
        return
    settings = get_settings()
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(sys.stdout),
        cache_logger_on_first_use=True,
    )
    _configured = True


def get_logger(name: str | None = None, **initial_values: Any) -> structlog.BoundLogger:
    """Return a configured structlog logger."""
    configure_logging()
    return structlog.get_logger(name, **initial_values)

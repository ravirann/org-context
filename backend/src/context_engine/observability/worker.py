"""Dramatiq broker setup — the worker entrypoint.

Run with: ``dramatiq context_engine.observability.worker --processes 1 --threads 4``.
Actor modules (ingestion, evals) are imported lazily at the bottom so this module
keeps working before those packages land.
"""

from __future__ import annotations

import importlib

import dramatiq
from dramatiq.brokers.redis import RedisBroker
from dramatiq.brokers.stub import StubBroker

from context_engine.config.settings import get_settings
from context_engine.observability.logging import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)

_settings = get_settings()

broker: dramatiq.Broker
if _settings.env == "test":
    broker = StubBroker()
    broker.emit_after("process_boot")
else:
    broker = RedisBroker(url=_settings.redis_url)

dramatiq.set_broker(broker)


def get_broker() -> dramatiq.Broker:
    """Return the configured dramatiq broker."""
    return broker


# Import actor modules so the worker registers them. These packages are delivered
# by other modules of the platform; tolerate their absence during bootstrap.
for _module in (
    "context_engine.ingestion.actors",
    "context_engine.evals.actors",
    "context_engine.indexing.actors",
):
    try:
        importlib.import_module(_module)
    except ImportError:
        logger.debug("actor_module_unavailable", module=_module)

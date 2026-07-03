"""Connector protocol, RawItem payload, and the connector registry.

Concrete connectors are demo/offline connectors: they return deterministic,
realistic fixtures for the demo organization without any network access.
Timestamps derive from a fixed epoch so two fetches always agree.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, ClassVar, Protocol, runtime_checkable

from context_engine.storage.models import Source

DEMO_EPOCH = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
"""Fixed reference time demo connectors derive item timestamps from."""

ALL_SOURCE_TYPES: list[str] = [
    "github",
    "jira",
    "slack",
    "confluence",
    "adr",
    "incident",
    "ci",
    "feedback",
]
"""Every source type with a built-in demo connector."""


def demo_timestamp(days: int, hours: int = 0) -> datetime:
    """Deterministic timestamp ``days``/``hours`` before the demo epoch."""
    return DEMO_EPOCH - timedelta(days=days, hours=hours)


@dataclass(frozen=True)
class RawAcl:
    """Access control payload attached to a RawItem (resolved to ids at ingest)."""

    public: bool = True
    team_names: list[str] = field(default_factory=list)
    user_emails: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class RawItem:
    """A single normalized-enough payload emitted by a connector."""

    external_id: str
    doc_type: str
    title: str
    content: str
    url: str = ""
    author_email: str | None = None
    repo: str | None = None
    service: str | None = None
    team_name: str | None = None
    acl: RawAcl = field(default_factory=RawAcl)
    topic_key: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    last_activity_at: datetime = DEMO_EPOCH


@runtime_checkable
class Connector(Protocol):
    """A source connector able to fetch raw items for a Source row."""

    source_type: ClassVar[str]

    async def fetch(self, source: Source) -> list[RawItem]:
        """Return the raw items currently visible in the upstream system."""
        ...


_REGISTRY: dict[str, Connector] = {}


def register(connector: Connector) -> None:
    """Register a connector instance under its ``source_type``."""
    _REGISTRY[connector.source_type] = connector


def _load_builtin_connectors() -> None:
    for name in ALL_SOURCE_TYPES:
        importlib.import_module(f"context_engine.connectors.{name}")


def get_connector(source_type: str) -> Connector:
    """Return the registered connector for ``source_type`` (loads built-ins lazily)."""
    key = str(source_type)
    if key not in _REGISTRY:
        _load_builtin_connectors()
    try:
        return _REGISTRY[key]
    except KeyError:
        raise ValueError(f"No connector registered for source type {key!r}") from None

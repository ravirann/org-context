"""Unit tests for the ingestion scheduler's pure due-source selection (PHASE3 §B)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from context_engine.ingestion.scheduler import due_sources
from context_engine.storage.models import Source, SourceType

NOW = datetime(2026, 7, 4, 12, 0, tzinfo=UTC)


def _source(
    *, enabled: bool = True, last_synced_at: datetime | None = None, name: str = "s"
) -> Source:
    return Source(
        id=uuid.uuid4(),
        type=SourceType.github,
        name=name,
        enabled=enabled,
        config={},
        last_synced_at=last_synced_at,
    )


@pytest.mark.parametrize(
    ("enabled", "age_minutes", "interval", "expected_due"),
    [
        (True, None, 30, True),  # never synced -> due
        (True, 45, 30, True),  # older than interval -> due
        (True, 10, 30, False),  # synced recently -> not due
        (False, None, 30, False),  # disabled -> never due
        (False, 999, 30, False),  # disabled + stale -> still not due
        (True, 30, 30, True),  # exactly at threshold -> due (<=)
        (True, 29, 30, False),  # just under threshold -> not due
    ],
)
def test_due_sources_table(
    enabled: bool, age_minutes: int | None, interval: int, expected_due: bool
) -> None:
    last = None if age_minutes is None else NOW - timedelta(minutes=age_minutes)
    source = _source(enabled=enabled, last_synced_at=last)
    result = due_sources([source], NOW, interval)
    assert (source in result) is expected_due


def test_due_sources_filters_mixed_batch() -> None:
    never = _source(last_synced_at=None, name="never")
    stale = _source(last_synced_at=NOW - timedelta(hours=2), name="stale")
    fresh = _source(last_synced_at=NOW - timedelta(minutes=5), name="fresh")
    disabled = _source(enabled=False, last_synced_at=None, name="disabled")

    due = due_sources([never, stale, fresh, disabled], NOW, 30)

    assert {s.name for s in due} == {"never", "stale"}


def test_due_sources_clamps_nonpositive_interval() -> None:
    # A zero/negative interval must not select a source synced this very instant.
    just_now = _source(last_synced_at=NOW, name="just_now")
    # threshold = NOW - 1min, so a sync exactly at NOW is not due.
    assert due_sources([just_now], NOW, 0) == []

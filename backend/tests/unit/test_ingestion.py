"""Unit tests for ingestion helpers: freshness math and the dramatiq actor shell."""

from __future__ import annotations

import importlib
import math
import sys
from datetime import UTC, datetime, timedelta

import dramatiq
import pytest

from context_engine.ingestion import actors
from context_engine.ingestion.normalize import STALE_FRESHNESS_THRESHOLD, compute_freshness

BASE = datetime(2026, 1, 1, tzinfo=UTC)


def test_freshness_is_one_for_zero_age() -> None:
    assert compute_freshness(BASE, 90, now=BASE) == 1.0


def test_freshness_is_clamped_to_one_for_future_timestamps() -> None:
    assert compute_freshness(BASE + timedelta(days=10), 90, now=BASE) == 1.0


def test_freshness_decays_exponentially() -> None:
    assert compute_freshness(BASE - timedelta(days=90), 90, now=BASE) == pytest.approx(
        math.exp(-1.0)
    )
    assert compute_freshness(BASE - timedelta(days=45), 90, now=BASE) == pytest.approx(
        math.exp(-0.5)
    )


def test_freshness_is_clamped_to_zero_floor_for_ancient_docs() -> None:
    value = compute_freshness(BASE - timedelta(days=5000), 90, now=BASE)
    assert 0.0 <= value < 1e-9


def test_freshness_guards_non_positive_window() -> None:
    assert compute_freshness(BASE - timedelta(days=2), 0, now=BASE) == pytest.approx(math.exp(-2.0))


def test_freshness_defaults_to_current_time() -> None:
    value = compute_freshness(datetime.now(UTC) - timedelta(days=1), 90)
    assert math.exp(-1.5 / 90) < value <= 1.0


def test_stale_threshold_matches_data_model() -> None:
    assert STALE_FRESHNESS_THRESHOLD == 0.15


def test_sync_source_actor_is_registered_with_retries() -> None:
    assert isinstance(actors.sync_source_actor, dramatiq.Actor)
    assert actors.sync_source_actor.actor_name == "sync_source_actor"
    assert actors.sync_source_actor.options["max_retries"] == 3


def test_worker_module_imports_ingestion_actors() -> None:
    importlib.import_module("context_engine.observability.worker")
    assert "context_engine.ingestion.actors" in sys.modules
    module = importlib.import_module("context_engine.ingestion.actors")
    assert hasattr(module, "sync_source_actor")


def test_sync_source_actor_runs_the_async_helper(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, str]] = []

    async def fake(source_id: str, trigger: str = "manual") -> None:
        calls.append((source_id, trigger))

    monkeypatch.setattr(actors, "_sync_source_by_id", fake)
    actors.sync_source_actor("abc-123")
    assert calls == [("abc-123", "manual")]


def test_sync_source_actor_forwards_trigger(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, str]] = []

    async def fake(source_id: str, trigger: str = "manual") -> None:
        calls.append((source_id, trigger))

    monkeypatch.setattr(actors, "_sync_source_by_id", fake)
    actors.sync_source_actor("abc-123", trigger="scheduled")
    assert calls == [("abc-123", "scheduled")]


def test_sync_source_actor_propagates_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    async def boom(source_id: str, trigger: str = "manual") -> None:
        raise ValueError("nope")

    monkeypatch.setattr(actors, "_sync_source_by_id", boom)
    with pytest.raises(ValueError, match="nope"):
        actors.sync_source_actor("abc-123")

"""Unit tests for freshness decay, authority normalization and packet confidence."""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta

import pytest

from context_engine.reasoning.scoring import (
    CONFIDENCE_FLOOR,
    authority_from_rank,
    freshness_score,
    packet_confidence,
)
from context_engine.retrieval.service import SearchHit


def make_hit(score: float = 0.8, freshness: float = 0.9, authority: float = 0.95) -> SearchHit:
    return SearchHit(
        document_id="d1",
        chunk_id="c1",
        title="ADR",
        doc_type="adr",
        source_name="ADR Repository",
        snippet="…",
        score=score,
        url="https://demo.dev/adr/1",
        repo="payments-api",
        service="payments-api",
        status="active",
        freshness_score=freshness,
        authority_score=authority,
        last_activity_at=datetime.now(UTC),
    )


class TestFreshnessScore:
    def test_now_is_fresh(self) -> None:
        assert freshness_score(datetime.now(UTC), 90) == pytest.approx(1.0, abs=1e-3)

    def test_exponential_decay_at_window(self) -> None:
        ts = datetime.now(UTC) - timedelta(days=90)
        assert freshness_score(ts, 90) == pytest.approx(math.exp(-1.0), abs=1e-3)

    def test_half_window(self) -> None:
        ts = datetime.now(UTC) - timedelta(days=45)
        assert freshness_score(ts, 90) == pytest.approx(math.exp(-0.5), abs=1e-3)

    def test_very_old_clamped_to_zero_one(self) -> None:
        ts = datetime.now(UTC) - timedelta(days=10_000)
        value = freshness_score(ts, 90)
        assert 0.0 <= value < 0.001

    def test_future_timestamp_clamped_to_one(self) -> None:
        ts = datetime.now(UTC) + timedelta(days=30)
        assert freshness_score(ts, 90) == 1.0

    def test_naive_datetime_assumed_utc(self) -> None:
        naive = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=90)
        assert freshness_score(naive, 90) == pytest.approx(math.exp(-1.0), abs=1e-3)

    def test_zero_window_guarded(self) -> None:
        ts = datetime.now(UTC) - timedelta(days=1)
        value = freshness_score(ts, 0)
        assert 0.0 <= value <= 1.0


class TestAuthorityFromRank:
    @pytest.mark.parametrize(
        ("rank", "expected"),
        [(0, 0.0), (50, 0.5), (95, 0.95), (100, 1.0), (150, 1.0), (-5, 0.0)],
    )
    def test_rank_mapping(self, rank: int, expected: float) -> None:
        assert authority_from_rank(rank) == pytest.approx(expected)


class TestPacketConfidence:
    def test_empty_selection_hits_floor(self) -> None:
        assert packet_confidence([], 0) == CONFIDENCE_FLOOR

    def test_single_hit_is_quality_product(self) -> None:
        hit = make_hit(score=0.8, freshness=0.5, authority=0.5)
        assert packet_confidence([hit], 0) == pytest.approx(0.8 * 0.5 * 0.5)

    def test_conflict_penalty(self) -> None:
        hit = make_hit(score=0.9, freshness=1.0, authority=1.0)
        base = packet_confidence([hit], 0)
        assert packet_confidence([hit], 1) == pytest.approx(base - 0.1)
        assert packet_confidence([hit], 2) == pytest.approx(base - 0.2)

    def test_floor_applies_after_penalty(self) -> None:
        hit = make_hit(score=0.3, freshness=0.3, authority=0.3)
        assert packet_confidence([hit], 10) == CONFIDENCE_FLOOR

    def test_clamped_to_at_most_one(self) -> None:
        hit = make_hit(score=2.0, freshness=2.0, authority=2.0)
        assert packet_confidence([hit], 0) <= 1.0

    def test_weighted_mean_prefers_high_score_hits(self) -> None:
        strong = make_hit(score=0.9, freshness=1.0, authority=1.0)
        weak = make_hit(score=0.1, freshness=0.1, authority=0.1)
        value = packet_confidence([strong, weak], 0)
        plain_mean = ((0.9 * 1.0 * 1.0) + (0.1 * 0.1 * 0.1)) / 2
        assert value > plain_mean

    def test_negative_conflicts_do_not_boost(self) -> None:
        hit = make_hit(score=0.5, freshness=0.5, authority=0.5)
        assert packet_confidence([hit], -3) == packet_confidence([hit], 0)

    def test_zero_score_hits_fall_back_to_plain_mean(self) -> None:
        hits = [make_hit(score=0.0, freshness=1.0, authority=1.0)]
        assert packet_confidence(hits, 0) == pytest.approx(CONFIDENCE_FLOOR)

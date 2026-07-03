"""Scoring helpers: freshness decay, authority normalization, packet confidence.

Conventions (docs/DATA_MODEL.md):
    freshness_score  = exp(-age_days / window_days), clamped to [0, 1]
    authority_score  = source.authority_rank / 100, clamped to [0, 1]
    confidence_score = weighted mean of selected hits' (score · freshness · authority),
                       penalized by 0.1 per open conflict, floored at 0.05.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from datetime import UTC, datetime

from context_engine.retrieval.service import SearchHit

CONFLICT_PENALTY = 0.1
CONFIDENCE_FLOOR = 0.05


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def freshness_score(last_activity_at: datetime, window_days: int) -> float:
    """Exponential freshness decay, clamped to [0, 1]. Naive datetimes are assumed UTC."""
    if last_activity_at.tzinfo is None:
        last_activity_at = last_activity_at.replace(tzinfo=UTC)
    window = max(1, window_days)
    age_days = max(0.0, (datetime.now(UTC) - last_activity_at).total_seconds() / 86400.0)
    return _clamp01(math.exp(-age_days / window))


def authority_from_rank(rank: int) -> float:
    """Map a source authority rank (0–100) to an authority score in [0, 1]."""
    return _clamp01(rank / 100.0)


def packet_confidence(selected: list[SearchHit], open_conflicts: int) -> float:
    """Confidence for a compiled packet (see module docstring).

    The mean is weighted by each hit's retrieval score so strong matches dominate.
    An empty selection bottoms out at the floor (0.05).
    """
    base = _weighted_quality_mean(selected)
    confidence = base - CONFLICT_PENALTY * max(0, open_conflicts)
    return max(CONFIDENCE_FLOOR, _clamp01(confidence))


def _weighted_quality_mean(selected: Sequence[SearchHit]) -> float:
    if not selected:
        return 0.0
    weights = [max(0.0, hit.score) for hit in selected]
    qualities = [
        _clamp01(hit.score) * _clamp01(hit.freshness_score) * _clamp01(hit.authority_score)
        for hit in selected
    ]
    total_weight = sum(weights)
    if total_weight <= 0.0:
        return sum(qualities) / len(qualities)
    return sum(w * q for w, q in zip(weights, qualities, strict=True)) / total_weight

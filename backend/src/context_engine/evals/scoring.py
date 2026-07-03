"""Pure scoring functions for the eval harness (no I/O, no ORM access)."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any

DEFAULT_TOKEN_BUDGET = 6000
"""Token budget used to reward smaller compiled contexts."""

WEIGHT_F1 = 0.40
WEIGHT_KEYWORD = 0.35
WEIGHT_CITATIONS = 0.15
WEIGHT_TOKEN_EFFICIENCY = 0.10


def retrieval_scores(expected_ids: Sequence[str], got_ids: Sequence[str]) -> dict[str, float]:
    """Precision / recall / F1 of retrieved document ids against the golden set.

    Safe on empties: both empty scores a perfect 1.0 across the board (nothing
    to find, nothing wrong retrieved); an empty ``got`` with a non-empty
    ``expected`` scores 0.0; an empty ``expected`` yields recall 1.0.
    """
    expected = {str(doc_id) for doc_id in expected_ids}
    got = {str(doc_id) for doc_id in got_ids}
    if not expected and not got:
        return {"precision": 1.0, "recall": 1.0, "f1": 1.0}
    hits = len(expected & got)
    precision = hits / len(got) if got else 0.0
    recall = hits / len(expected) if expected else 1.0
    denominator = precision + recall
    f1 = (2 * precision * recall / denominator) if denominator > 0 else 0.0
    return {"precision": precision, "recall": recall, "f1": f1}


def keyword_score(context_text: str, expected_keywords: Sequence[str]) -> float:
    """Fraction of expected keywords present in the context (case-insensitive)."""
    if not expected_keywords:
        return 1.0
    haystack = context_text.lower()
    hits = sum(1 for keyword in expected_keywords if keyword.lower() in haystack)
    return hits / len(expected_keywords)


def missing_keywords(context_text: str, expected_keywords: Sequence[str]) -> list[str]:
    """Expected keywords absent from the context (case-insensitive), in order."""
    haystack = context_text.lower()
    return [keyword for keyword in expected_keywords if keyword.lower() not in haystack]


def citations_ok(packet_citations: Sequence[dict[str, Any]], selected_ids: Iterable[str]) -> bool:
    """True when every citation has a unique marker and cites a selected document.

    An empty citation list is vacuously OK. A citation missing its ``marker``
    or ``document_id``, or pointing outside ``selected_ids``, fails the check.
    """
    selected = {str(doc_id) for doc_id in selected_ids}
    markers: list[str] = []
    for citation in packet_citations:
        marker = citation.get("marker")
        document_id = citation.get("document_id")
        if not marker or not document_id or str(document_id) not in selected:
            return False
        markers.append(str(marker))
    return len(set(markers)) == len(markers)


def token_efficiency(tokens_used: int, budget: int = DEFAULT_TOKEN_BUDGET) -> float:
    """1.0 for a free context, linearly down to 0.0 at/over ``budget`` tokens."""
    if budget <= 0:
        return 0.0
    return 1.0 - min(1.0, max(0, tokens_used) / budget)


def task_score(
    f1: float, keyword: float, citations_ok_flag: bool, token_efficiency: float
) -> float:
    """Weighted task score: 0.4·f1 + 0.35·keyword + 0.15·citations + 0.10·efficiency."""
    score = (
        WEIGHT_F1 * f1
        + WEIGHT_KEYWORD * keyword
        + WEIGHT_CITATIONS * (1.0 if citations_ok_flag else 0.0)
        + WEIGHT_TOKEN_EFFICIENCY * token_efficiency
    )
    return max(0.0, min(1.0, score))


def is_regression(current_avg: float, previous_avg: float | None, delta_threshold: float) -> bool:
    """True when the average score dropped by more than ``delta_threshold``."""
    if previous_avg is None:
        return False
    return (previous_avg - current_avg) > delta_threshold

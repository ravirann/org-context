"""Unit tests for the pure MMR reranker (retrieval/mmr.py)."""

from __future__ import annotations

import math

from context_engine.retrieval.mmr import cosine_similarity, mmr_order


def test_cosine_similarity_basics() -> None:
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == 1.0
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == 0.0
    assert math.isclose(cosine_similarity([1.0, 1.0], [1.0, 1.0]), 1.0)
    # Empty / mismatched / zero vectors are safe.
    assert cosine_similarity([], [1.0]) == 0.0
    assert cosine_similarity([0.0, 0.0], [1.0, 1.0]) == 0.0


def test_lambda_one_is_pure_relevance_order() -> None:
    items = [
        ("a", 0.9, [1.0, 0.0]),
        ("b", 0.5, [1.0, 0.0]),
        ("c", 0.7, [0.0, 1.0]),
    ]
    # lambda=1 ignores diversity entirely -> strict relevance ordering.
    assert mmr_order(items, lam=1.0, k=3) == ["a", "c", "b"]


def test_mmr_promotes_diversity_over_near_duplicate() -> None:
    # a and b are near-duplicates (identical embedding); c is orthogonal but slightly
    # less relevant. With diversity weight, c should be picked 2nd over the duplicate b.
    items = [
        ("a", 0.90, [1.0, 0.0]),
        ("b", 0.85, [1.0, 0.0]),
        ("c", 0.60, [0.0, 1.0]),
    ]
    order = mmr_order(items, lam=0.5, k=3)
    assert order[0] == "a"
    assert order[1] == "c"
    assert order[2] == "b"


def test_k_truncates_and_empty_inputs() -> None:
    items = [("a", 0.9, [1.0]), ("b", 0.5, [1.0])]
    assert mmr_order(items, lam=0.7, k=1) == ["a"]
    assert mmr_order(items, lam=0.7, k=0) == []
    assert mmr_order([], lam=0.7, k=5) == []


def test_missing_embeddings_treated_as_diverse() -> None:
    # Rows without embeddings contribute zero similarity -> selection stays relevance-led.
    items: list[tuple[str, float, list[float]]] = [
        ("a", 0.9, []),
        ("b", 0.8, []),
        ("c", 0.7, []),
    ]
    assert mmr_order(items, lam=0.7, k=3) == ["a", "b", "c"]

"""Maximal Marginal Relevance (MMR) reranking — pure, dependency-free, testable.

MMR trades relevance against diversity: at each step it picks the still-unselected
item maximizing ``lambda * relevance - (1 - lambda) * max_cosine_to_already_picked``.
With ``lambda = 1.0`` this degrades to pure relevance ordering; with ``lambda = 0.0``
it maximizes novelty. Embeddings are compared with cosine similarity computed from a
plain Python dot product (vectors are assumed pre-normalized by the embedding
provider, but we normalize defensively so the function is correct for any input).
"""

from __future__ import annotations

import math

__all__ = ["cosine_similarity", "mmr_order"]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity of two equal-length vectors; 0.0 if either is empty/zero."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b, strict=True):
        dot += x * y
        na += x * x
        nb += y * y
    denom = math.sqrt(na) * math.sqrt(nb)
    if denom == 0.0:
        return 0.0
    return dot / denom


def mmr_order(items: list[tuple[str, float, list[float]]], lam: float, k: int) -> list[str]:
    """Reorder ``items`` by MMR, returning up to ``k`` ids (relevance-tie-stable).

    Args:
        items: ``(id, relevance, embedding)`` tuples. Relevance is the already-computed
            hybrid score; embedding is the stored chunk vector (may be empty).
        lam: MMR lambda in ``[0, 1]`` — relevance weight vs. diversity weight.
        k: number of ids to emit (the window MMR is applied over).

    The input order is used only as a stable tiebreaker; selection is greedy over the
    marginal-relevance objective. Items whose embedding is missing simply contribute
    zero similarity to picked items (treated as maximally diverse).
    """
    if k <= 0 or not items:
        return []
    lam = min(1.0, max(0.0, lam))
    remaining = list(range(len(items)))
    picked: list[int] = []
    limit = min(k, len(items))

    while remaining and len(picked) < limit:
        best_idx: int | None = None
        best_val = -math.inf
        for idx in remaining:
            _id, relevance, emb = items[idx]
            if picked:
                max_sim = max(cosine_similarity(emb, items[p][2]) for p in picked)
            else:
                max_sim = 0.0
            mmr = lam * relevance - (1.0 - lam) * max_sim
            if mmr > best_val:
                best_val = mmr
                best_idx = idx
        assert best_idx is not None
        picked.append(best_idx)
        remaining.remove(best_idx)

    return [items[i][0] for i in picked]

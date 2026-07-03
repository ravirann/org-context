"""Embedding providers. Default is deterministic and offline (no API keys needed)."""

from __future__ import annotations

import hashlib
import math
import random
from typing import Protocol

from context_engine.config.constants import EMBEDDING_DIM


class EmbeddingProvider(Protocol):
    """Protocol for pluggable embedding providers."""

    dim: int

    def embed(self, text: str) -> list[float]:
        """Return an embedding vector for the given text."""
        ...


class DeterministicEmbeddingProvider:
    """Stable hash-based embeddings: sha256-seeded RNG per text, L2-normalized."""

    def __init__(self, dim: int = EMBEDDING_DIM) -> None:
        self.dim = dim

    def embed(self, text: str) -> list[float]:
        seed = int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest()[:8], "big")
        rng = random.Random(seed)
        values = [rng.gauss(0.0, 1.0) for _ in range(self.dim)]
        norm = math.sqrt(sum(v * v for v in values)) or 1.0
        return [v / norm for v in values]


_default_provider = DeterministicEmbeddingProvider()


def get_embedding_provider() -> EmbeddingProvider:
    """Return the default embedding provider."""
    return _default_provider


def embed_text(text: str) -> list[float]:
    """Embed text with the default provider (384-dim, deterministic)."""
    return _default_provider.embed(text)

"""Embedding provider registry.

The configured provider is selected from ``settings.embedding_provider``. Every
provider emits 384-dim, L2-normalized vectors so the ``Vector(384)`` column stays
valid regardless of which one is active. The default (**deterministic**) needs no
API keys and no network — it wraps a stable hash impl and backs seeds/tests.

Public surface (pinned by PHASE3_CONTRACT §A):

* ``EmbeddingProvider`` protocol — ``name``/``model``/``dim`` + ``embed_texts``.
* ``get_embedding_provider()`` — cached, resettable via ``reset_provider_cache()``.
* ``embed_texts`` / ``embed_query`` — async, via the configured provider (batched ≤64).
* ``embed_text`` — sync deterministic impl kept for seeds/tests/back-compat.
* ``current_embedding_version()`` — ``f"{provider.name}/{provider.model}"``.
"""

from __future__ import annotations

import asyncio
import hashlib
import math
import random
import time
from typing import Protocol, runtime_checkable

import httpx

from context_engine.config.constants import EMBEDDING_DIM
from context_engine.config.settings import get_settings
from context_engine.observability.logging import get_logger

logger = get_logger(__name__)

_OPENAI_MAX_RETRIES = 3
_OPENAI_BACKOFF_BASE = 0.5


def _l2_normalize(vector: list[float]) -> list[float]:
    """Return ``vector`` scaled to unit L2 norm (zero-vector safe)."""
    norm = math.sqrt(sum(v * v for v in vector)) or 1.0
    return [v / norm for v in vector]


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Protocol for pluggable embedding providers. All emit ``dim``-length vectors."""

    name: str
    model: str
    dim: int

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Return one embedding vector per input text."""
        ...


class DeterministicEmbeddingProvider:
    """Stable hash-based embeddings: sha256-seeded RNG per text, L2-normalized."""

    name = "deterministic"
    model = "sha256-v1"

    def __init__(self, dim: int = EMBEDDING_DIM) -> None:
        self.dim = dim

    def _embed_one(self, text: str) -> list[float]:
        seed = int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest()[:8], "big")
        rng = random.Random(seed)
        values = [rng.gauss(0.0, 1.0) for _ in range(self.dim)]
        return _l2_normalize(values)

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]


class OpenAIEmbeddingProvider:
    """OpenAI ``text-embedding-3-small`` at 384 dims via the REST embeddings API.

    Retries 429/5xx with exponential backoff. An ``httpx`` transport may be
    injected for tests; otherwise a default async client is built per request.
    """

    name = "openai"
    model = "text-embedding-3-small"

    def __init__(
        self,
        api_key: str,
        base_url: str,
        dim: int = EMBEDDING_DIM,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if not api_key:
            raise RuntimeError(
                "OpenAI embedding provider requires an API key "
                "(set CE_OPENAI_API_KEY or switch CE_EMBEDDING_PROVIDER)."
            )
        self.dim = dim
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._transport = transport

    async def _post(self, batch: list[str]) -> list[list[float]]:
        payload = {"model": self.model, "input": batch, "dimensions": self.dim}
        headers = {"Authorization": f"Bearer {self._api_key}"}
        url = f"{self._base_url}/embeddings"
        last_exc: Exception | None = None
        async with httpx.AsyncClient(transport=self._transport, timeout=30.0) as client:
            for attempt in range(_OPENAI_MAX_RETRIES):
                try:
                    response = await client.post(url, json=payload, headers=headers)
                except httpx.HTTPError as exc:  # network error → retry
                    last_exc = exc
                else:
                    if response.status_code == 429 or response.status_code >= 500:
                        last_exc = RuntimeError(
                            f"OpenAI embeddings returned {response.status_code}"
                        )
                    else:
                        response.raise_for_status()
                        data = response.json()["data"]
                        return [_l2_normalize(item["embedding"]) for item in data]
                if attempt < _OPENAI_MAX_RETRIES - 1:
                    await asyncio.sleep(_OPENAI_BACKOFF_BASE * (2**attempt))
        raise RuntimeError("OpenAI embeddings failed after retries") from last_exc

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        batch_size = max(1, get_settings().embedding_batch_size)
        out: list[list[float]] = []
        for start in range(0, len(texts), batch_size):
            out.extend(await self._post(texts[start : start + batch_size]))
        return out


class FastEmbedEmbeddingProvider:
    """Local ``BAAI/bge-small-en-v1.5`` (384-dim) via the optional ``fastembed`` extra.

    The dependency is imported lazily inside ``__init__`` so importing this module
    never requires ``fastembed``. The underlying model is synchronous, so calls run
    in a worker thread via ``asyncio.to_thread``.
    """

    name = "fastembed"
    model = "BAAI/bge-small-en-v1.5"

    def __init__(self, dim: int = EMBEDDING_DIM) -> None:
        try:
            from fastembed import TextEmbedding
        except ImportError as exc:  # pragma: no cover - exercised via importorskip
            raise RuntimeError(
                "fastembed is not installed. Install the optional extra: "
                "`uv sync --extra local-embeddings`."
            ) from exc
        self.dim = dim
        self._model = TextEmbedding(model_name=self.model)

    def _embed_sync(self, texts: list[str]) -> list[list[float]]:
        return [_l2_normalize(list(vec)) for vec in self._model.embed(texts)]

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        return await asyncio.to_thread(self._embed_sync, texts)


_PROVIDER_NAMES = ("deterministic", "openai", "fastembed")

_cached_provider: EmbeddingProvider | None = None


def _build_provider(name: str) -> EmbeddingProvider:
    settings = get_settings()
    if name == "deterministic":
        return DeterministicEmbeddingProvider(dim=settings.embedding_dim)
    if name == "openai":
        return OpenAIEmbeddingProvider(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            dim=settings.embedding_dim,
        )
    if name == "fastembed":
        return FastEmbedEmbeddingProvider(dim=settings.embedding_dim)
    raise ValueError(
        f"Unknown embedding provider {name!r}. Valid names: {', '.join(_PROVIDER_NAMES)}."
    )


def get_embedding_provider() -> EmbeddingProvider:
    """Return the configured embedding provider (cached; see ``reset_provider_cache``)."""
    global _cached_provider
    if _cached_provider is None:
        _cached_provider = _build_provider(get_settings().embedding_provider)
    return _cached_provider


def set_provider_cache(provider: EmbeddingProvider) -> None:
    """Install ``provider`` as the cached instance (test hook for fakes)."""
    global _cached_provider
    _cached_provider = provider


def reset_provider_cache() -> None:
    """Clear the cached provider so the next call re-reads settings."""
    global _cached_provider
    _cached_provider = None


def current_embedding_version() -> str:
    """``f"{provider.name}/{provider.model}"`` of the configured provider."""
    provider = get_embedding_provider()
    return f"{provider.name}/{provider.model}"


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed ``texts`` via the configured provider (providers batch internally ≤64)."""
    return await get_embedding_provider().embed_texts(texts)


async def embed_query(text: str) -> list[float]:
    """Embed a single query string via the configured provider."""
    vectors = await embed_texts([text])
    return vectors[0]


_DETERMINISTIC = DeterministicEmbeddingProvider()


def embed_text(text: str) -> list[float]:
    """Sync deterministic embedding (kept for seeds/tests/back-compat, 384-dim)."""
    return _DETERMINISTIC._embed_one(text)


# Timing helper used by the reindex path for progress logging.
def _now() -> float:
    return time.monotonic()

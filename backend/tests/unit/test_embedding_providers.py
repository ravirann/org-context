"""Unit tests for the embedding provider registry (PHASE3_CONTRACT §A)."""

from __future__ import annotations

import json
import math

import httpx
import pytest

from context_engine.config.settings import get_settings
from context_engine.indexing import embeddings as emb


def _is_normalized(vector: list[float]) -> bool:
    return math.isclose(math.sqrt(sum(v * v for v in vector)), 1.0, rel_tol=1e-6)


@pytest.fixture(autouse=True)
def _reset_caches() -> object:
    emb.reset_provider_cache()
    get_settings.cache_clear()
    yield
    emb.reset_provider_cache()
    get_settings.cache_clear()


# --------------------------------------------------------------------------- #
# Deterministic provider                                                       #
# --------------------------------------------------------------------------- #


async def test_deterministic_is_stable_and_normalized() -> None:
    provider = emb.DeterministicEmbeddingProvider()
    a, b = await provider.embed_texts(["hello world", "hello world"])
    assert a == b  # deterministic
    assert len(a) == emb.EMBEDDING_DIM
    assert _is_normalized(a)


def test_embed_text_sync_matches_provider() -> None:
    assert emb.embed_text("payload") == emb.embed_text("payload")
    assert len(emb.embed_text("payload")) == emb.EMBEDDING_DIM


def test_deterministic_version_string() -> None:
    assert emb.current_embedding_version() == "deterministic/sha256-v1"


async def test_embed_query_returns_single_vector() -> None:
    vec = await emb.embed_query("a query")
    assert len(vec) == emb.EMBEDDING_DIM
    assert _is_normalized(vec)


# --------------------------------------------------------------------------- #
# Provider selection / cache                                                   #
# --------------------------------------------------------------------------- #


def test_unknown_provider_raises_value_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CE_EMBEDDING_PROVIDER", "nope")
    get_settings.cache_clear()
    emb.reset_provider_cache()
    with pytest.raises(ValueError, match="Unknown embedding provider"):
        emb.get_embedding_provider()


def test_provider_cache_and_reset() -> None:
    first = emb.get_embedding_provider()
    assert emb.get_embedding_provider() is first
    emb.reset_provider_cache()
    assert emb.get_embedding_provider() is not first


def test_set_provider_cache_hook() -> None:
    class Fake:
        name = "fake"
        model = "m1"
        dim = emb.EMBEDDING_DIM

        async def embed_texts(self, texts: list[str]) -> list[list[float]]:
            return [[0.0] * self.dim for _ in texts]

    fake = Fake()
    emb.set_provider_cache(fake)
    assert emb.get_embedding_provider() is fake
    assert emb.current_embedding_version() == "fake/m1"


# --------------------------------------------------------------------------- #
# OpenAI provider (via httpx.MockTransport)                                    #
# --------------------------------------------------------------------------- #


def _openai_transport(calls: list[dict[str, object]]) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        calls.append(body)
        inputs = body["input"]
        data = [
            {"embedding": [float((i + 1) % 7) for _ in range(emb.EMBEDDING_DIM)]}
            for i, _ in enumerate(inputs)
        ]
        return httpx.Response(200, json={"data": data})

    return httpx.MockTransport(handler)


async def test_openai_returns_normalized_384(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CE_EMBEDDING_BATCH_SIZE", "64")
    get_settings.cache_clear()
    calls: list[dict[str, object]] = []
    provider = emb.OpenAIEmbeddingProvider(
        api_key="sk-test",
        base_url="https://api.openai.com/v1",
        transport=_openai_transport(calls),
    )
    vectors = await provider.embed_texts(["a", "b"])
    assert len(vectors) == 2
    assert all(len(v) == emb.EMBEDDING_DIM for v in vectors)
    assert all(_is_normalized(v) for v in vectors)
    assert calls[0]["dimensions"] == emb.EMBEDDING_DIM
    assert calls[0]["model"] == "text-embedding-3-small"


async def test_openai_batches_by_size(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CE_EMBEDDING_BATCH_SIZE", "2")
    get_settings.cache_clear()
    calls: list[dict[str, object]] = []
    provider = emb.OpenAIEmbeddingProvider(
        api_key="sk-test",
        base_url="https://api.openai.com/v1",
        transport=_openai_transport(calls),
    )
    vectors = await provider.embed_texts(["a", "b", "c", "d", "e"])
    assert len(vectors) == 5
    # 5 inputs, batch size 2 → 3 requests of sizes 2, 2, 1
    assert [len(c["input"]) for c in calls] == [2, 2, 1]  # type: ignore[arg-type]


async def test_openai_retries_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(emb.asyncio, "sleep", _noop_sleep)
    attempts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        if attempts["n"] == 1:
            return httpx.Response(429, json={"error": "rate limited"})
        if attempts["n"] == 2:
            return httpx.Response(503, json={"error": "unavailable"})
        data = [{"embedding": [1.0] * emb.EMBEDDING_DIM}]
        return httpx.Response(200, json={"data": data})

    provider = emb.OpenAIEmbeddingProvider(
        api_key="sk-test",
        base_url="https://api.openai.com/v1",
        transport=httpx.MockTransport(handler),
    )
    vectors = await provider.embed_texts(["x"])
    assert attempts["n"] == 3
    assert _is_normalized(vectors[0])


async def test_openai_raises_after_exhausting_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(emb.asyncio, "sleep", _noop_sleep)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "boom"})

    provider = emb.OpenAIEmbeddingProvider(
        api_key="sk-test",
        base_url="https://api.openai.com/v1",
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(RuntimeError, match="failed after retries"):
        await provider.embed_texts(["x"])


def test_openai_missing_key_raises() -> None:
    with pytest.raises(RuntimeError, match="requires an API key"):
        emb.OpenAIEmbeddingProvider(api_key="", base_url="https://api.openai.com/v1")


async def _noop_sleep(_seconds: float) -> None:
    return None


# --------------------------------------------------------------------------- #
# fastembed provider (optional extra)                                          #
# --------------------------------------------------------------------------- #


async def test_fastembed_provider() -> None:
    pytest.importorskip("fastembed")
    provider = emb.FastEmbedEmbeddingProvider()
    vectors = await provider.embed_texts(["hello world"])
    assert len(vectors) == 1
    assert len(vectors[0]) == emb.EMBEDDING_DIM
    assert _is_normalized(vectors[0])

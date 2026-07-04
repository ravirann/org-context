"""Integration tests for the full re-index path (PHASE3_CONTRACT §A)."""

from __future__ import annotations

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from context_engine.indexing import embeddings as emb
from context_engine.indexing.reindex import reindex_all
from context_engine.storage.models import Chunk, DocStatus, Document


async def _active_doc_count(session: AsyncSession) -> int:
    return int(
        (
            await session.execute(
                select(func.count())
                .select_from(Document)
                .where(Document.status == DocStatus.active)
            )
        ).scalar_one()
    )


async def _active_chunk_rows(session: AsyncSession) -> list[Chunk]:
    """Chunks belonging to active documents (the set reindex_all rewrites)."""
    stmt = (
        select(Chunk)
        .join(Document, Document.id == Chunk.document_id)
        .where(Document.status == DocStatus.active)
    )
    return list((await session.execute(stmt)).scalars().all())


@pytest.fixture(autouse=True)
def _reset_provider() -> object:
    emb.reset_provider_cache()
    yield
    emb.reset_provider_cache()


async def test_reindex_regenerates_chunks_and_stamps_version(
    seeded_session: AsyncSession,
) -> None:
    before = await _active_chunk_rows(seeded_session)
    assert before, "seed should produce chunks"
    old_ids = {c.id for c in before}
    doc_count = await _active_doc_count(seeded_session)

    processed = await reindex_all(seeded_session)

    assert processed == doc_count
    after = await _active_chunk_rows(seeded_session)
    new_ids = {c.id for c in after}
    # Chunks were deleted and re-created → fresh ids.
    assert new_ids.isdisjoint(old_ids)
    # Deterministic chunker → same chunk count for the same content.
    assert len(after) == len(before)
    # Every chunk stamped with the configured (deterministic) version.
    assert {c.embedding_version for c in after} == {"deterministic/sha256-v1"}
    assert all(c.embedding is not None for c in after)


async def test_reindex_swaps_embedding_version_with_fake_provider(
    seeded_session: AsyncSession,
) -> None:
    class FakeProvider:
        name = "fake"
        model = "m1"
        dim = emb.EMBEDDING_DIM

        async def embed_texts(self, texts: list[str]) -> list[list[float]]:
            return [[0.1] * self.dim for _ in texts]

    emb.set_provider_cache(FakeProvider())

    processed = await reindex_all(seeded_session)
    assert processed > 0

    after = await _active_chunk_rows(seeded_session)
    assert {c.embedding_version for c in after} == {"fake/m1"}

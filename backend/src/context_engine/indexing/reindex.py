"""Full re-index path: re-chunk + re-embed every active document.

Used when the configured embedding provider changes (so stored vectors and their
``embedding_version`` stamp go stale). Iterates active documents in id-ordered
batches to bound memory, re-embeds each doc's chunks through the async batch API,
and replaces the doc's chunks in place. Returns the number of documents processed.
"""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from context_engine.indexing.chunking import chunk_text
from context_engine.indexing.embeddings import current_embedding_version, embed_texts
from context_engine.indexing.tokens import estimate_tokens
from context_engine.observability.logging import get_logger
from context_engine.storage.models import Chunk, DocStatus, Document

logger = get_logger(__name__)


async def reindex_all(session: AsyncSession, batch: int = 200) -> int:
    """Re-chunk and re-embed all active documents; stamp ``embedding_version``.

    Documents are processed in id-ordered batches of ``batch``. For each doc,
    existing chunks are deleted and freshly computed chunks inserted with the
    current provider's embedding version. Returns the document count.
    """
    version = current_embedding_version()
    processed = 0
    last_id: object | None = None

    while True:
        stmt = (
            select(Document.id)
            .where(Document.status == DocStatus.active)
            .order_by(Document.id)
            .limit(batch)
        )
        if last_id is not None:
            stmt = stmt.where(Document.id > last_id)
        doc_ids = list((await session.execute(stmt)).scalars().all())
        if not doc_ids:
            break

        for doc_id in doc_ids:
            doc = await session.get(Document, doc_id)
            if doc is None:
                continue
            await session.execute(delete(Chunk).where(Chunk.document_id == doc.id))
            pieces = chunk_text(doc.content)
            embeddings = await embed_texts(pieces)
            session.add_all(
                Chunk(
                    document_id=doc.id,
                    ord=i,
                    content=piece,
                    token_count=estimate_tokens(piece),
                    embedding=embedding,
                    embedding_version=version,
                )
                for i, (piece, embedding) in enumerate(zip(pieces, embeddings, strict=True))
            )
            processed += 1

        last_id = doc_ids[-1]
        await session.flush()
        logger.info("reindex_progress", processed=processed, embedding_version=version)

    logger.info("reindex_complete", documents=processed, embedding_version=version)
    return processed

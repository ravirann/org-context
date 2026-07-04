"""Paragraph-aware text chunking and document (re)indexing."""

from __future__ import annotations

import re

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from context_engine.config.constants import CHUNK_SIZE_CHARS
from context_engine.indexing.embeddings import current_embedding_version, embed_texts
from context_engine.indexing.tokens import estimate_tokens
from context_engine.storage.models import Chunk, Document

DEFAULT_OVERLAP_CHARS = 80


def _split_long_paragraph(paragraph: str, target_chars: int) -> list[str]:
    """Split a single oversized paragraph at word boundaries."""
    pieces: list[str] = []
    remaining = paragraph
    while len(remaining) > target_chars:
        cut = remaining.rfind(" ", max(1, int(target_chars * 0.5)), target_chars)
        if cut <= 0:
            cut = target_chars
        pieces.append(remaining[:cut].strip())
        remaining = remaining[cut:].strip()
    if remaining:
        pieces.append(remaining)
    return pieces


def _overlap_tail(chunk: str, overlap: int) -> str:
    """Return the trailing ~``overlap`` chars of ``chunk``, cut at a word boundary."""
    if overlap <= 0:
        return ""
    tail = chunk[-overlap:]
    if len(tail) < len(chunk):
        space = tail.find(" ")
        if 0 <= space < len(tail) - 1:
            tail = tail[space + 1 :]
    return tail.strip()


def chunk_text(
    text: str, target_chars: int = CHUNK_SIZE_CHARS, overlap: int = DEFAULT_OVERLAP_CHARS
) -> list[str]:
    """Split ``text`` into ~``target_chars`` chunks along paragraph boundaries.

    Paragraphs (blank-line separated) are packed into chunks; when a chunk
    fills up, the tail of the previous chunk is carried into the next one as
    overlap. Deterministic; never returns an empty list.
    """
    cleaned = text.strip()
    if not cleaned:
        return [cleaned]

    segments: list[str] = []
    for paragraph in re.split(r"\n\s*\n", cleaned):
        normalized = " ".join(paragraph.split())
        if not normalized:
            continue
        if len(normalized) > target_chars:
            segments.extend(_split_long_paragraph(normalized, target_chars))
        else:
            segments.append(normalized)

    chunks: list[str] = []
    current = ""
    for segment in segments:
        candidate = f"{current}\n\n{segment}" if current else segment
        if current and len(candidate) > target_chars:
            chunks.append(current)
            tail = _overlap_tail(current, overlap)
            current = f"{tail}\n\n{segment}" if tail else segment
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks or [cleaned]


async def index_document(session: AsyncSession, doc: Document) -> int:
    """Replace the document's chunks (content, tokens, embedding); return the count."""
    await session.execute(delete(Chunk).where(Chunk.document_id == doc.id))
    pieces = chunk_text(doc.content)
    embeddings = await embed_texts([piece for piece in pieces])
    version = current_embedding_version()
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
    await session.flush()
    return len(pieces)

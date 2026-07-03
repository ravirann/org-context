"""Unit tests for paragraph-aware chunking."""

from __future__ import annotations

from context_engine.indexing.chunking import chunk_text

TARGET = 600
OVERLAP = 80


def _long_text(paragraphs: int = 12) -> str:
    return "\n\n".join(
        f"marker{i} " + f"paragraph {i} discusses retry policies and pagination. " * 4
        for i in range(paragraphs)
    )


def test_short_text_is_a_single_chunk() -> None:
    assert chunk_text("hello world") == ["hello world"]


def test_short_multi_paragraph_text_stays_together() -> None:
    assert chunk_text("alpha\n\nbeta") == ["alpha\n\nbeta"]


def test_empty_and_whitespace_inputs_never_return_empty_list() -> None:
    assert chunk_text("") == [""]
    assert chunk_text("   \n\n \t ") == [""]


def test_deterministic() -> None:
    text = _long_text()
    assert chunk_text(text) == chunk_text(text)


def test_long_text_produces_bounded_chunks() -> None:
    chunks = chunk_text(_long_text())
    assert len(chunks) > 1
    for chunk in chunks:
        assert chunk.strip()
        assert len(chunk) <= TARGET + OVERLAP + 2


def test_all_paragraphs_are_covered() -> None:
    chunks = chunk_text(_long_text())
    joined = " ".join(chunks)
    for i in range(12):
        assert f"marker{i}" in joined


def test_consecutive_chunks_overlap() -> None:
    chunks = chunk_text(_long_text())
    assert len(chunks) >= 3
    for prev, nxt in zip(chunks, chunks[1:], strict=False):
        head = nxt.split("\n\n")[0]
        assert head and head in prev, "next chunk must start with the tail of the previous"


def test_single_giant_paragraph_is_split_at_word_boundaries() -> None:
    text = "word " * 600  # ~3000 chars, no blank lines
    chunks = chunk_text(text)
    assert len(chunks) >= 4
    for chunk in chunks:
        assert len(chunk) <= TARGET + OVERLAP + 2
        assert "word" in chunk
        assert "wo rd" not in chunk  # no mid-word cuts


def test_unbroken_text_without_spaces_is_hard_cut() -> None:
    chunks = chunk_text("x" * 2000)
    assert len(chunks) >= 3
    assert all(len(c) <= TARGET + OVERLAP + 2 for c in chunks)
    assert sum(len(c.replace("\n\n", "")) for c in chunks) >= 2000  # nothing lost


def test_custom_target_and_overlap() -> None:
    text = "\n\n".join(f"para {i} " + "x" * 50 for i in range(10))
    chunks = chunk_text(text, target_chars=120, overlap=20)
    assert len(chunks) > 2
    assert all(len(c) <= 120 + 20 + 2 for c in chunks)


def test_zero_overlap_disables_tail_carry() -> None:
    chunks = chunk_text(_long_text(), overlap=0)
    assert len(chunks) > 1
    for prev, nxt in zip(chunks, chunks[1:], strict=False):
        assert nxt.split("\n\n")[0] not in prev

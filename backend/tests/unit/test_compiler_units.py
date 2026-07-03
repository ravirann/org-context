"""Unit tests for pure compiler/retrieval helpers: budget packing, snippets, jaccard."""

from __future__ import annotations

from context_engine.context_compiler.compiler import pack_budget
from context_engine.reasoning.conflicts import token_jaccard
from context_engine.retrieval.service import build_snippet


class TestPackBudget:
    def test_all_fit(self) -> None:
        kept, overflow = pack_budget([10, 20, 30], 100)
        assert kept == [0, 1, 2]
        assert overflow == []

    def test_overflow_rejected_in_order(self) -> None:
        kept, overflow = pack_budget([60, 60, 60], 100)
        assert kept == [0]
        assert overflow == [1, 2]

    def test_smaller_later_item_still_fits(self) -> None:
        kept, overflow = pack_budget([80, 50, 15], 100)
        assert kept == [0, 2]
        assert overflow == [1]

    def test_zero_budget_rejects_everything(self) -> None:
        kept, overflow = pack_budget([1, 2], 0)
        assert kept == []
        assert overflow == [0, 1]

    def test_empty_items(self) -> None:
        assert pack_budget([], 100) == ([], [])

    def test_exact_fit(self) -> None:
        kept, overflow = pack_budget([50, 50], 100)
        assert kept == [0, 1]
        assert overflow == []


class TestBuildSnippet:
    def test_short_content_returned_whole(self) -> None:
        assert build_snippet("short text", "text") == "short text"

    def test_centers_on_first_query_term(self) -> None:
        content = ("padding " * 60) + "IDEMPOTENCY anchor here " + ("tail " * 60)
        snippet = build_snippet(content, "idempotency keys")
        assert "IDEMPOTENCY" in snippet
        assert len(snippet) <= 240 + 2  # width plus ellipses

    def test_no_term_match_uses_prefix(self) -> None:
        content = "alpha " * 100
        snippet = build_snippet(content, "zzz-not-there")
        assert snippet.startswith("alpha")
        assert snippet.endswith("…")

    def test_empty_query_uses_prefix(self) -> None:
        content = "beta " * 100
        snippet = build_snippet(content, "")
        assert snippet.startswith("beta")
        assert len(snippet) <= 241

    def test_whitespace_collapsed(self) -> None:
        assert build_snippet("a\n\n  b\tc", "a") == "a b c"

    def test_ellipses_on_both_sides_for_middle_match(self) -> None:
        content = ("x " * 200) + "needle" + (" y" * 200)
        snippet = build_snippet(content, "needle")
        assert snippet.startswith("…")
        assert snippet.endswith("…")
        assert "needle" in snippet


class TestTokenJaccard:
    def test_identical_texts(self) -> None:
        assert token_jaccard("retry with backoff", "retry with backoff") == 1.0

    def test_disjoint_texts(self) -> None:
        assert token_jaccard("alpha beta", "gamma delta") == 0.0

    def test_partial_overlap(self) -> None:
        value = token_jaccard("retry with jitter", "retry with delay")
        assert 0.0 < value < 1.0

    def test_case_insensitive(self) -> None:
        assert token_jaccard("Retry Backoff", "retry backoff") == 1.0

    def test_both_empty(self) -> None:
        assert token_jaccard("", "") == 1.0

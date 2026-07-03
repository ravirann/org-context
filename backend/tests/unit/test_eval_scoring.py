"""Table-driven unit tests for evals.scoring and evals.report (no DB needed)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import pytest

from context_engine.evals import scoring
from context_engine.evals.baseline import BaselineHit, build_baseline_context
from context_engine.evals.report import format_report
from context_engine.storage import models as m

# ---------------------------------------------------------------------------
# retrieval_scores
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("expected", "got", "precision", "recall", "f1"),
    [
        ([], [], 1.0, 1.0, 1.0),  # nothing to find, nothing retrieved
        ([], ["a"], 0.0, 1.0, 0.0),  # noise retrieved, but nothing was expected
        (["a"], [], 0.0, 0.0, 0.0),  # expected docs, retrieved nothing
        (["a", "b"], ["a", "b"], 1.0, 1.0, 1.0),
        (["a", "b"], ["a", "c"], 0.5, 0.5, 0.5),
        (["a"], ["a", "b", "c"], 1 / 3, 1.0, 0.5),
        (["a", "b", "c", "d"], ["a"], 1.0, 0.25, 0.4),
        (["a"], ["a", "a"], 1.0, 1.0, 1.0),  # duplicates collapse to sets
        (["a"], ["b"], 0.0, 0.0, 0.0),
    ],
)
def test_retrieval_scores(
    expected: list[str], got: list[str], precision: float, recall: float, f1: float
) -> None:
    scores = scoring.retrieval_scores(expected, got)
    assert scores["precision"] == pytest.approx(precision)
    assert scores["recall"] == pytest.approx(recall)
    assert scores["f1"] == pytest.approx(f1)


# ---------------------------------------------------------------------------
# keyword_score / missing_keywords
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "keywords", "expected"),
    [
        ("anything", [], 1.0),  # no expectations -> perfect
        ("", ["jitter"], 0.0),
        ("Exponential BACKOFF with jitter", ["exponential", "backoff", "jitter"], 1.0),
        ("exponential only", ["exponential", "jitter"], 0.5),
        ("UPPER case MATCH", ["upper", "MATCH"], 1.0),  # case-insensitive both ways
        ("nothing relevant here", ["idempotency"], 0.0),
    ],
)
def test_keyword_score(text: str, keywords: list[str], expected: float) -> None:
    assert scoring.keyword_score(text, keywords) == pytest.approx(expected)


@pytest.mark.parametrize(
    ("text", "keywords", "expected"),
    [
        ("", [], []),
        ("exponential backoff", ["exponential", "jitter"], ["jitter"]),
        ("all here: cursor pagination", ["cursor", "pagination"], []),
        ("", ["a", "b"], ["a", "b"]),
    ],
)
def test_missing_keywords(text: str, keywords: list[str], expected: list[str]) -> None:
    assert scoring.missing_keywords(text, keywords) == expected


# ---------------------------------------------------------------------------
# citations_ok
# ---------------------------------------------------------------------------


def _citation(marker: str | None, document_id: str | None) -> dict[str, Any]:
    citation: dict[str, Any] = {"title": "t", "url": "u", "quote": "q"}
    if marker is not None:
        citation["marker"] = marker
    if document_id is not None:
        citation["document_id"] = document_id
    return citation


@pytest.mark.parametrize(
    ("citations", "selected", "expected"),
    [
        ([], ["d1"], True),  # vacuously ok
        ([], [], True),
        ([_citation("S1", "d1")], ["d1"], True),
        ([_citation("S1", "d1"), _citation("S2", "d2")], ["d1", "d2"], True),
        ([_citation("S1", "d1"), _citation("S1", "d2")], ["d1", "d2"], False),  # dup marker
        ([_citation("S1", "d3")], ["d1", "d2"], False),  # cites unselected doc
        ([_citation(None, "d1")], ["d1"], False),  # missing marker
        ([_citation("S1", None)], ["d1"], False),  # missing document_id
        ([_citation("S1", "d1")], [], False),  # nothing selected at all
    ],
)
def test_citations_ok(citations: list[dict[str, Any]], selected: list[str], expected: bool) -> None:
    assert scoring.citations_ok(citations, selected) is expected


# ---------------------------------------------------------------------------
# token_efficiency / task_score
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("tokens", "budget", "expected"),
    [
        (0, 6000, 1.0),
        (3000, 6000, 0.5),
        (6000, 6000, 0.0),
        (12000, 6000, 0.0),  # clamped
        (-5, 6000, 1.0),  # negative treated as zero
        (100, 0, 0.0),  # degenerate budget
        (1500, 6000, 0.75),
    ],
)
def test_token_efficiency(tokens: int, budget: int, expected: float) -> None:
    assert scoring.token_efficiency(tokens, budget) == pytest.approx(expected)


def test_token_efficiency_default_budget() -> None:
    assert scoring.token_efficiency(3000) == pytest.approx(0.5)


@pytest.mark.parametrize(
    ("f1", "keyword", "citations", "efficiency", "expected"),
    [
        (1.0, 1.0, True, 1.0, 1.0),
        (0.0, 0.0, False, 0.0, 0.0),
        (1.0, 0.0, False, 0.0, 0.4),
        (0.0, 1.0, False, 0.0, 0.35),
        (0.0, 0.0, True, 0.0, 0.15),
        (0.0, 0.0, False, 1.0, 0.10),
        (0.5, 0.5, True, 0.5, 0.4 * 0.5 + 0.35 * 0.5 + 0.15 + 0.10 * 0.5),
    ],
)
def test_task_score(
    f1: float, keyword: float, citations: bool, efficiency: float, expected: float
) -> None:
    assert scoring.task_score(f1, keyword, citations, efficiency) == pytest.approx(expected)


def test_task_score_clamped_to_unit_interval() -> None:
    assert scoring.task_score(2.0, 2.0, True, 2.0) == 1.0
    assert scoring.task_score(-1.0, -1.0, False, -1.0) == 0.0


# ---------------------------------------------------------------------------
# is_regression
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("current", "previous", "delta", "expected"),
    [
        (0.5, 0.6, 0.05, True),  # dropped 0.10 > 0.05
        (0.56, 0.6, 0.05, False),  # dropped 0.04 <= 0.05
        (0.55, 0.6, 0.05, False),  # boundary: exactly the threshold is NOT a regression
        (0.7, 0.6, 0.05, False),  # improved
        (0.6, 0.6, 0.05, False),  # flat
        (0.5, None, 0.05, False),  # no previous run
        (0.0, 1.0, 0.99, True),
    ],
)
def test_is_regression(
    current: float, previous: float | None, delta: float, expected: bool
) -> None:
    assert scoring.is_regression(current, previous, delta) is expected


# ---------------------------------------------------------------------------
# build_baseline_context (pure helper)
# ---------------------------------------------------------------------------


def test_build_baseline_context_concatenates_and_caps() -> None:
    hits = [
        BaselineHit(document_id="d1", title="Doc One", content="alpha " * 10, score=0.9),
        BaselineHit(document_id="d2", title="Doc Two", content="beta " * 10, score=0.5),
    ]
    text = build_baseline_context(hits)
    assert "## Doc One" in text
    assert "## Doc Two" in text
    assert text.index("Doc One") < text.index("Doc Two")

    big = [
        BaselineHit(document_id=str(i), title=f"D{i}", content="x" * 5000, score=1.0)
        for i in range(5)
    ]
    capped = build_baseline_context(big, max_chars=8000)
    assert len(capped) <= 8000


def test_build_baseline_context_empty() -> None:
    assert build_baseline_context([]) == ""


# ---------------------------------------------------------------------------
# format_report
# ---------------------------------------------------------------------------


def _make_run(summary: dict[str, Any], mode: m.EvalMode = m.EvalMode.comparison) -> m.EvalRun:
    return m.EvalRun(
        id=uuid.uuid4(),
        mode=mode,
        status=m.EvalRunStatus.completed,
        started_at=datetime(2026, 7, 1, 12, 0, tzinfo=UTC),
        finished_at=datetime(2026, 7, 1, 12, 5, tzinfo=UTC),
        summary=summary,
    )


def _make_result(
    task: m.EvalTask, mode: m.EvalResultMode, score: float, passed: bool, tokens: int
) -> m.EvalResult:
    return m.EvalResult(
        id=uuid.uuid4(),
        eval_run_id=uuid.uuid4(),
        eval_task_id=task.id,
        eval_task=task,
        mode=mode,
        score=score,
        passed=passed,
        explanation="",
        tokens_used=tokens,
        details={},
    )


def _make_task(name: str) -> m.EvalTask:
    return m.EvalTask(
        id=uuid.uuid4(),
        name=name,
        task=f"question for {name}",
        expected_document_ids=[],
        expected_keywords=[],
        is_active=True,
    )


def test_format_report_comparison_table() -> None:
    task_a = _make_task("payments-retry-policy")
    task_b = _make_task("auth-token-ttl")
    run = _make_run(
        {
            "avg_score": 0.8,
            "pass_rate": 1.0,
            "total_tokens": 2100,
            "baseline_avg_score": 0.45,
            "baseline_total_tokens": 7800,
            "regression": False,
            "regressed_task_names": [],
        }
    )
    results = [
        _make_result(task_a, m.EvalResultMode.baseline, 0.45, False, 7800),
        _make_result(task_a, m.EvalResultMode.context_engine, 0.8, True, 2100),
        _make_result(task_b, m.EvalResultMode.baseline, 0.5, False, 6400),
        _make_result(task_b, m.EvalResultMode.context_engine, 0.9, True, 1800),
    ]
    report = format_report(run, results)
    assert "payments-retry-policy" in report
    assert "auth-token-ttl" in report
    assert "+0.350" in report  # engine - baseline delta for task_a
    assert "+0.400" in report  # delta for task_b
    assert "0.450 FAIL" in report
    assert "0.800 PASS" in report
    assert "7800/2100" in report
    assert "avg_score: 0.8" in report
    assert "baseline_avg_score: 0.45" in report
    assert "REGRESSION" not in report


def test_format_report_regression_banner() -> None:
    task = _make_task("payments-retry-policy")
    run = _make_run(
        {
            "avg_score": 0.4,
            "pass_rate": 0.0,
            "total_tokens": 900,
            "regression": True,
            "regressed_task_names": ["payments-retry-policy"],
        }
    )
    results = [_make_result(task, m.EvalResultMode.context_engine, 0.4, False, 900)]
    report = format_report(run, results)
    assert "!!! REGRESSION DETECTED !!!" in report
    assert "regressed tasks: payments-retry-policy" in report


def test_format_report_single_leg_and_missing_task_relationship() -> None:
    # Result without the eval_task relationship loaded falls back to the id.
    result = m.EvalResult(
        id=uuid.uuid4(),
        eval_run_id=uuid.uuid4(),
        eval_task_id=uuid.uuid4(),
        mode=m.EvalResultMode.baseline,
        score=0.3,
        passed=False,
        explanation="",
        tokens_used=1200,
        details={},
    )
    run = _make_run(
        {"avg_score": 0.3, "pass_rate": 0.0, "total_tokens": 1200, "regression": False},
        mode=m.EvalMode.baseline,
    )
    run.finished_at = None  # still running / crashed before finishing
    report = format_report(run, [result])
    assert str(result.eval_task_id) in report
    assert "0.300 FAIL" in report
    assert "1200/-" in report  # only the baseline leg has tokens
    assert "Finished: -" in report


def test_format_report_no_results_and_error_summary() -> None:
    run = _make_run({"error": "boom"})
    run.status = m.EvalRunStatus.failed
    report = format_report(run, [])
    assert "(no results)" in report
    assert "error: boom" in report
    assert "status=failed" in report

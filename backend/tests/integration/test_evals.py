"""Integration tests for the eval harness against a seeded Postgres database."""

from __future__ import annotations

import importlib
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from context_engine.evals import actors, scoring
from context_engine.evals.baseline import baseline_retrieve
from context_engine.evals.harness import execute_eval_run, run_eval
from context_engine.storage import models as m


def _compiler_available() -> bool:
    try:
        importlib.import_module("context_engine.context_compiler.compiler")
    except ImportError:
        return False
    return True


async def _get_user(session: AsyncSession, email: str) -> m.User:
    return (await session.execute(select(m.User).where(m.User.email == email))).scalar_one()


async def _get_doc_by_title_prefix(session: AsyncSession, prefix: str) -> m.Document:
    stmt = select(m.Document).where(m.Document.title.startswith(prefix))
    return (await session.execute(stmt)).scalars().first() or pytest.fail(
        f"seed document {prefix!r} not found"
    )


async def _create_golden_tasks(session: AsyncSession) -> list[m.EvalTask]:
    """Create extra golden tasks pointing at seed_minimal documents."""
    adr = await _get_doc_by_title_prefix(session, "ADR-0042")
    guide = await _get_doc_by_title_prefix(session, "Payments guide 1")
    tasks = [
        m.EvalTask(
            name="it-retry-policy",
            # plainto_tsquery ANDs every lexeme, so phrase the question with
            # words that actually occur in the seeded ADR content.
            task="What backoff do payment charge retries use?",
            repo="payments-api",
            service="payments-api",
            expected_document_ids=[str(adr.id)],
            expected_keywords=["exponential", "backoff", "jitter"],
            is_active=True,
        ),
        m.EvalTask(
            name="it-idempotency",
            task="How does the charge endpoint validate idempotency keys?",
            repo="payments-api",
            service="payments-api",
            expected_document_ids=[str(guide.id)],
            expected_keywords=["idempotency", "event_id"],
            is_active=True,
        ),
    ]
    session.add_all(tasks)
    await session.flush()
    return tasks


async def _active_task_count(session: AsyncSession) -> int:
    stmt = select(m.EvalTask).where(m.EvalTask.is_active.is_(True))
    return len((await session.execute(stmt)).scalars().all())


async def _results_for(session: AsyncSession, run: m.EvalRun) -> list[m.EvalResult]:
    stmt = select(m.EvalResult).where(m.EvalResult.eval_run_id == run.id)
    return list((await session.execute(stmt)).scalars().all())


# ---------------------------------------------------------------------------
# baseline retrieval
# ---------------------------------------------------------------------------


async def test_baseline_retrieve_finds_matching_docs(seeded_session: AsyncSession) -> None:
    admin = await _get_user(seeded_session, "admin@demo.dev")
    adr = await _get_doc_by_title_prefix(seeded_session, "ADR-0042")
    hits = await baseline_retrieve(
        seeded_session, admin, "exponential backoff jitter payment retries"
    )
    assert hits, "FTS baseline should match the seeded retry ADR"
    assert str(adr.id) in {hit.document_id for hit in hits}
    assert all(hit.score >= 0 for hit in hits)
    # ranked descending
    assert [hit.score for hit in hits] == sorted((hit.score for hit in hits), reverse=True)


async def test_baseline_retrieve_never_leaks_acl_restricted_docs(
    seeded_session: AsyncSession,
) -> None:
    admin = await _get_user(seeded_session, "admin@demo.dev")
    engineer = await _get_user(seeded_session, "jade@demo.dev")  # Growth team
    restricted = await _get_doc_by_title_prefix(seeded_session, "Payments postmortem")
    query = "postmortem duplicate charges customer impact"

    admin_ids = {h.document_id for h in await baseline_retrieve(seeded_session, admin, query)}
    assert str(restricted.id) in admin_ids  # admin sees the team-restricted postmortem

    engineer_ids = {h.document_id for h in await baseline_retrieve(seeded_session, engineer, query)}
    assert str(restricted.id) not in engineer_ids  # never leaked to other teams


# ---------------------------------------------------------------------------
# run_eval: baseline mode
# ---------------------------------------------------------------------------


async def test_run_eval_baseline_completes(seeded_session: AsyncSession) -> None:
    await _create_golden_tasks(seeded_session)
    active = await _active_task_count(seeded_session)

    run = await run_eval(seeded_session, m.EvalMode.baseline)

    assert run.status == m.EvalRunStatus.completed
    assert run.mode == m.EvalMode.baseline
    assert run.finished_at is not None

    results = await _results_for(seeded_session, run)
    assert len(results) == active  # one baseline row per active golden task
    assert all(result.mode == m.EvalResultMode.baseline for result in results)
    for result in results:
        assert 0.0 <= result.score <= 1.0
        assert result.tokens_used >= 1
        assert result.explanation.startswith("baseline:")
        assert set(result.details) >= {"precision", "recall", "keyword_hits", "citations_ok"}
        assert result.details["citations_ok"] is False  # naive baseline has no citations

    summary = run.summary
    assert 0.0 <= summary["avg_score"] <= 1.0
    assert 0.0 <= summary["pass_rate"] <= 1.0
    assert summary["total_tokens"] == sum(result.tokens_used for result in results)
    assert summary["regression"] is False  # no previous completed baseline run in the seed
    assert summary["regressed_task_names"] == []
    assert "baseline_avg_score" not in summary  # only present in comparison mode


async def test_run_eval_baseline_retrieves_expected_doc(seeded_session: AsyncSession) -> None:
    tasks = await _create_golden_tasks(seeded_session)
    run = await run_eval(seeded_session, m.EvalMode.baseline)
    results = await _results_for(seeded_session, run)
    by_task = {result.eval_task_id: result for result in results}
    retry_result = by_task[tasks[0].id]
    # the retry ADR is a strong FTS match for its own question
    assert retry_result.details["recall"] == pytest.approx(1.0)
    assert retry_result.details["keyword_hits"] == 3
    assert "all expected documents retrieved" in retry_result.explanation


# ---------------------------------------------------------------------------
# run_eval: comparison / engine modes
# ---------------------------------------------------------------------------


async def test_run_eval_comparison_full(seeded_session: AsyncSession) -> None:
    pytest.importorskip(
        "context_engine.context_compiler.compiler",
        reason="context_compiler is being built concurrently by another agent",
    )
    await _create_golden_tasks(seeded_session)
    active = await _active_task_count(seeded_session)

    run = await run_eval(seeded_session, m.EvalMode.comparison)
    assert run.status == m.EvalRunStatus.completed, run.summary

    results = await _results_for(seeded_session, run)
    engine_results = [r for r in results if r.mode == m.EvalResultMode.context_engine]
    baseline_results = [r for r in results if r.mode == m.EvalResultMode.baseline]
    assert len(engine_results) == active
    assert len(baseline_results) == active
    assert all(0.0 <= r.score <= 1.0 for r in results)

    summary = run.summary
    assert "baseline_avg_score" in summary
    assert "baseline_total_tokens" in summary
    assert summary["baseline_total_tokens"] == sum(r.tokens_used for r in baseline_results)
    assert isinstance(summary["regression"], bool)
    assert isinstance(summary["regressed_task_names"], list)


@pytest.mark.skipif(
    _compiler_available(), reason="context_compiler present; missing-module path unreachable"
)
async def test_run_eval_engine_mode_fails_cleanly_without_compiler(
    seeded_session: AsyncSession,
) -> None:
    await _create_golden_tasks(seeded_session)
    run = await run_eval(seeded_session, m.EvalMode.context_engine)
    assert run.status == m.EvalRunStatus.failed
    assert "context_compiler" in run.summary["error"]
    assert run.finished_at is not None


# ---------------------------------------------------------------------------
# regression detection
# ---------------------------------------------------------------------------


async def test_second_run_detects_regression(
    seeded_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    tasks = await _create_golden_tasks(seeded_session)

    monkeypatch.setattr(scoring, "task_score", lambda *args, **kwargs: 0.9)
    first = await run_eval(seeded_session, m.EvalMode.baseline)
    assert first.status == m.EvalRunStatus.completed
    assert first.summary["avg_score"] == pytest.approx(0.9)
    assert first.summary["regression"] is False

    monkeypatch.setattr(scoring, "task_score", lambda *args, **kwargs: 0.2)
    second = await run_eval(seeded_session, m.EvalMode.baseline)
    assert second.status == m.EvalRunStatus.completed
    assert second.summary["avg_score"] == pytest.approx(0.2)
    assert second.summary["regression"] is True

    regressed = second.summary["regressed_task_names"]
    assert {task.name for task in tasks} <= set(regressed)  # every task's score dropped
    assert regressed == sorted(regressed)


async def test_no_regression_when_scores_hold(
    seeded_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _create_golden_tasks(seeded_session)
    monkeypatch.setattr(scoring, "task_score", lambda *args, **kwargs: 0.7)
    first = await run_eval(seeded_session, m.EvalMode.baseline)
    second = await run_eval(seeded_session, m.EvalMode.baseline)
    assert first.summary["avg_score"] == second.summary["avg_score"]
    assert second.summary["regression"] is False
    assert second.summary["regressed_task_names"] == []


# ---------------------------------------------------------------------------
# failure handling
# ---------------------------------------------------------------------------


async def test_run_eval_marks_failed_on_error(
    seeded_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _create_golden_tasks(seeded_session)

    async def boom(*args: object, **kwargs: object) -> object:
        raise RuntimeError("synthetic retrieval failure")

    monkeypatch.setattr("context_engine.evals.harness.baseline_retrieve", boom)
    run = await run_eval(seeded_session, m.EvalMode.baseline)
    assert run.status == m.EvalRunStatus.failed
    assert "synthetic retrieval failure" in run.summary["error"]
    assert run.finished_at is not None
    assert await _results_for(seeded_session, run) == []  # no partial results persisted


# ---------------------------------------------------------------------------
# actor
# ---------------------------------------------------------------------------


@asynccontextmanager
async def _fake_session_scope(session: AsyncSession) -> AsyncIterator[AsyncSession]:
    yield session


async def test_actor_is_registered_and_enqueues(seeded_session: AsyncSession) -> None:
    from context_engine.observability.worker import get_broker

    broker = get_broker()
    assert "run_eval_actor" in broker.get_declared_actors()

    message = actors.run_eval_actor.send(str(uuid.uuid4()), "baseline")
    assert message.actor_name == "run_eval_actor"
    broker.flush_all()  # drop the stub message; execution is tested below


async def test_actor_executes_pre_created_run(
    seeded_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _create_golden_tasks(seeded_session)
    run = m.EvalRun(mode=m.EvalMode.baseline, status=m.EvalRunStatus.running, summary={})
    seeded_session.add(run)
    await seeded_session.flush()

    monkeypatch.setattr(actors, "session_scope", lambda: _fake_session_scope(seeded_session))
    await actors.execute_eval_run_by_id(str(run.id))

    assert run.status == m.EvalRunStatus.completed
    assert run.summary["avg_score"] >= 0.0
    assert len(await _results_for(seeded_session, run)) == await _active_task_count(seeded_session)


async def test_actor_ignores_unknown_run(
    seeded_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(actors, "session_scope", lambda: _fake_session_scope(seeded_session))
    await actors.execute_eval_run_by_id(str(uuid.uuid4()))  # must not raise


def test_run_eval_actor_sync_wrapper(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    async def fake_execute(eval_run_id: str) -> None:
        calls.append(eval_run_id)

    monkeypatch.setattr(actors, "execute_eval_run_by_id", fake_execute)
    actors.run_eval_actor("abc-123", "baseline")
    assert calls == ["abc-123"]


def test_run_eval_actor_marks_failed_on_crash(monkeypatch: pytest.MonkeyPatch) -> None:
    async def boom(eval_run_id: str) -> None:
        raise RuntimeError("worker exploded")

    marked: dict[str, str] = {}

    async def fake_mark_failed(eval_run_id: str, error: str) -> None:
        marked[eval_run_id] = error

    monkeypatch.setattr(actors, "execute_eval_run_by_id", boom)
    monkeypatch.setattr(actors, "_mark_failed", fake_mark_failed)
    actors.run_eval_actor("abc-123", "baseline")  # must not raise
    assert "worker exploded" in marked["abc-123"]


async def test_execute_eval_run_directly_on_running_row(seeded_session: AsyncSession) -> None:
    """execute_eval_run (used by both run_eval and the actor) drives the transition."""
    await _create_golden_tasks(seeded_session)
    run = m.EvalRun(mode=m.EvalMode.baseline, status=m.EvalRunStatus.running, summary={})
    seeded_session.add(run)
    await seeded_session.flush()

    returned = await execute_eval_run(seeded_session, run)
    assert returned is run
    assert run.status == m.EvalRunStatus.completed
    assert run.summary["pass_rate"] >= 0.0

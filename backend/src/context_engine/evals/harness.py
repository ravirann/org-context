"""Eval harness: runs golden tasks through the baseline and the context engine.

Evals run as the seeded admin user (first active ``role=admin`` user): golden
task expectations are authored org-wide, so the run must not depend on any
one member's ACL grants. ACL filtering is still exercised end-to-end via
``acl_filter_clause`` (which short-circuits to TRUE for admins).
"""

from __future__ import annotations

import importlib
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from context_engine.config.constants import SETTINGS_EVAL_THRESHOLDS
from context_engine.evals import scoring
from context_engine.evals.baseline import baseline_retrieve, build_baseline_context
from context_engine.indexing.tokens import estimate_tokens
from context_engine.observability.logging import get_logger
from context_engine.storage.models import (
    Document,
    EvalMode,
    EvalResult,
    EvalResultMode,
    EvalRun,
    EvalRunStatus,
    EvalTask,
    User,
    UserRole,
)
from context_engine.storage.repositories import get_setting, write_audit

logger = get_logger(__name__)

DEFAULT_MIN_SCORE = 0.5
DEFAULT_REGRESSION_DELTA = 0.05


async def run_eval(
    session: AsyncSession, mode: EvalMode, triggered_by: uuid.UUID | None = None
) -> EvalRun:
    """Create a running EvalRun for ``mode`` and execute it synchronously."""
    eval_run = EvalRun(
        mode=EvalMode(mode),
        status=EvalRunStatus.running,
        triggered_by=triggered_by,
        started_at=datetime.now(UTC),
        summary={},
    )
    session.add(eval_run)
    await session.flush()
    return await execute_eval_run(session, eval_run)


async def execute_eval_run(session: AsyncSession, eval_run: EvalRun) -> EvalRun:
    """Execute a pre-created EvalRun: score every active golden task.

    Marks the run completed with a populated summary, or failed with the
    error message in ``summary.error`` — this function does not raise.
    """
    try:
        results, summary = await _execute(session, eval_run)
        session.add_all(results)
        eval_run.summary = summary
        eval_run.status = EvalRunStatus.completed
        await write_audit(
            session,
            eval_run.triggered_by,
            "eval.run",
            "eval_run",
            str(eval_run.id),
            {"mode": eval_run.mode.value, "results": len(results), "status": "completed"},
        )
    except Exception as exc:
        logger.error("eval_run_failed", eval_run_id=str(eval_run.id), error=str(exc))
        eval_run.status = EvalRunStatus.failed
        eval_run.summary = {"error": str(exc)}
    eval_run.finished_at = datetime.now(UTC)
    await session.flush()
    return eval_run


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


async def _execute(
    session: AsyncSession, eval_run: EvalRun
) -> tuple[list[EvalResult], dict[str, Any]]:
    mode = EvalMode(eval_run.mode)
    thresholds = await get_setting(session, SETTINGS_EVAL_THRESHOLDS, default={}) or {}
    min_score = float(thresholds.get("min_score", DEFAULT_MIN_SCORE))
    regression_delta = float(thresholds.get("regression_delta", DEFAULT_REGRESSION_DELTA))

    user = await _resolve_eval_user(session)
    tasks = list(
        (
            await session.execute(
                select(EvalTask).where(EvalTask.is_active.is_(True)).order_by(EvalTask.name)
            )
        )
        .scalars()
        .all()
    )
    titles = await _expected_titles(session, tasks)

    run_baseline = mode in (EvalMode.baseline, EvalMode.comparison)
    run_engine = mode in (EvalMode.context_engine, EvalMode.comparison)
    baseline_leg: list[EvalResult] = []
    engine_leg: list[EvalResult] = []
    results: list[EvalResult] = []

    for task in tasks:
        if run_baseline:
            result = await _run_baseline_leg(session, eval_run, user, task, min_score, titles)
            baseline_leg.append(result)
            results.append(result)
        if run_engine:
            result = await _run_engine_leg(session, eval_run, user, task, min_score, titles)
            engine_leg.append(result)
            results.append(result)

    primary_leg = engine_leg if run_engine else baseline_leg
    primary_mode = EvalResultMode.context_engine if run_engine else EvalResultMode.baseline
    primary_scores = {
        task.id: result.score for task, result in zip(tasks, primary_leg, strict=True)
    }

    avg_score, pass_rate, total_tokens = _leg_stats(primary_leg)
    summary: dict[str, Any] = {
        "avg_score": avg_score,
        "pass_rate": pass_rate,
        "total_tokens": total_tokens,
    }
    if mode == EvalMode.comparison:
        baseline_avg, _, baseline_tokens = _leg_stats(baseline_leg)
        summary["baseline_avg_score"] = baseline_avg
        summary["baseline_total_tokens"] = baseline_tokens

    regression = False
    regressed_task_names: list[str] = []
    previous = await _previous_completed_run(session, eval_run)
    if previous is not None:
        previous_avg = (
            previous.summary.get("avg_score") if isinstance(previous.summary, dict) else None
        )
        regression = scoring.is_regression(avg_score, previous_avg, regression_delta)
        previous_scores = await _previous_task_scores(session, previous.id, primary_mode)
        regressed_task_names = sorted(
            task.name
            for task in tasks
            if task.id in previous_scores and primary_scores[task.id] < previous_scores[task.id]
        )
    summary["regression"] = regression
    summary["regressed_task_names"] = regressed_task_names
    return results, summary


async def _run_baseline_leg(
    session: AsyncSession,
    eval_run: EvalRun,
    user: User,
    task: EvalTask,
    min_score: float,
    titles: dict[str, str],
) -> EvalResult:
    hits = await baseline_retrieve(session, user, task.task)
    context_text = build_baseline_context(hits)
    got_ids = list(dict.fromkeys(hit.document_id for hit in hits))
    tokens = estimate_tokens(context_text)
    # The naive baseline emits no citations, so its citation check always fails.
    return _score_leg(
        eval_run=eval_run,
        task=task,
        mode=EvalResultMode.baseline,
        got_ids=got_ids,
        context_text=context_text,
        citations_flag=False,
        tokens=tokens,
        min_score=min_score,
        titles=titles,
    )


async def _run_engine_leg(
    session: AsyncSession,
    eval_run: EvalRun,
    user: User,
    task: EvalTask,
    min_score: float,
    titles: dict[str, str],
) -> EvalResult:
    # Imported lazily: the context_compiler module is being built concurrently.
    try:
        compiler = importlib.import_module("context_engine.context_compiler.compiler")
    except ImportError as exc:
        raise RuntimeError(
            "context_engine.context_compiler.compiler is not available yet; the "
            "context_engine leg of the eval harness needs compile_context "
            "(module is being built concurrently — retry once it lands)."
        ) from exc

    packet = await compiler.compile_context(
        session, user, task.task, repo=task.repo, service=task.service
    )
    got_ids = list(
        dict.fromkeys(
            str(source["document_id"])
            for source in packet.selected_sources
            if source.get("document_id")
        )
    )
    context_text = packet.compiled_context or ""
    citations_flag = scoring.citations_ok(packet.citations, got_ids)
    tokens = int(packet.token_estimate or estimate_tokens(context_text))
    return _score_leg(
        eval_run=eval_run,
        task=task,
        mode=EvalResultMode.context_engine,
        got_ids=got_ids,
        context_text=context_text,
        citations_flag=citations_flag,
        tokens=tokens,
        min_score=min_score,
        titles=titles,
    )


def _score_leg(
    *,
    eval_run: EvalRun,
    task: EvalTask,
    mode: EvalResultMode,
    got_ids: list[str],
    context_text: str,
    citations_flag: bool,
    tokens: int,
    min_score: float,
    titles: dict[str, str],
) -> EvalResult:
    expected_ids = [str(doc_id) for doc_id in task.expected_document_ids]
    retrieval = scoring.retrieval_scores(expected_ids, got_ids)
    keyword = scoring.keyword_score(context_text, task.expected_keywords)
    absent_keywords = scoring.missing_keywords(context_text, task.expected_keywords)
    efficiency = scoring.token_efficiency(tokens)
    score = scoring.task_score(retrieval["f1"], keyword, citations_flag, efficiency)
    missed_ids = [doc_id for doc_id in expected_ids if doc_id not in set(got_ids)]
    explanation = _build_explanation(mode.value, missed_ids, absent_keywords, titles)
    return EvalResult(
        eval_run_id=eval_run.id,
        eval_task_id=task.id,
        mode=mode,
        score=round(score, 4),
        passed=score >= min_score,
        explanation=explanation,
        tokens_used=tokens,
        details={
            "precision": round(retrieval["precision"], 4),
            "recall": round(retrieval["recall"], 4),
            "f1": round(retrieval["f1"], 4),
            "keyword_hits": len(task.expected_keywords) - len(absent_keywords),
            "citations_ok": citations_flag,
            "token_efficiency": round(efficiency, 4),
        },
    )


def _build_explanation(
    label: str, missed_ids: list[str], absent_keywords: list[str], titles: dict[str, str]
) -> str:
    parts: list[str] = []
    if missed_ids:
        missed = ", ".join(titles.get(doc_id, doc_id) for doc_id in missed_ids)
        parts.append(f"missed expected documents: {missed}")
    else:
        parts.append("all expected documents retrieved")
    if absent_keywords:
        parts.append(f"missing keywords: {', '.join(absent_keywords)}")
    else:
        parts.append("all expected keywords present")
    return f"{label}: " + "; ".join(parts)


def _leg_stats(results: list[EvalResult]) -> tuple[float, float, int]:
    """(avg_score, pass_rate, total_tokens) for one leg; zeros when empty."""
    if not results:
        return 0.0, 0.0, 0
    avg = sum(result.score for result in results) / len(results)
    pass_rate = sum(1 for result in results if result.passed) / len(results)
    total_tokens = sum(result.tokens_used for result in results)
    return round(avg, 4), round(pass_rate, 4), total_tokens


async def _resolve_eval_user(session: AsyncSession) -> User:
    """Resolve the seeded admin user evals run as (see module docstring)."""
    stmt = (
        select(User)
        .where(User.role == UserRole.admin, User.is_active.is_(True))
        .order_by(User.created_at, User.email)
        .limit(1)
    )
    user = (await session.execute(stmt)).scalar_one_or_none()
    if user is None:
        raise RuntimeError("No active admin user found; seed the database before running evals.")
    return user


async def _expected_titles(session: AsyncSession, tasks: list[EvalTask]) -> dict[str, str]:
    """Map expected document id -> title, for human-readable explanations."""
    ids: set[uuid.UUID] = set()
    for task in tasks:
        for raw in task.expected_document_ids:
            try:
                ids.add(uuid.UUID(str(raw)))
            except ValueError:
                continue
    if not ids:
        return {}
    rows = await session.execute(select(Document.id, Document.title).where(Document.id.in_(ids)))
    return {str(row.id): row.title for row in rows}


async def _previous_completed_run(session: AsyncSession, eval_run: EvalRun) -> EvalRun | None:
    stmt = (
        select(EvalRun)
        .where(
            EvalRun.mode == eval_run.mode,
            EvalRun.status == EvalRunStatus.completed,
            EvalRun.id != eval_run.id,
        )
        .order_by(EvalRun.started_at.desc())
        .limit(1)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def _previous_task_scores(
    session: AsyncSession, eval_run_id: uuid.UUID, mode: EvalResultMode
) -> dict[uuid.UUID, float]:
    stmt = select(EvalResult).where(EvalResult.eval_run_id == eval_run_id, EvalResult.mode == mode)
    rows = (await session.execute(stmt)).scalars().all()
    return {result.eval_task_id: result.score for result in rows}

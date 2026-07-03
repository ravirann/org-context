"""Eval endpoints: list runs, run detail, enqueue a run, and list golden tasks."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from context_engine.api.deps import SessionDep, UserDep
from context_engine.api.routes._common import page_bounds
from context_engine.api.schemas import (
    EvalResultOut,
    EvalRunDetail,
    EvalRunEnqueued,
    EvalRunOut,
    EvalRunRequest,
    GoldenTask,
    Items,
    Page,
)
from context_engine.evals.actors import run_eval_actor
from context_engine.storage.models import (
    EvalMode,
    EvalResult,
    EvalRun,
    EvalRunStatus,
    EvalTask,
)

router = APIRouter(tags=["evals"])


def _run_out(run: EvalRun) -> EvalRunOut:
    return EvalRunOut(
        id=str(run.id),
        mode=run.mode.value,
        status=run.status.value,
        started_at=run.started_at,
        finished_at=run.finished_at,
        summary=run.summary or None,
    )


@router.get("/evals", response_model=Page[EvalRunOut])
async def list_eval_runs(
    session: SessionDep,
    user: UserDep,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> Page[EvalRunOut]:
    total = (await session.execute(select(func.count()).select_from(EvalRun))).scalar_one()
    offset, limit = page_bounds(page, page_size)
    rows = (
        (
            await session.execute(
                select(EvalRun)
                .order_by(EvalRun.started_at.desc(), EvalRun.id)
                .offset(offset)
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    return Page(items=[_run_out(r) for r in rows], total=int(total), page=page, page_size=page_size)


@router.get("/evals/golden-tasks", response_model=Items[GoldenTask])
async def list_golden_tasks(session: SessionDep, user: UserDep) -> Items[GoldenTask]:
    rows = (await session.execute(select(EvalTask).order_by(EvalTask.name))).scalars().all()
    items = [
        GoldenTask(
            id=str(t.id),
            name=t.name,
            task=t.task,
            repo=t.repo,
            service=t.service,
            is_active=t.is_active,
            expected_keywords=list(t.expected_keywords or []),
        )
        for t in rows
    ]
    return Items(items=items)


@router.get("/evals/{run_id}", response_model=EvalRunDetail)
async def get_eval_run(run_id: uuid.UUID, session: SessionDep, user: UserDep) -> EvalRunDetail:
    run = await session.get(EvalRun, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    results = (
        (
            await session.execute(
                select(EvalResult)
                .where(EvalResult.eval_run_id == run_id)
                .options(selectinload(EvalResult.eval_task))
                .order_by(EvalResult.mode, EvalResult.id)
            )
        )
        .scalars()
        .all()
    )
    result_out = [
        EvalResultOut(
            task_name=r.eval_task.name if r.eval_task else "",
            mode=r.mode.value,
            score=r.score,
            passed=r.passed,
            explanation=r.explanation,
            tokens_used=r.tokens_used,
            details=r.details or {},
        )
        for r in results
    ]
    golden_total = (
        await session.execute(
            select(func.count()).select_from(EvalTask).where(EvalTask.is_active.is_(True))
        )
    ).scalar_one()

    base = _run_out(run)
    return EvalRunDetail(
        **base.model_dump(), results=result_out, golden_tasks_total=int(golden_total)
    )


@router.post("/evals/run", response_model=EvalRunEnqueued, status_code=status.HTTP_202_ACCEPTED)
async def run_eval(body: EvalRunRequest, session: SessionDep, user: UserDep) -> EvalRunEnqueued:
    run = EvalRun(
        mode=EvalMode(body.mode),
        status=EvalRunStatus.running,
        triggered_by=user.id,
        started_at=datetime.now(UTC),
        summary={},
    )
    session.add(run)
    await session.flush()
    run_eval_actor.send(str(run.id), body.mode)
    return EvalRunEnqueued(eval_run_id=str(run.id), status=run.status.value)

"""Dashboard endpoints: summary counts and time-series trends."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Query
from sqlalchemy import distinct, func, select

from context_engine.api.deps import SessionDep, UserDep
from context_engine.api.schemas import DashboardSummary, TrendPoint, Trends
from context_engine.storage.models import (
    AgentRun,
    AgentRunStatus,
    AuditLog,
    Conflict,
    ConflictStatus,
    ContextPacket,
    DocStatus,
    Document,
    EvalRun,
    EvalRunStatus,
    Source,
    User,
)

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard/summary", response_model=DashboardSummary)
async def summary(session: SessionDep, user: UserDep) -> DashboardSummary:
    total_documents = (
        await session.execute(select(func.count()).select_from(Document))
    ).scalar_one()
    connected_sources = (
        await session.execute(select(func.count()).select_from(Source))
    ).scalar_one()
    active_repos = (
        await session.execute(
            select(func.count(distinct(Document.repo))).where(Document.repo.is_not(None))
        )
    ).scalar_one()
    active_services = (
        await session.execute(
            select(func.count(distinct(Document.service))).where(Document.service.is_not(None))
        )
    ).scalar_one()
    active_users = (
        await session.execute(
            select(func.count()).select_from(User).where(User.is_active.is_(True))
        )
    ).scalar_one()
    context_packets = (
        await session.execute(select(func.count()).select_from(ContextPacket))
    ).scalar_one()
    agent_runs = (await session.execute(select(func.count()).select_from(AgentRun))).scalar_one()
    failed_agent_runs = (
        await session.execute(
            select(func.count())
            .select_from(AgentRun)
            .where(AgentRun.status == AgentRunStatus.failed)
        )
    ).scalar_one()
    stale_documents = (
        await session.execute(
            select(func.count()).select_from(Document).where(Document.status == DocStatus.stale)
        )
    ).scalar_one()

    # Distinct documents participating in open conflicts.
    open_conflicts = (
        (
            await session.execute(
                select(Conflict.document_ids).where(Conflict.status == ConflictStatus.open)
            )
        )
        .scalars()
        .all()
    )
    conflicting_docs: set[str] = set()
    for doc_ids in open_conflicts:
        conflicting_docs.update(doc_ids or [])

    acl_violations_blocked = (
        await session.execute(
            select(func.count()).select_from(AuditLog).where(AuditLog.action == "acl.blocked")
        )
    ).scalar_one()

    latest_run = (
        await session.execute(
            select(EvalRun)
            .where(EvalRun.status == EvalRunStatus.completed)
            .order_by(EvalRun.finished_at.desc(), EvalRun.started_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    latest_eval_score: float | None = None
    if latest_run is not None and isinstance(latest_run.summary, dict):
        raw = latest_run.summary.get("avg_score")
        if isinstance(raw, int | float):
            latest_eval_score = float(raw)

    return DashboardSummary(
        total_documents=int(total_documents),
        connected_sources=int(connected_sources),
        active_repos=int(active_repos),
        active_services=int(active_services),
        active_users=int(active_users),
        context_packets=int(context_packets),
        agent_runs=int(agent_runs),
        failed_agent_runs=int(failed_agent_runs),
        stale_documents=int(stale_documents),
        conflicting_documents=len(conflicting_docs),
        acl_violations_blocked=int(acl_violations_blocked),
        latest_eval_score=latest_eval_score,
    )


def _fill_series(values: dict[date, float], start: date, end: date) -> list[TrendPoint]:
    """Dense daily series from start..end inclusive; missing days carry 0."""
    points: list[TrendPoint] = []
    current = start
    while current <= end:
        points.append(TrendPoint(date=current.isoformat(), value=values.get(current, 0.0)))
        current += timedelta(days=1)
    return points


@router.get("/dashboard/trends", response_model=Trends)
async def trends(session: SessionDep, user: UserDep, days: int = Query(30, ge=1, le=365)) -> Trends:
    today = datetime.now(UTC).date()
    start = today - timedelta(days=days - 1)

    # Eval scores: avg completed-run avg_score per finished day.
    eval_rows = (
        await session.execute(
            select(EvalRun.finished_at, EvalRun.summary).where(
                EvalRun.status == EvalRunStatus.completed,
                EvalRun.finished_at.is_not(None),
            )
        )
    ).all()
    eval_by_day: dict[date, list[float]] = defaultdict(list)
    for finished_at, summary_json in eval_rows:
        if finished_at is None:
            continue
        d = finished_at.date()
        if d < start or d > today:
            continue
        if isinstance(summary_json, dict):
            val = summary_json.get("avg_score")
            if isinstance(val, int | float):
                eval_by_day[d].append(float(val))
    eval_scores = _fill_series({d: sum(v) / len(v) for d, v in eval_by_day.items()}, start, today)

    # Source freshness: avg document freshness_score per last_activity day.
    fresh_rows = (
        await session.execute(select(Document.last_activity_at, Document.freshness_score))
    ).all()
    fresh_by_day: dict[date, list[float]] = defaultdict(list)
    for last_activity_at, freshness in fresh_rows:
        if last_activity_at is None:
            continue
        d = last_activity_at.date()
        if d < start or d > today:
            continue
        fresh_by_day[d].append(float(freshness))
    source_freshness = _fill_series(
        {d: sum(v) / len(v) for d, v in fresh_by_day.items()}, start, today
    )

    # Review rework: failed / total agent runs per started day.
    run_rows = (await session.execute(select(AgentRun.started_at, AgentRun.status))).all()
    run_total: dict[date, int] = defaultdict(int)
    run_failed: dict[date, int] = defaultdict(int)
    for started_at, run_status in run_rows:
        if started_at is None:
            continue
        d = started_at.date()
        if d < start or d > today:
            continue
        run_total[d] += 1
        if run_status == AgentRunStatus.failed:
            run_failed[d] += 1
    rework = {d: (run_failed[d] / run_total[d]) if run_total[d] else 0.0 for d in run_total}
    review_rework = _fill_series(rework, start, today)

    # Packets per day: count by created_at day.
    packet_rows = (await session.execute(select(ContextPacket.created_at))).scalars().all()
    packet_by_day: dict[date, float] = defaultdict(float)
    for created_at in packet_rows:
        if created_at is None:
            continue
        d = created_at.date()
        if d < start or d > today:
            continue
        packet_by_day[d] += 1
    packets_per_day = _fill_series(dict(packet_by_day), start, today)

    return Trends(
        eval_scores=eval_scores,
        source_freshness=source_freshness,
        review_rework=review_rework,
        packets_per_day=packets_per_day,
    )

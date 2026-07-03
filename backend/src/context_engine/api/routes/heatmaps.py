"""Heatmap endpoints: user activity, ownership, and context-debt aggregates."""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Query
from sqlalchemy import select

from context_engine.api.deps import SessionDep, UserDep
from context_engine.api.routes._common import team_name_map, user_name_map
from context_engine.api.schemas import (
    ContextDebtHeatmapResponse,
    ContextDebtRow,
    HeatmapCell,
    HeatmapRow,
    HeatmapUsersResponse,
    OwnershipResponse,
    OwnershipRow,
)
from context_engine.storage.models import (
    ActivityEvent,
    AgentRun,
    AgentRunStatus,
    Conflict,
    ConflictStatus,
    DocStatus,
    Document,
    User,
)

router = APIRouter(tags=["heatmaps"])

USER_ROW_CAP = 50


@router.get("/heatmaps/users", response_model=HeatmapUsersResponse)
async def users_heatmap(
    session: SessionDep,
    user: UserDep,
    from_: str | None = Query(None, alias="from"),
    to: str | None = None,
    team_id: uuid.UUID | None = None,
    repo: str | None = None,
    service: str | None = None,
    metric: str = "all",
) -> HeatmapUsersResponse:
    today = datetime.now(UTC).date()
    end = date.fromisoformat(to) if to else today
    start = date.fromisoformat(from_) if from_ else end - timedelta(days=29)

    clauses = [ActivityEvent.day >= start, ActivityEvent.day <= end]
    if team_id:
        clauses.append(ActivityEvent.team_id == team_id)
    if repo:
        clauses.append(ActivityEvent.repo == repo)
    if service:
        clauses.append(ActivityEvent.service == service)
    if metric and metric != "all":
        clauses.append(ActivityEvent.event_type == metric)

    rows = (await session.execute(select(ActivityEvent).where(*clauses))).scalars().all()

    # user -> {day -> summed count}
    per_user: dict[uuid.UUID, dict[date, int]] = defaultdict(lambda: defaultdict(int))
    for ev in rows:
        per_user[ev.user_id][ev.day] += ev.count

    days: list[date] = []
    current = start
    while current <= end:
        days.append(current)
        current += timedelta(days=1)
    day_strs = [d.isoformat() for d in days]

    user_ids = set(per_user)
    users = (
        (
            await session.execute(
                select(User)
                .where(User.id.in_(user_ids))
                .options()  # team loaded lazily below via map
            )
        )
        .scalars()
        .all()
        if user_ids
        else []
    )
    team_ids = {u.team_id for u in users if u.team_id}
    team_names = await team_name_map(session, team_ids)
    user_map = {u.id: u for u in users}

    heat_rows: list[HeatmapRow] = []
    for uid, by_day in per_user.items():
        u = user_map.get(uid)
        if u is None:
            continue
        cells = [HeatmapCell(day=d.isoformat(), value=by_day.get(d, 0)) for d in days]
        total = sum(by_day.values())
        heat_rows.append(
            HeatmapRow(
                user_id=str(uid),
                user_name=u.name,
                team_name=team_names.get(u.team_id) if u.team_id else None,
                cells=cells,
                total=total,
            )
        )
    heat_rows.sort(key=lambda r: r.total, reverse=True)
    return HeatmapUsersResponse(rows=heat_rows[:USER_ROW_CAP], days=day_strs)


@router.get("/heatmaps/ownership", response_model=OwnershipResponse)
async def ownership_heatmap(session: SessionDep, user: UserDep) -> OwnershipResponse:
    docs = (
        await session.execute(
            select(
                Document.id,
                Document.repo,
                Document.service,
                Document.team_id,
                Document.author_id,
                Document.last_activity_at,
            )
        )
    ).all()

    # key -> aggregation buckets
    doc_count: dict[str, int] = defaultdict(int)
    with_owner: dict[str, int] = defaultdict(int)
    team_votes: dict[str, dict[uuid.UUID, int]] = defaultdict(lambda: defaultdict(int))
    author_votes: dict[str, dict[uuid.UUID, int]] = defaultdict(lambda: defaultdict(int))
    last_activity: dict[str, datetime] = {}

    for row in docs:
        for key in (row.repo, row.service):
            if not key:
                continue
            doc_count[key] += 1
            if row.team_id is not None:
                with_owner[key] += 1
                team_votes[key][row.team_id] += 1
            if row.author_id is not None:
                author_votes[key][row.author_id] += 1
            if row.last_activity_at is not None and (
                key not in last_activity or row.last_activity_at > last_activity[key]
            ):
                last_activity[key] = row.last_activity_at

    team_ids = {tid for votes in team_votes.values() for tid in votes}
    author_ids = {aid for votes in author_votes.values() for aid in votes}
    team_names = await team_name_map(session, team_ids)
    author_names = await user_name_map(session, author_ids)

    rows: list[OwnershipRow] = []
    for key in sorted(doc_count):
        owner_team = None
        if team_votes[key]:
            top_team = max(team_votes[key], key=lambda t: team_votes[key][t])
            owner_team = team_names.get(top_team)
        top_authors = sorted(author_votes[key], key=lambda a: author_votes[key][a], reverse=True)[
            :3
        ]
        owner_user_names = [author_names[a] for a in top_authors if a in author_names]
        coverage = with_owner[key] / doc_count[key] if doc_count[key] else 0.0
        rows.append(
            OwnershipRow(
                key=key,
                owner_team=owner_team,
                doc_count=doc_count[key],
                owner_user_names=owner_user_names,
                coverage_score=round(coverage, 4),
                last_activity_at=last_activity.get(key),
            )
        )
    return OwnershipResponse(rows=rows)


@router.get("/heatmaps/context-debt", response_model=ContextDebtHeatmapResponse)
async def context_debt_heatmap(session: SessionDep, user: UserDep) -> ContextDebtHeatmapResponse:
    """Per repo/service context-debt rows.

    debt_score is a normalized 0-1 weighted blend of the debt signals:
        0.30 * (stale_count / doc_count)
        0.20 * missing_owner (1 or 0)
        0.20 * min(conflict_count / 3, 1)
        0.15 * min(rejected_count / 20, 1)
        0.15 * (failed_runs / max(1, run_total))
    """
    docs = (
        await session.execute(
            select(
                Document.repo,
                Document.service,
                Document.team_id,
                Document.status,
                Document.id,
                Document.rejection_count,
            )
        )
    ).all()

    keys: set[str] = set()
    doc_count: dict[str, int] = defaultdict(int)
    stale_count: dict[str, int] = defaultdict(int)
    rejected_count: dict[str, int] = defaultdict(int)
    team_votes: dict[str, dict[uuid.UUID, int]] = defaultdict(lambda: defaultdict(int))
    has_owner: dict[str, bool] = defaultdict(bool)
    key_repo: dict[str, str | None] = {}
    key_service: dict[str, str | None] = {}
    doc_id_to_keys: dict[str, set[str]] = defaultdict(set)

    for row in docs:
        for key, is_repo in ((row.repo, True), (row.service, False)):
            if not key:
                continue
            keys.add(key)
            doc_count[key] += 1
            rejected_count[key] += row.rejection_count or 0
            if row.status == DocStatus.stale:
                stale_count[key] += 1
            if row.team_id is not None:
                has_owner[key] = True
                team_votes[key][row.team_id] += 1
            key_repo.setdefault(key, row.repo if is_repo else key_repo.get(key))
            key_service.setdefault(key, row.service if not is_repo else key_service.get(key))
            doc_id_to_keys[str(row.id)].add(key)

    # Open conflicts affecting each key (via document ids).
    conflict_count: dict[str, int] = defaultdict(int)
    conflicts = (
        (
            await session.execute(
                select(Conflict.document_ids).where(Conflict.status == ConflictStatus.open)
            )
        )
        .scalars()
        .all()
    )
    for doc_ids in conflicts:
        affected_keys: set[str] = set()
        for did in doc_ids or []:
            affected_keys.update(doc_id_to_keys.get(did, set()))
        for key in affected_keys:
            conflict_count[key] += 1

    # Failed / total agent runs per key (repo or service).
    run_rows = (
        await session.execute(select(AgentRun.repo, AgentRun.service, AgentRun.status))
    ).all()
    failed_runs: dict[str, int] = defaultdict(int)
    run_total: dict[str, int] = defaultdict(int)
    for r_repo, r_service, r_status in run_rows:
        for key in {k for k in (r_repo, r_service) if k}:
            run_total[key] += 1
            if r_status == AgentRunStatus.failed:
                failed_runs[key] += 1

    team_ids = {tid for votes in team_votes.values() for tid in votes}
    team_names = await team_name_map(session, team_ids)

    rows: list[ContextDebtRow] = []
    for key in sorted(keys):
        count = doc_count[key] or 1
        owner_team = None
        if team_votes[key]:
            top = max(team_votes[key], key=lambda t: team_votes[key][t])
            owner_team = team_names.get(top)
        missing_owner = not has_owner[key]
        debt = (
            0.30 * (stale_count[key] / count)
            + 0.20 * (1.0 if missing_owner else 0.0)
            + 0.20 * min(conflict_count[key] / 3.0, 1.0)
            + 0.15 * min(rejected_count[key] / 20.0, 1.0)
            + 0.15 * (failed_runs[key] / run_total[key] if run_total[key] else 0.0)
        )
        rows.append(
            ContextDebtRow(
                key=key,
                repo=key_repo.get(key),
                service=key_service.get(key),
                team_name=owner_team,
                stale_count=stale_count[key],
                missing_owner=missing_owner,
                conflict_count=conflict_count[key],
                rejected_count=rejected_count[key],
                failed_runs=failed_runs[key],
                debt_score=round(min(debt, 1.0), 4),
            )
        )
    rows.sort(key=lambda r: r.debt_score, reverse=True)
    return ContextDebtHeatmapResponse(rows=rows)

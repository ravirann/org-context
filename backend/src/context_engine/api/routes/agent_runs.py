"""Agent run endpoints: list (filtered/paginated) and detail."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from context_engine.api.deps import SessionDep, UserDep
from context_engine.api.routes._common import page_bounds
from context_engine.api.routes.context import _packet_out
from context_engine.api.schemas import (
    AgentRunDetail,
    AgentRunSummary,
    Page,
    ReviewerComment,
)
from context_engine.observability.langfuse_client import trace_url
from context_engine.storage.models import AgentRun, ContextPacket

router = APIRouter(tags=["agent-runs"])


def _run_summary(run: AgentRun) -> AgentRunSummary:
    return AgentRunSummary(
        id=str(run.id),
        agent_name=run.agent_name,
        task=run.task,
        repo=run.repo,
        service=run.service,
        user_name=run.user.name if run.user else "",
        status=run.status.value,
        started_at=run.started_at,
        finished_at=run.finished_at,
        context_packet_id=str(run.context_packet_id) if run.context_packet_id else None,
    )


@router.get("/agent-runs", response_model=Page[AgentRunSummary])
async def list_agent_runs(
    session: SessionDep,
    user: UserDep,
    agent: str | None = None,
    repo: str | None = None,
    service: str | None = None,
    user_id: uuid.UUID | None = None,
    status_filter: str | None = Query(None, alias="status"),
    from_: str | None = Query(None, alias="from"),
    to: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> Page[AgentRunSummary]:
    clauses = []
    if agent:
        clauses.append(AgentRun.agent_name == agent)
    if repo:
        clauses.append(AgentRun.repo == repo)
    if service:
        clauses.append(AgentRun.service == service)
    if user_id:
        clauses.append(AgentRun.user_id == user_id)
    if status_filter:
        clauses.append(AgentRun.status == status_filter)
    if from_:
        clauses.append(AgentRun.started_at >= from_)
    if to:
        clauses.append(AgentRun.started_at <= to)

    total = (
        await session.execute(select(func.count()).select_from(AgentRun).where(*clauses))
    ).scalar_one()
    offset, limit = page_bounds(page, page_size)
    rows = (
        (
            await session.execute(
                select(AgentRun)
                .where(*clauses)
                .options(selectinload(AgentRun.user))
                .order_by(AgentRun.started_at.desc(), AgentRun.id)
                .offset(offset)
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    return Page(
        items=[_run_summary(r) for r in rows],
        total=int(total),
        page=page,
        page_size=page_size,
    )


@router.get("/agent-runs/{run_id}", response_model=AgentRunDetail)
async def get_agent_run(run_id: uuid.UUID, session: SessionDep, user: UserDep) -> AgentRunDetail:
    run = (
        await session.execute(
            select(AgentRun).where(AgentRun.id == run_id).options(selectinload(AgentRun.user))
        )
    ).scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    packet_out = None
    if run.context_packet_id is not None:
        packet = (
            await session.execute(
                select(ContextPacket)
                .where(ContextPacket.id == run.context_packet_id)
                .options(selectinload(ContextPacket.requester))
            )
        ).scalar_one_or_none()
        if packet is not None:
            packet_out = _packet_out(packet)

    summary = _run_summary(run)
    return AgentRunDetail(
        **summary.model_dump(),
        plan=run.plan,
        changed_files=list(run.changed_files or []),
        test_output=run.test_output,
        pr_url=run.pr_url,
        reviewer_comments=[
            ReviewerComment(author=c.get("author", ""), comment=c.get("comment", ""))
            for c in (run.reviewer_comments or [])
        ],
        langfuse_trace_url=trace_url(run.langfuse_trace_id),
        context_packet=packet_out,
    )

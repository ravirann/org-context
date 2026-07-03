"""Context packet endpoints: compile, list, and detail.

ACL note: context packets are derived artifacts. Any authenticated user may list and
read packets and their compiled contents; the ACL that matters was enforced at compile
time (document selection is ACL-filtered inside ``compile_context``). Individual document
content is only ever reachable through the ACL-gated documents endpoint.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from context_engine.api.deps import SessionDep, UserDep
from context_engine.api.routes._common import page_bounds
from context_engine.api.schemas import (
    AgentRunSummary,
    CompileRequest,
    ContextPacketDetail,
    ContextPacketOut,
    ContextPacketSummary,
    FeedbackOut,
    Page,
)
from context_engine.context_compiler.compiler import compile_context
from context_engine.storage.models import AgentRun, ContextPacket, Feedback

router = APIRouter(tags=["context"])


def _packet_out(packet: ContextPacket) -> ContextPacketOut:
    return ContextPacketOut(
        id=str(packet.id),
        task=packet.task,
        intent=packet.intent.value,
        repo=packet.repo,
        service=packet.service,
        compiled_context=packet.compiled_context,
        selected_sources=packet.selected_sources,  # type: ignore[arg-type]
        rejected_sources=packet.rejected_sources,  # type: ignore[arg-type]
        citations=packet.citations,  # type: ignore[arg-type]
        conflict_notes=packet.conflict_notes,  # type: ignore[arg-type]
        acl_notes=packet.acl_notes,  # type: ignore[arg-type]
        token_estimate=packet.token_estimate,
        confidence_score=packet.confidence_score,
        freshness_score=packet.freshness_score,
        authority_score=packet.authority_score,
        risks=packet.risks,
        recommended_tests=packet.recommended_tests,
        agent_outcome=packet.agent_outcome.value,
        feedback_score=packet.feedback_score,
        requested_by_name=packet.requester.name if packet.requester else "",
        created_at=packet.created_at,
    )


@router.post(
    "/context/compile", response_model=ContextPacketOut, status_code=status.HTTP_201_CREATED
)
async def compile_packet(
    body: CompileRequest, session: SessionDep, user: UserDep
) -> ContextPacketOut:
    packet = await compile_context(
        session, user, body.task, repo=body.repo, service=body.service, max_tokens=body.max_tokens
    )
    # Requester is the current user; avoid an extra load.
    packet.requester = user  # type: ignore[assignment]
    return _packet_out(packet)


@router.get("/context-packets", response_model=Page[ContextPacketSummary])
async def list_packets(
    session: SessionDep,
    user: UserDep,
    repo: str | None = None,
    service: str | None = None,
    intent: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> Page[ContextPacketSummary]:
    clauses = []
    if repo:
        clauses.append(ContextPacket.repo == repo)
    if service:
        clauses.append(ContextPacket.service == service)
    if intent:
        clauses.append(ContextPacket.intent == intent)

    total = (
        await session.execute(select(func.count()).select_from(ContextPacket).where(*clauses))
    ).scalar_one()

    offset, limit = page_bounds(page, page_size)
    rows = (
        (
            await session.execute(
                select(ContextPacket)
                .where(*clauses)
                .options(selectinload(ContextPacket.requester))
                .order_by(ContextPacket.created_at.desc(), ContextPacket.id)
                .offset(offset)
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    items = [
        ContextPacketSummary(
            id=str(p.id),
            task=p.task,
            intent=p.intent.value,
            repo=p.repo,
            service=p.service,
            token_estimate=p.token_estimate,
            confidence_score=p.confidence_score,
            agent_outcome=p.agent_outcome.value,
            requested_by_name=p.requester.name if p.requester else "",
            created_at=p.created_at,
            source_count=len(p.selected_sources or []),
        )
        for p in rows
    ]
    return Page(items=items, total=int(total), page=page, page_size=page_size)


@router.get("/context-packets/{packet_id}", response_model=ContextPacketDetail)
async def get_packet(
    packet_id: uuid.UUID, session: SessionDep, user: UserDep
) -> ContextPacketDetail:
    packet = (
        await session.execute(
            select(ContextPacket)
            .where(ContextPacket.id == packet_id)
            .options(selectinload(ContextPacket.requester))
        )
    ).scalar_one_or_none()
    if packet is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    feedback_rows = (
        (
            await session.execute(
                select(Feedback)
                .where(Feedback.context_packet_id == packet_id)
                .options(selectinload(Feedback.user))
                .order_by(Feedback.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    feedback = [
        FeedbackOut(
            id=str(f.id),
            type=f.type.value,
            context_packet_id=str(f.context_packet_id) if f.context_packet_id else None,
            document_id=str(f.document_id) if f.document_id else None,
            comment=f.comment,
            user_name=f.user.name if f.user else "",
            created_at=f.created_at,
        )
        for f in feedback_rows
    ]

    run = (
        await session.execute(
            select(AgentRun)
            .where(AgentRun.context_packet_id == packet_id)
            .options(selectinload(AgentRun.user))
            .order_by(AgentRun.started_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    agent_run = None
    if run is not None:
        agent_run = AgentRunSummary(
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

    base = _packet_out(packet)
    return ContextPacketDetail(**base.model_dump(), feedback=feedback, agent_run=agent_run)

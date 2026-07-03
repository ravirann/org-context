"""POST /v1/feedback — record feedback and apply documented side effects."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, status
from sqlalchemy import select

from context_engine.api.deps import SessionDep, UserDep
from context_engine.api.schemas import FeedbackCreate, FeedbackOut
from context_engine.storage.models import DocStatus, Document, Feedback, FeedbackType
from context_engine.storage.repositories import write_audit

router = APIRouter(tags=["feedback"])


@router.post("/feedback", response_model=FeedbackOut, status_code=status.HTTP_201_CREATED)
async def create_feedback(body: FeedbackCreate, session: SessionDep, user: UserDep) -> FeedbackOut:
    fb_type = FeedbackType(body.type)
    packet_id = uuid.UUID(body.context_packet_id) if body.context_packet_id else None
    document_id = uuid.UUID(body.document_id) if body.document_id else None

    row = Feedback(
        user_id=user.id,
        context_packet_id=packet_id,
        document_id=document_id,
        type=fb_type,
        comment=body.comment,
    )
    session.add(row)
    await session.flush()

    # Side effects on the target document (per API_CONTRACT).
    if document_id is not None:
        doc = (
            await session.execute(select(Document).where(Document.id == document_id))
        ).scalar_one_or_none()
        if doc is not None:
            action: str | None = None
            if fb_type == FeedbackType.promote_authoritative:
                doc.authority_score = 1.0
                action = "feedback.promote_authoritative"
            elif fb_type == FeedbackType.mark_deprecated:
                doc.status = DocStatus.deprecated
                action = "feedback.mark_deprecated"
            elif fb_type == FeedbackType.stale_context:
                doc.status = DocStatus.stale
                action = "feedback.stale_context"
            if action is not None:
                await write_audit(
                    session,
                    user.id,
                    action,
                    resource_type="document",
                    resource_id=str(document_id),
                    detail={"feedback_id": str(row.id)},
                )

    await write_audit(
        session,
        user.id,
        "feedback.create",
        resource_type="feedback",
        resource_id=str(row.id),
        detail={"type": fb_type.value},
    )
    await session.flush()

    return FeedbackOut(
        id=str(row.id),
        type=row.type.value,
        context_packet_id=str(row.context_packet_id) if row.context_packet_id else None,
        document_id=str(row.document_id) if row.document_id else None,
        comment=row.comment,
        user_name=user.name,
        created_at=row.created_at,
    )

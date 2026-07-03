"""Normalize connector RawItems into Document rows (upsert, no duplicates)."""

from __future__ import annotations

import math
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from context_engine.connectors.base import RawItem
from context_engine.storage.models import DocStatus, DocType, Document, Source, Team, User

STALE_FRESHNESS_THRESHOLD = 0.15
"""Documents whose freshness decays below this are marked stale."""


def compute_freshness(
    last_activity_at: datetime, window_days: int, now: datetime | None = None
) -> float:
    """exp(-age_days / window_days), clamped to [0, 1].

    Age is measured against ``now`` (defaults to the current UTC time); future
    timestamps and non-positive windows are handled defensively.
    """
    reference = now if now is not None else datetime.now(UTC)
    age_days = (reference - last_activity_at).total_seconds() / 86400.0
    if age_days <= 0:
        return 1.0
    window = max(1, window_days)
    return max(0.0, min(1.0, math.exp(-age_days / window)))


async def _user_id_by_email(session: AsyncSession, email: str) -> uuid.UUID | None:
    result = await session.execute(select(User.id).where(User.email == email))
    return result.scalar_one_or_none()


async def _team_id_by_name(session: AsyncSession, name: str) -> uuid.UUID | None:
    result = await session.execute(select(Team.id).where(Team.name == name))
    return result.scalar_one_or_none()


async def upsert_raw_item(session: AsyncSession, source: Source, item: RawItem) -> Document:
    """Upsert a Document for ``(source.id, item.external_id)`` and return it.

    Authors and teams are resolved by email/name against existing rows only —
    unknown references resolve to ``None`` (nothing is created). ACL names are
    mapped to ids the same way; unknown names are dropped from the ACL lists.
    """
    author_id = await _user_id_by_email(session, item.author_email) if item.author_email else None
    team_id = await _team_id_by_name(session, item.team_name) if item.team_name else None

    acl_team_ids: list[str] = []
    for name in item.acl.team_names:
        tid = await _team_id_by_name(session, name)
        if tid is not None:
            acl_team_ids.append(str(tid))
    acl_user_ids: list[str] = []
    for email in item.acl.user_emails:
        uid = await _user_id_by_email(session, email)
        if uid is not None:
            acl_user_ids.append(str(uid))

    authority_score = source.authority_rank / 100.0
    override = item.metadata.get("authority")
    if isinstance(override, int | float) and not isinstance(override, bool):
        authority_score = max(0.0, min(1.0, float(override)))

    freshness_score = compute_freshness(item.last_activity_at, source.freshness_window_days)
    if item.metadata.get("deprecated"):
        status = DocStatus.deprecated
    elif freshness_score < STALE_FRESHNESS_THRESHOLD:
        status = DocStatus.stale
    else:
        status = DocStatus.active

    existing = await session.execute(
        select(Document).where(
            Document.source_id == source.id, Document.external_id == item.external_id
        )
    )
    doc = existing.scalar_one_or_none()
    if doc is None:
        doc = Document(source_id=source.id, external_id=item.external_id)
        session.add(doc)
    else:
        # func.now() is transaction-scoped in Postgres; bump explicitly on re-sync.
        doc.updated_at = datetime.now(UTC)

    doc.doc_type = DocType(item.doc_type)
    doc.title = item.title
    doc.content = item.content
    doc.url = item.url
    doc.author_id = author_id
    doc.repo = item.repo
    doc.service = item.service
    doc.team_id = team_id
    doc.status = status
    doc.topic_key = item.topic_key
    doc.authority_score = authority_score
    doc.freshness_score = freshness_score
    doc.acl_public = item.acl.public
    doc.acl_team_ids = acl_team_ids
    doc.acl_user_ids = acl_user_ids
    doc.last_activity_at = item.last_activity_at
    doc.doc_metadata = dict(item.metadata)

    await session.flush()
    return doc

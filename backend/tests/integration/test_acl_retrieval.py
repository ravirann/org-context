"""Integration tests: ACL enforcement inside search_chunks + acl.blocked auditing."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from context_engine.indexing.embeddings import embed_text
from context_engine.indexing.tokens import estimate_tokens
from context_engine.retrieval.service import SearchFilters, search_chunks
from context_engine.storage.models import (
    AuditLog,
    Chunk,
    DocType,
    Document,
    Source,
    SourceType,
    User,
)

TEAM_RESTRICTED_TITLE = "Payments postmortem: INC-2107 duplicate charges"
USER_RESTRICTED_TITLE = "Secret infra credentials rotation plan"


async def get_user(session: AsyncSession, email: str) -> User:
    return (await session.execute(select(User).where(User.email == email))).scalar_one()


async def titles_for(session: AsyncSession, user: User, query: str) -> list[str]:
    page = await search_chunks(session, user, query, SearchFilters(page_size=50))
    return [hit.title for hit in page.items]


async def make_restricted_doc(
    session: AsyncSession, *, title: str, content: str, user_ids: list[str]
) -> Document:
    source = (
        await session.execute(select(Source).where(Source.type == SourceType.confluence))
    ).scalar_one()
    doc = Document(
        source_id=source.id,
        external_id=f"acl-test-{uuid.uuid4()}",
        doc_type=DocType.doc,
        title=title,
        content=content,
        url="https://demo.dev/acl-test",
        repo="payments-api",
        service="payments-api",
        authority_score=0.8,
        freshness_score=0.9,
        acl_public=False,
        acl_team_ids=[],
        acl_user_ids=user_ids,
        last_activity_at=datetime.now(UTC),
    )
    session.add(doc)
    await session.flush()
    session.add(
        Chunk(
            document_id=doc.id,
            ord=0,
            content=content,
            token_count=estimate_tokens(content),
            embedding=embed_text(content),
        )
    )
    await session.flush()
    return doc


async def test_team_restricted_doc_hidden_from_other_team(
    seeded_session: AsyncSession,
) -> None:
    engineer = await get_user(seeded_session, "jade@demo.dev")  # Growth team
    admin = await get_user(seeded_session, "admin@demo.dev")
    lead = await get_user(seeded_session, "priya@demo.dev")  # Payments team

    query = "postmortem duplicate charges"
    assert TEAM_RESTRICTED_TITLE not in await titles_for(seeded_session, engineer, query)
    assert TEAM_RESTRICTED_TITLE in await titles_for(seeded_session, admin, query)
    assert TEAM_RESTRICTED_TITLE in await titles_for(seeded_session, lead, query)


async def test_acl_blocked_count_is_exact(seeded_session: AsyncSession) -> None:
    engineer = await get_user(seeded_session, "jade@demo.dev")
    admin = await get_user(seeded_session, "admin@demo.dev")

    # Empty query matches every document: seed has 10 docs, 2 of which the
    # Growth engineer cannot read (Payments-team postmortem + admin-only secret).
    engineer_page = await search_chunks(seeded_session, engineer, "", SearchFilters())
    assert engineer_page.total == 8
    assert engineer_page.acl_blocked_count == 2

    admin_page = await search_chunks(seeded_session, admin, "", SearchFilters())
    assert admin_page.total == 10
    assert admin_page.acl_blocked_count == 0


async def test_user_restricted_doc_visible_only_to_grantee(
    seeded_session: AsyncSession,
) -> None:
    engineer = await get_user(seeded_session, "jade@demo.dev")
    lead = await get_user(seeded_session, "priya@demo.dev")
    admin = await get_user(seeded_session, "admin@demo.dev")

    # Seeded secret doc is granted to the admin user only.
    query = "credentials rotation plan"
    assert USER_RESTRICTED_TITLE in await titles_for(seeded_session, admin, query)
    assert USER_RESTRICTED_TITLE not in await titles_for(seeded_session, lead, query)
    assert USER_RESTRICTED_TITLE not in await titles_for(seeded_session, engineer, query)

    # A doc granted to the engineer is visible to them but not to the lead.
    doc = await make_restricted_doc(
        seeded_session,
        title="Growth-only experiment readout",
        content="Experiment readout xylophone metrics for the growth funnel.",
        user_ids=[str(engineer.id)],
    )
    assert doc.title in await titles_for(seeded_session, engineer, "xylophone metrics")
    assert doc.title not in await titles_for(seeded_session, lead, "xylophone metrics")


async def test_acl_blocked_writes_audit_row(seeded_session: AsyncSession) -> None:
    engineer = await get_user(seeded_session, "jade@demo.dev")
    before = (
        (await seeded_session.execute(select(AuditLog).where(AuditLog.action == "acl.blocked")))
        .scalars()
        .all()
    )
    assert before == []

    page = await search_chunks(seeded_session, engineer, "credentials rotation", SearchFilters())
    assert page.acl_blocked_count > 0

    rows = (
        (await seeded_session.execute(select(AuditLog).where(AuditLog.action == "acl.blocked")))
        .scalars()
        .all()
    )
    assert len(rows) == 1
    audit = rows[0]
    assert audit.actor_id == engineer.id
    assert audit.resource_type == "search"
    assert audit.detail["query"] == "credentials rotation"
    assert audit.detail["blocked"] == page.acl_blocked_count


async def test_admin_search_writes_no_acl_audit(seeded_session: AsyncSession) -> None:
    admin = await get_user(seeded_session, "admin@demo.dev")
    page = await search_chunks(seeded_session, admin, "credentials rotation", SearchFilters())
    assert page.acl_blocked_count == 0
    rows = (
        (await seeded_session.execute(select(AuditLog).where(AuditLog.action == "acl.blocked")))
        .scalars()
        .all()
    )
    assert rows == []

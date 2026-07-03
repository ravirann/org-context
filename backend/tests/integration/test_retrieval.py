"""Integration tests for hybrid retrieval (FTS + vector + weights + filters + paging)."""

from __future__ import annotations

import math
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from context_engine.indexing.embeddings import embed_text
from context_engine.indexing.tokens import estimate_tokens
from context_engine.retrieval.service import SearchFilters, search_chunks
from context_engine.storage.models import (
    Chunk,
    DocStatus,
    DocType,
    Document,
    Source,
    SourceType,
    User,
)
from context_engine.storage.repositories import set_setting

ADR_TITLE = "ADR-0042: Exponential backoff with jitter for payment retries"
LEGACY_TITLE = "Payments runbook: retry handling (legacy)"

FTS_ONLY = {"vector": 0.0, "fts": 1.0, "freshness": 0.0, "authority": 0.0}
AUTHORITY_ONLY = {"vector": 0.0, "fts": 0.0, "freshness": 0.0, "authority": 1.0}


async def get_user(session: AsyncSession, email: str) -> User:
    return (await session.execute(select(User).where(User.email == email))).scalar_one()


async def make_doc(
    session: AsyncSession,
    *,
    title: str,
    contents: list[str],
    repo: str = "payments-api",
    service: str = "payments-api",
    doc_type: str = "doc",
    status: str = "active",
    age_days: int = 5,
) -> Document:
    source = (
        await session.execute(select(Source).where(Source.type == SourceType.confluence))
    ).scalar_one()
    doc = Document(
        source_id=source.id,
        external_id=f"test-{uuid.uuid4()}",
        doc_type=DocType(doc_type),
        title=title,
        content="\n\n".join(contents),
        url=f"https://demo.dev/test/{uuid.uuid4()}",
        repo=repo,
        service=service,
        status=DocStatus(status),
        authority_score=source.authority_rank / 100.0,
        freshness_score=max(0.0, min(1.0, math.exp(-age_days / 90))),
        acl_public=True,
        acl_team_ids=[],
        acl_user_ids=[],
        last_activity_at=datetime.now(UTC) - timedelta(days=age_days),
    )
    session.add(doc)
    await session.flush()
    for i, piece in enumerate(contents):
        session.add(
            Chunk(
                document_id=doc.id,
                ord=i,
                content=piece,
                token_count=estimate_tokens(piece),
                embedding=embed_text(piece),
            )
        )
    await session.flush()
    return doc


async def test_fts_finds_exact_phrase_document(seeded_session: AsyncSession) -> None:
    admin = await get_user(seeded_session, "admin@demo.dev")
    page = await search_chunks(seeded_session, admin, "exponential backoff jitter", SearchFilters())
    assert page.total > 0
    assert ADR_TITLE in [hit.title for hit in page.items[:3]]

    # With FTS-only weights the exact-phrase document must rank first.
    await set_setting(seeded_session, "retrieval_weights", FTS_ONLY)
    page = await search_chunks(seeded_session, admin, "exponential backoff jitter", SearchFilters())
    assert page.items[0].title == ADR_TITLE
    assert page.items[0].score > page.items[1].score


async def test_vector_finds_identical_text(seeded_session: AsyncSession) -> None:
    admin = await get_user(seeded_session, "admin@demo.dev")
    # Exact chunk text of "Payments guide 1" -> deterministic embedding is identical,
    # so the vector leg pins it to the top.
    query = (
        "Guide 1: the POST /v1/payments/charge endpoint validates idempotency keys "
        "before writing to the payments table. Webhook retries must deduplicate on event_id. "
        "Cursor pagination is standard for list endpoints."
    )
    page = await search_chunks(seeded_session, admin, query, SearchFilters())
    assert page.items[0].title == "Payments guide 1: idempotency and webhooks"
    # Guides 2-6 share almost identical wording but hash embeddings differ entirely,
    # so only the exact-match document gets the full vector contribution.
    assert page.items[0].score > page.items[1].score


async def test_retrieval_weights_honored(seeded_session: AsyncSession) -> None:
    admin = await get_user(seeded_session, "admin@demo.dev")

    await set_setting(seeded_session, "retrieval_weights", FTS_ONLY)
    fts_page = await search_chunks(seeded_session, admin, "idempotency", SearchFilters())
    assert fts_page.items[0].title.startswith("Payments guide")

    await set_setting(seeded_session, "retrieval_weights", AUTHORITY_ONLY)
    auth_page = await search_chunks(seeded_session, admin, "idempotency", SearchFilters())
    assert auth_page.items[0].title == ADR_TITLE

    assert fts_page.items[0].document_id != auth_page.items[0].document_id


async def test_missing_weights_setting_uses_defaults(seeded_session: AsyncSession) -> None:
    admin = await get_user(seeded_session, "admin@demo.dev")
    await set_setting(seeded_session, "retrieval_weights", None)
    page = await search_chunks(seeded_session, admin, "payments", SearchFilters())
    assert page.total > 0
    assert all(hit.score >= 0 for hit in page.items)


async def test_doc_type_filter(seeded_session: AsyncSession) -> None:
    admin = await get_user(seeded_session, "admin@demo.dev")
    page = await search_chunks(seeded_session, admin, "retries", SearchFilters(doc_types=["adr"]))
    assert page.total == 1
    assert page.items[0].doc_type == "adr"
    assert page.items[0].title == ADR_TITLE


async def test_repo_filter(seeded_session: AsyncSession) -> None:
    admin = await get_user(seeded_session, "admin@demo.dev")
    other = await make_doc(
        seeded_session,
        title="Search service ranking notes",
        contents=["Ranking weights for the search service reranker."],
        repo="search-svc",
        service="search-svc",
    )
    page = await search_chunks(seeded_session, admin, "", SearchFilters(repo="search-svc"))
    assert page.total == 1
    assert page.items[0].document_id == str(other.id)

    page = await search_chunks(seeded_session, admin, "", SearchFilters(repo="payments-api"))
    assert str(other.id) not in [hit.document_id for hit in page.items]


async def test_status_filter(seeded_session: AsyncSession) -> None:
    admin = await get_user(seeded_session, "admin@demo.dev")
    page = await search_chunks(seeded_session, admin, "", SearchFilters(status="stale"))
    assert page.total == 1
    assert page.items[0].title == LEGACY_TITLE
    assert page.items[0].status == "stale"


async def test_source_ids_filter(seeded_session: AsyncSession) -> None:
    admin = await get_user(seeded_session, "admin@demo.dev")
    adr_source = await session_source(seeded_session, SourceType.adr)
    page = await search_chunks(
        seeded_session, admin, "", SearchFilters(source_ids=[str(adr_source.id)])
    )
    assert page.total == 1
    assert page.items[0].title == ADR_TITLE


async def session_source(session: AsyncSession, source_type: SourceType) -> Source:
    return (await session.execute(select(Source).where(Source.type == source_type))).scalar_one()


async def test_dedupe_one_hit_per_document(seeded_session: AsyncSession) -> None:
    admin = await get_user(seeded_session, "admin@demo.dev")
    doc = await make_doc(
        seeded_session,
        title="Long zebraquery guide",
        contents=[
            "zebraquery part one about payment retries.",
            "zebraquery part two about webhook dedupe.",
            "zebraquery part three about pagination.",
        ],
    )
    page = await search_chunks(seeded_session, admin, "zebraquery", SearchFilters())
    hits_for_doc = [hit for hit in page.items if hit.document_id == str(doc.id)]
    assert len(hits_for_doc) == 1
    assert page.total == len({hit.document_id for hit in page.items})


async def test_pagination_after_dedupe(seeded_session: AsyncSession) -> None:
    admin = await get_user(seeded_session, "admin@demo.dev")
    first = await search_chunks(seeded_session, admin, "", SearchFilters(page=1, page_size=4))
    second = await search_chunks(seeded_session, admin, "", SearchFilters(page=2, page_size=4))
    third = await search_chunks(seeded_session, admin, "", SearchFilters(page=3, page_size=4))
    assert first.total == second.total == third.total == 10
    assert len(first.items) == 4
    assert len(second.items) == 4
    assert len(third.items) == 2
    all_ids = [h.document_id for h in first.items + second.items + third.items]
    assert len(all_ids) == len(set(all_ids)) == 10


async def test_empty_query_returns_recent_authoritative(seeded_session: AsyncSession) -> None:
    admin = await get_user(seeded_session, "admin@demo.dev")
    page = await search_chunks(seeded_session, admin, "   ", SearchFilters())
    assert page.total == 10
    assert page.items
    scores = [hit.score for hit in page.items]
    assert scores == sorted(scores, reverse=True)
    # Snippets and metadata are populated even without a query.
    assert all(hit.snippet for hit in page.items)
    assert all(hit.source_name for hit in page.items)

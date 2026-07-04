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
    SearchEvent,
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
    # Scores are freshness+authority driven and bounded; MMR may diversify the exact
    # order, so we assert validity/range rather than strict monotonicity.
    scores = [hit.score for hit in page.items]
    assert all(0.0 <= s <= 1.0 for s in scores)
    # Snippets and metadata are populated even without a query.
    assert all(hit.snippet for hit in page.items)
    assert all(hit.source_name for hit in page.items)


async def test_or_fallback_recalls_multi_term_partial_matches(
    seeded_session: AsyncSession,
) -> None:
    admin = await get_user(seeded_session, "admin@demo.dev")
    # Two docs each carry only ONE of the two distinctive terms, so a strict websearch
    # AND-style match for both terms finds neither; the OR-of-lexemes recall fallback
    # must surface them.
    doc_a = await make_doc(
        seeded_session,
        title="Quokka runbook",
        contents=["The quokka procedure covers restart steps for the mascot cluster."],
    )
    doc_b = await make_doc(
        seeded_session,
        title="Narwhal runbook",
        contents=["The narwhal procedure covers restart steps for the arctic cluster."],
    )
    page = await search_chunks(seeded_session, admin, "quokka narwhal", SearchFilters())
    found = {hit.document_id for hit in page.items}
    assert str(doc_a.id) in found
    assert str(doc_b.id) in found


async def test_min_max_normalization_stabilizes_ordering(
    seeded_session: AsyncSession,
) -> None:
    admin = await get_user(seeded_session, "admin@demo.dev")
    # Legs are min-max normalized then weighted, so all scores land in [0, 1]. With
    # MMR lambda=1 (pure relevance) the ordering is strictly non-increasing.
    await set_setting(seeded_session, "retrieval_extras", {"mmr_lambda": 1.0})
    page = await search_chunks(seeded_session, admin, "idempotency webhooks", SearchFilters())
    assert page.items
    scores = [hit.score for hit in page.items]
    assert scores == sorted(scores, reverse=True)
    assert all(0.0 <= s <= 1.0 for s in scores)


async def test_phrase_boost_lifts_exact_title_match(seeded_session: AsyncSession) -> None:
    admin = await get_user(seeded_session, "admin@demo.dev")
    phrase = "flamingo migration checklist"
    exact = await make_doc(
        seeded_session,
        title="Flamingo migration checklist",
        contents=["Follow the flamingo migration checklist before cutting over."],
    )
    # A doc mentioning only the individual words, without the exact phrase.
    await make_doc(
        seeded_session,
        title="Assorted notes",
        contents=["The flamingo lives near the migration path; keep a checklist somewhere."],
    )
    page = await search_chunks(seeded_session, admin, phrase, SearchFilters())
    # The exact-phrase title match ranks first thanks to the phrase/title boost.
    assert page.items[0].document_id == str(exact.id)


async def test_mmr_reduces_same_topic_adjacency(seeded_session: AsyncSession) -> None:
    admin = await get_user(seeded_session, "admin@demo.dev")
    # Four near-duplicate "wombat" docs plus one distinct "wombat" doc. Under pure
    # relevance the near-duplicates cluster at the top; MMR should interleave the
    # distinct doc earlier. We assert MMR (lambda 0.5) differs from pure relevance
    # (lambda 1.0) — i.e. diversification actually reorders the head.
    shared = "Wombat deployment: rollout steps for the burrow service in production."
    for i in range(4):
        await make_doc(
            seeded_session,
            title=f"Wombat rollout copy {i}",
            contents=[shared],
            repo="wombat-svc",
            service="wombat-svc",
        )
    await make_doc(
        seeded_session,
        title="Wombat incident retro",
        contents=["Wombat incident retro: burrow service outage postmortem and lessons."],
        repo="wombat-svc",
        service="wombat-svc",
    )

    await set_setting(seeded_session, "retrieval_extras", {"mmr_lambda": 0.5})
    diverse = await search_chunks(
        seeded_session, admin, "wombat burrow service", SearchFilters(repo="wombat-svc")
    )
    await set_setting(seeded_session, "retrieval_extras", {"mmr_lambda": 1.0})
    relevance = await search_chunks(
        seeded_session, admin, "wombat burrow service", SearchFilters(repo="wombat-svc")
    )

    diverse_ids = [h.document_id for h in diverse.items]
    relevance_ids = [h.document_id for h in relevance.items]
    # Same candidate set, but diversification changes the head ordering.
    assert set(diverse_ids) == set(relevance_ids)
    assert diverse_ids != relevance_ids


async def test_search_records_telemetry_event(seeded_session: AsyncSession) -> None:
    admin = await get_user(seeded_session, "admin@demo.dev")
    before = await _event_count(seeded_session)
    page = await search_chunks(seeded_session, admin, "idempotency", SearchFilters())
    after = await _event_count(seeded_session)
    assert after == before + 1

    event = (
        await seeded_session.execute(
            select(SearchEvent).order_by(SearchEvent.created_at.desc()).limit(1)
        )
    ).scalar_one()
    assert event.query == "idempotency"
    assert event.user_id == admin.id
    assert event.result_count == page.total
    assert event.cache_hit is False
    assert event.took_ms >= 0.0
    assert len(event.top_document_ids) <= 10
    assert event.top_document_ids == [h.document_id for h in page.items[:10]]


async def test_zero_result_query_records_zero_count_event(
    seeded_session: AsyncSession,
) -> None:
    admin = await get_user(seeded_session, "admin@demo.dev")
    await search_chunks(
        seeded_session, admin, "zznonexistentqqterm", SearchFilters(repo="no-such-repo")
    )
    event = (
        await seeded_session.execute(
            select(SearchEvent).order_by(SearchEvent.created_at.desc()).limit(1)
        )
    ).scalar_one()
    assert event.result_count == 0


async def _event_count(session: AsyncSession) -> int:
    from sqlalchemy import func

    return int((await session.execute(select(func.count()).select_from(SearchEvent))).scalar_one())

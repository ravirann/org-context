"""Context-debt report: 8 sections present and coherent with seed data."""

from __future__ import annotations


async def test_report_shape(api_client: object) -> None:
    r = await api_client.get("/v1/context-debt")  # type: ignore[attr-defined]
    assert r.status_code == 200
    body = r.json()
    for section in (
        "stale_docs",
        "missing_owners",
        "undocumented_apis",
        "repeated_misses",
        "failed_agent_areas",
        "never_used_docs",
        "frequently_rejected_docs",
        "conflicts_by_source_type",
    ):
        assert section in body
        assert isinstance(body[section], list)


async def test_stale_docs_present(api_client: object) -> None:
    body = (await api_client.get("/v1/context-debt")).json()  # type: ignore[attr-defined]
    # The legacy runbook is stale.
    assert body["stale_docs"]
    total_stale = sum(r["count"] for r in body["stale_docs"])
    assert total_stale >= 1


async def test_failed_agent_areas(api_client: object) -> None:
    body = (await api_client.get("/v1/context-debt")).json()  # type: ignore[attr-defined]
    # payments-api has a failed agent run.
    assert any(
        r["service"] == "payments-api" and r["failed"] >= 1 for r in body["failed_agent_areas"]
    )


async def test_conflicts_by_source_type(api_client: object) -> None:
    body = (await api_client.get("/v1/context-debt")).json()  # type: ignore[attr-defined]
    # The seeded conflict spans an adr and a confluence doc.
    types = {r["source_type"] for r in body["conflicts_by_source_type"]}
    assert "adr" in types or "confluence" in types


async def test_repeated_misses_zero_result_searches(
    api_client: object, seeded_session: object
) -> None:
    # Zero-result searches (SearchEvent rows) grouped by lowercased query -> count.
    from sqlalchemy import select

    from context_engine.storage.models import SearchEvent, User

    admin = (
        await seeded_session.execute(  # type: ignore[attr-defined]
            select(User).where(User.email == "admin@demo.dev")
        )
    ).scalar_one()
    # Two zero-result rows for the same query (varied case -> normalized together),
    # plus one with results that must NOT be counted.
    for query, result_count in [
        ("Where is the deploy runbook?", 0),
        ("where is the deploy runbook?", 0),
        ("where is the deploy runbook?", 3),
    ]:
        seeded_session.add(  # type: ignore[attr-defined]
            SearchEvent(
                user_id=admin.id,
                query=query,
                result_count=result_count,
                acl_blocked_count=0,
                took_ms=1.0,
                cache_hit=False,
                top_document_ids=[],
            )
        )
    await seeded_session.flush()  # type: ignore[attr-defined]

    body = (await api_client.get("/v1/context-debt")).json()  # type: ignore[attr-defined]
    hit = next(
        (r for r in body["repeated_misses"] if r["query"] == "where is the deploy runbook?"),
        None,
    )
    assert hit is not None
    assert hit["count"] == 2

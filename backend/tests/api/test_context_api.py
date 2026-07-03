"""Context packet endpoints: compile, list (filters), detail (feedback/agent_run)."""

from __future__ import annotations

from sqlalchemy import select

from context_engine.storage.models import ContextPacket


async def test_compile_201_full_shape(api_client: object) -> None:
    r = await api_client.post(  # type: ignore[attr-defined]
        "/v1/context/compile",
        json={"task": "What retry policy should payment charges use?", "service": "payments-api"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    for key in (
        "id",
        "task",
        "intent",
        "compiled_context",
        "selected_sources",
        "rejected_sources",
        "citations",
        "conflict_notes",
        "acl_notes",
        "token_estimate",
        "confidence_score",
        "freshness_score",
        "authority_score",
        "risks",
        "recommended_tests",
        "agent_outcome",
        "requested_by_name",
        "created_at",
    ):
        assert key in body
    assert body["requested_by_name"] == "Ava Admin"
    assert body["intent"] == "question"
    assert isinstance(body["acl_notes"], dict)
    assert "blocked_count" in body["acl_notes"]


async def test_compile_citations_and_selected(api_client: object) -> None:
    body = (
        await api_client.post(  # type: ignore[attr-defined]
            "/v1/context/compile",
            json={"task": "payment charge retry backoff jitter", "service": "payments-api"},
        )
    ).json()
    # Selected sources carry reasons; citations carry markers.
    if body["selected_sources"]:
        assert "reasons" in body["selected_sources"][0]
    for cite in body["citations"]:
        assert cite["marker"].startswith("S")


async def test_list_packets_shape(api_client: object) -> None:
    r = await api_client.get("/v1/context-packets?page=1&page_size=10")  # type: ignore[attr-defined]
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"items", "total", "page", "page_size"}
    assert body["total"] >= 2
    item = body["items"][0]
    for key in (
        "id",
        "task",
        "intent",
        "token_estimate",
        "confidence_score",
        "agent_outcome",
        "requested_by_name",
        "created_at",
        "source_count",
    ):
        assert key in item


async def test_list_packets_filter_repo(api_client: object) -> None:
    body = (
        await api_client.get("/v1/context-packets?repo=payments-api")  # type: ignore[attr-defined]
    ).json()
    for item in body["items"]:
        assert item["repo"] == "payments-api"


async def test_packet_detail_feedback_and_run(api_client: object, seeded_session: object) -> None:
    # Seed packet 0 (admin requester) has a useful feedback + a succeeded agent run.
    packet = (
        (
            await seeded_session.execute(  # type: ignore[attr-defined]
                select(ContextPacket).order_by(ContextPacket.created_at)
            )
        )
        .scalars()
        .first()
    )
    body = (
        await api_client.get(f"/v1/context-packets/{packet.id}")  # type: ignore[attr-defined]
    ).json()
    assert "feedback" in body
    assert "agent_run" in body
    # feedback entries carry the user name.
    for fb in body["feedback"]:
        assert "user_name" in fb


async def test_packet_detail_404(api_client: object) -> None:
    r = await api_client.get(  # type: ignore[attr-defined]
        "/v1/context-packets/00000000-0000-0000-0000-000000000000"
    )
    assert r.status_code == 404

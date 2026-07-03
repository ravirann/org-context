"""Search endpoint: ACL filtering, pagination shape, filters."""

from __future__ import annotations

from tests.conftest import ENGINEER_KEY, auth_headers


async def test_search_basic_shape(api_client: object) -> None:
    r = await api_client.post(  # type: ignore[attr-defined]
        "/v1/search", json={"query": "payments retry policy", "page": 1, "page_size": 20}
    )
    assert r.status_code == 200
    body = r.json()
    assert set(body) >= {"items", "total", "page", "page_size", "acl_blocked_count"}
    assert body["page"] == 1
    assert body["page_size"] == 20
    assert isinstance(body["items"], list)
    if body["items"]:
        hit = body["items"][0]
        for key in (
            "document_id",
            "chunk_id",
            "title",
            "doc_type",
            "source_name",
            "snippet",
            "score",
            "status",
            "freshness_score",
            "authority_score",
            "last_activity_at",
        ):
            assert key in hit


async def test_search_admin_no_blocked(api_client: object) -> None:
    body = (
        await api_client.post("/v1/search", json={"query": "credentials rotation"})  # type: ignore[attr-defined]
    ).json()
    # Admin sees everything -> nothing blocked.
    assert body["acl_blocked_count"] == 0


async def test_search_engineer_acl_blocked(api_client: object) -> None:
    # The engineer (Growth team) cannot see the payments-team-restricted postmortem
    # nor the admin-only credentials doc.
    body = (
        await api_client.post(  # type: ignore[attr-defined]
            "/v1/search",
            json={"query": "duplicate charges postmortem customer impact"},
            headers=auth_headers(ENGINEER_KEY),
        )
    ).json()
    assert body["acl_blocked_count"] >= 1


async def test_search_filters(api_client: object) -> None:
    body = (
        await api_client.post(  # type: ignore[attr-defined]
            "/v1/search",
            json={"query": "payments", "doc_types": ["adr"], "page_size": 50},
        )
    ).json()
    for hit in body["items"]:
        assert hit["doc_type"] == "adr"


async def test_search_pagination(api_client: object) -> None:
    body = (
        await api_client.post(  # type: ignore[attr-defined]
            "/v1/search", json={"query": "payments", "page": 1, "page_size": 2}
        )
    ).json()
    assert body["page_size"] == 2
    assert len(body["items"]) <= 2

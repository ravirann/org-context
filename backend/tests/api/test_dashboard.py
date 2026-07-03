"""Dashboard summary and trends endpoints."""

from __future__ import annotations


async def test_summary_shape(api_client: object) -> None:
    r = await api_client.get("/v1/dashboard/summary")  # type: ignore[attr-defined]
    assert r.status_code == 200
    body = r.json()
    for key in (
        "total_documents",
        "connected_sources",
        "active_repos",
        "active_services",
        "active_users",
        "context_packets",
        "agent_runs",
        "failed_agent_runs",
        "stale_documents",
        "conflicting_documents",
        "acl_violations_blocked",
        "latest_eval_score",
    ):
        assert key in body
    assert body["total_documents"] > 0
    assert body["connected_sources"] == 2
    assert body["active_users"] == 4
    # One failed agent run in seed_minimal.
    assert body["failed_agent_runs"] == 1
    # Two docs share the open conflict.
    assert body["conflicting_documents"] == 2
    # Latest completed eval run avg_score in seed = 0.8.
    assert body["latest_eval_score"] == 0.8


async def test_summary_stale_and_sources(api_client: object) -> None:
    body = (await api_client.get("/v1/dashboard/summary")).json()  # type: ignore[attr-defined]
    assert body["stale_documents"] >= 1  # legacy runbook is stale
    assert body["agent_runs"] == 2


async def test_trends_shape(api_client: object) -> None:
    r = await api_client.get("/v1/dashboard/trends?days=30")  # type: ignore[attr-defined]
    assert r.status_code == 200
    body = r.json()
    for series in ("eval_scores", "source_freshness", "review_rework", "packets_per_day"):
        assert series in body
        assert isinstance(body[series], list)
        # 30 dense daily points.
        assert len(body[series]) == 30
        for point in body[series]:
            assert set(point) == {"date", "value"}


async def test_trends_days_param(api_client: object) -> None:
    body = (await api_client.get("/v1/dashboard/trends?days=7")).json()  # type: ignore[attr-defined]
    assert len(body["eval_scores"]) == 7

"""Heatmap endpoints: users, ownership, context-debt."""

from __future__ import annotations


async def test_users_heatmap_shape(api_client: object) -> None:
    r = await api_client.get("/v1/heatmaps/users?metric=all")  # type: ignore[attr-defined]
    assert r.status_code == 200
    body = r.json()
    assert "rows" in body and "days" in body
    assert isinstance(body["days"], list)
    if body["rows"]:
        row = body["rows"][0]
        for key in ("user_id", "user_name", "team_name", "cells", "total"):
            assert key in row
        # Each cell aligns to the days axis.
        assert len(row["cells"]) == len(body["days"])
        # Rows sorted by total desc.
        totals = [r["total"] for r in body["rows"]]
        assert totals == sorted(totals, reverse=True)


async def test_users_heatmap_metric_filter(api_client: object) -> None:
    body = (
        await api_client.get("/v1/heatmaps/users?metric=commit")  # type: ignore[attr-defined]
    ).json()
    # Seed has commit events, so at least one row appears.
    assert body["rows"]


async def test_users_heatmap_date_range(api_client: object) -> None:
    body = (
        await api_client.get(  # type: ignore[attr-defined]
            "/v1/heatmaps/users?from=2020-01-01&to=2020-01-07"
        )
    ).json()
    assert len(body["days"]) == 7


async def test_ownership_shape(api_client: object) -> None:
    r = await api_client.get("/v1/heatmaps/ownership")  # type: ignore[attr-defined]
    assert r.status_code == 200
    body = r.json()
    assert "rows" in body
    assert body["rows"]
    row = body["rows"][0]
    for key in (
        "key",
        "owner_team",
        "doc_count",
        "owner_user_names",
        "coverage_score",
        "last_activity_at",
    ):
        assert key in row
    # payments-api docs are Payments-team owned.
    payments = next((r for r in body["rows"] if r["key"] == "payments-api"), None)
    assert payments is not None
    assert payments["owner_team"] == "Payments"
    assert 0.0 <= payments["coverage_score"] <= 1.0


async def test_context_debt_heatmap_shape(api_client: object) -> None:
    r = await api_client.get("/v1/heatmaps/context-debt")  # type: ignore[attr-defined]
    assert r.status_code == 200
    body = r.json()
    assert "rows" in body
    row = body["rows"][0]
    for key in (
        "key",
        "repo",
        "service",
        "team_name",
        "stale_count",
        "missing_owner",
        "conflict_count",
        "rejected_count",
        "failed_runs",
        "debt_score",
    ):
        assert key in row
    assert all(0.0 <= r["debt_score"] <= 1.0 for r in body["rows"])
    # payments-api has a stale doc, an open conflict, and a failed run.
    payments = next((r for r in body["rows"] if r["key"] == "payments-api"), None)
    assert payments is not None
    assert payments["stale_count"] >= 1
    assert payments["conflict_count"] >= 1
    assert payments["failed_runs"] >= 1

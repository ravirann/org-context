"""API tests for GET /v1/system/info (admin-only) — PHASE3_CONTRACT §A."""

from __future__ import annotations

import httpx

from tests.conftest import auth_headers


async def test_system_info_admin_ok(api_client: httpx.AsyncClient) -> None:
    resp = await api_client.get("/v1/system/info")
    assert resp.status_code == 200
    body = resp.json()

    assert body["embedding"] == {
        "provider": "deterministic",
        "model": "sha256-v1",
        "dim": 384,
    }
    assert body["auth_mode"] == "demo"
    assert body["version"] == "0.3.0"
    # queue_depth is int (redis reachable) or null (any error) — never absent.
    assert "queue_depth" in body
    assert body["queue_depth"] is None or isinstance(body["queue_depth"], int)


async def test_system_info_viewer_forbidden(api_client: httpx.AsyncClient) -> None:
    resp = await api_client.get("/v1/system/info", headers=auth_headers("demo-viewer-key"))
    assert resp.status_code == 403


async def test_system_info_unauthenticated(noauth_client: httpx.AsyncClient) -> None:
    resp = await noauth_client.get("/v1/system/info")
    assert resp.status_code == 401

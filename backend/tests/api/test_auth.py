"""Authentication and RBAC gating across the /v1 API."""

from __future__ import annotations

from tests.conftest import (
    ENGINEER_KEY,
    LEAD_KEY,
    VIEWER_KEY,
    auth_headers,
)


async def test_healthz_open(noauth_client: object) -> None:
    r = await noauth_client.get("/healthz")  # type: ignore[attr-defined]
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


async def test_missing_auth_401(noauth_client: object) -> None:
    r = await noauth_client.get("/v1/me")  # type: ignore[attr-defined]
    assert r.status_code == 401
    assert r.json() == {"detail": "Not authenticated"}


async def test_bad_key_401(api_client: object) -> None:
    r = await api_client.get(  # type: ignore[attr-defined]
        "/v1/me", headers={"Authorization": "Bearer not-a-real-key"}
    )
    assert r.status_code == 401
    assert r.json() == {"detail": "Not authenticated"}


async def test_no_scheme_401(api_client: object) -> None:
    r = await api_client.get(  # type: ignore[attr-defined]
        "/v1/me", headers={"Authorization": "demo-admin-key"}
    )
    assert r.status_code == 401


async def test_valid_key_200(api_client: object) -> None:
    r = await api_client.get("/v1/me")  # type: ignore[attr-defined]
    assert r.status_code == 200
    assert r.json()["role"] == "admin"


async def test_viewer_forbidden_on_admin(api_client: object) -> None:
    r = await api_client.get(  # type: ignore[attr-defined]
        "/v1/admin/users", headers=auth_headers(VIEWER_KEY)
    )
    assert r.status_code == 403


async def test_engineer_forbidden_on_admin(api_client: object) -> None:
    r = await api_client.get(  # type: ignore[attr-defined]
        "/v1/admin/settings" if False else "/v1/settings", headers=auth_headers(ENGINEER_KEY)
    )
    assert r.status_code == 403


async def test_engineer_forbidden_on_source_sync(
    api_client: object, seeded_session: object
) -> None:
    from sqlalchemy import select

    from context_engine.storage.models import Source

    source = (
        await seeded_session.execute(select(Source).limit(1))  # type: ignore[attr-defined]
    ).scalar_one()
    r = await api_client.post(  # type: ignore[attr-defined]
        f"/v1/sources/{source.id}/sync", headers=auth_headers(ENGINEER_KEY)
    )
    assert r.status_code == 403


async def test_lead_allowed_on_source_sync(api_client: object, seeded_session: object) -> None:
    from sqlalchemy import select

    from context_engine.storage.models import Source

    source = (
        await seeded_session.execute(select(Source).limit(1))  # type: ignore[attr-defined]
    ).scalar_one()
    r = await api_client.post(  # type: ignore[attr-defined]
        f"/v1/sources/{source.id}/sync", headers=auth_headers(LEAD_KEY)
    )
    assert r.status_code == 202
    assert r.json() == {"status": "queued"}


async def test_viewer_forbidden_on_source_create(api_client: object) -> None:
    r = await api_client.post(  # type: ignore[attr-defined]
        "/v1/sources",
        json={"type": "github", "name": "x"},
        headers=auth_headers(VIEWER_KEY),
    )
    assert r.status_code == 403

"""Source CRUD, sync enqueue, and RBAC matrix."""

from __future__ import annotations

from sqlalchemy import func, select

from context_engine.storage.models import AuditLog, Source
from tests.conftest import ENGINEER_KEY, LEAD_KEY, VIEWER_KEY, auth_headers


async def test_list_sources(api_client: object) -> None:
    r = await api_client.get("/v1/sources")  # type: ignore[attr-defined]
    assert r.status_code == 200
    body = r.json()
    assert "items" in body
    assert len(body["items"]) == 2
    src = body["items"][0]
    for key in (
        "id",
        "type",
        "name",
        "enabled",
        "sync_status",
        "document_count",
        "acl_sync_status",
        "authority_rank",
        "freshness_window_days",
    ):
        assert key in src


async def test_create_source_admin(api_client: object) -> None:
    r = await api_client.post(  # type: ignore[attr-defined]
        "/v1/sources", json={"type": "github", "name": "New Repo Source"}
    )
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "New Repo Source"
    assert body["type"] == "github"


async def test_create_source_viewer_forbidden(api_client: object) -> None:
    r = await api_client.post(  # type: ignore[attr-defined]
        "/v1/sources",
        json={"type": "github", "name": "x"},
        headers=auth_headers(VIEWER_KEY),
    )
    assert r.status_code == 403


async def test_delete_source_admin(api_client: object, seeded_session: object) -> None:
    created = (
        await api_client.post(  # type: ignore[attr-defined]
            "/v1/sources", json={"type": "jira", "name": "Deletable"}
        )
    ).json()
    r = await api_client.delete(f"/v1/sources/{created['id']}")  # type: ignore[attr-defined]
    assert r.status_code == 204


async def test_delete_source_engineer_forbidden(api_client: object, seeded_session: object) -> None:
    source = (
        await seeded_session.execute(select(Source).limit(1))  # type: ignore[attr-defined]
    ).scalar_one()
    r = await api_client.delete(  # type: ignore[attr-defined]
        f"/v1/sources/{source.id}", headers=auth_headers(ENGINEER_KEY)
    )
    assert r.status_code == 403


async def test_sync_lead_202_and_audit(api_client: object, seeded_session: object) -> None:
    source = (
        await seeded_session.execute(select(Source).limit(1))  # type: ignore[attr-defined]
    ).scalar_one()
    before = (
        await seeded_session.execute(  # type: ignore[attr-defined]
            select(func.count()).select_from(AuditLog).where(AuditLog.action == "source.sync")
        )
    ).scalar_one()
    r = await api_client.post(  # type: ignore[attr-defined]
        f"/v1/sources/{source.id}/sync", headers=auth_headers(LEAD_KEY)
    )
    assert r.status_code == 202
    assert r.json() == {"status": "queued"}
    after = (
        await seeded_session.execute(  # type: ignore[attr-defined]
            select(func.count()).select_from(AuditLog).where(AuditLog.action == "source.sync")
        )
    ).scalar_one()
    assert after == before + 1


async def test_sync_engineer_forbidden(api_client: object, seeded_session: object) -> None:
    source = (
        await seeded_session.execute(select(Source).limit(1))  # type: ignore[attr-defined]
    ).scalar_one()
    r = await api_client.post(  # type: ignore[attr-defined]
        f"/v1/sources/{source.id}/sync", headers=auth_headers(ENGINEER_KEY)
    )
    assert r.status_code == 403


async def test_patch_source_admin(api_client: object, seeded_session: object) -> None:
    source = (
        await seeded_session.execute(select(Source).limit(1))  # type: ignore[attr-defined]
    ).scalar_one()
    r = await api_client.patch(  # type: ignore[attr-defined]
        f"/v1/sources/{source.id}", json={"authority_rank": 42, "enabled": False}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["authority_rank"] == 42
    assert body["enabled"] is False


async def test_patch_source_engineer_forbidden(api_client: object, seeded_session: object) -> None:
    source = (
        await seeded_session.execute(select(Source).limit(1))  # type: ignore[attr-defined]
    ).scalar_one()
    r = await api_client.patch(  # type: ignore[attr-defined]
        f"/v1/sources/{source.id}",
        json={"authority_rank": 10},
        headers=auth_headers(ENGINEER_KEY),
    )
    assert r.status_code == 403

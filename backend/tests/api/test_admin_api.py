"""Admin & settings endpoints: users/teams/keys/audit + settings GET/PATCH persist."""

from __future__ import annotations

from sqlalchemy import func, select

from context_engine.storage.models import AuditLog
from tests.conftest import VIEWER_KEY, auth_headers


async def test_users(api_client: object) -> None:
    r = await api_client.get("/v1/admin/users")  # type: ignore[attr-defined]
    assert r.status_code == 200
    body = r.json()
    assert len(body["items"]) == 4
    u = body["items"][0]
    for key in ("id", "email", "name", "role", "team_name", "is_active"):
        assert key in u


async def test_teams(api_client: object) -> None:
    body = (await api_client.get("/v1/admin/teams")).json()  # type: ignore[attr-defined]
    assert len(body["items"]) == 2
    for t in body["items"]:
        assert "member_count" in t
    payments = next(t for t in body["items"] if t["name"] == "Payments")
    assert payments["member_count"] == 2


async def test_api_keys_no_material(api_client: object) -> None:
    body = (await api_client.get("/v1/admin/api-keys")).json()  # type: ignore[attr-defined]
    assert len(body["items"]) == 5
    k = body["items"][0]
    for key in ("id", "label", "kind", "user_name", "is_active", "last_used_at"):
        assert key in k
    # Never expose key material.
    assert "key_hash" not in k


async def test_audit_logs_filter(api_client: object) -> None:
    body = (
        await api_client.get("/v1/admin/audit-logs?action=source.sync")  # type: ignore[attr-defined]
    ).json()
    assert set(body) == {"items", "total", "page", "page_size"}
    for a in body["items"]:
        assert a["action"] == "source.sync"


async def test_admin_viewer_forbidden(api_client: object) -> None:
    r = await api_client.get(  # type: ignore[attr-defined]
        "/v1/admin/teams", headers=auth_headers(VIEWER_KEY)
    )
    assert r.status_code == 403


async def test_settings_get(api_client: object) -> None:
    r = await api_client.get("/v1/settings")  # type: ignore[attr-defined]
    assert r.status_code == 200
    body = r.json()
    for key in (
        "retrieval_weights",
        "freshness_window_days",
        "authority_rules",
        "eval_thresholds",
        "retention",
        "pii_redaction",
        "feature_flags",
        "token_budget",
    ):
        assert key in body


async def test_settings_patch_persists_and_audits(
    api_client: object, seeded_session: object
) -> None:
    before = (
        await seeded_session.execute(  # type: ignore[attr-defined]
            select(func.count()).select_from(AuditLog).where(AuditLog.action == "settings.update")
        )
    ).scalar_one()
    r = await api_client.patch(  # type: ignore[attr-defined]
        "/v1/settings", json={"freshness_window_days": 45}
    )
    assert r.status_code == 200
    assert r.json()["freshness_window_days"] == 45
    # Re-read confirms persistence.
    again = (await api_client.get("/v1/settings")).json()  # type: ignore[attr-defined]
    assert again["freshness_window_days"] == 45
    after = (
        await seeded_session.execute(  # type: ignore[attr-defined]
            select(func.count()).select_from(AuditLog).where(AuditLog.action == "settings.update")
        )
    ).scalar_one()
    assert after == before + 1


async def test_settings_patch_viewer_forbidden(api_client: object) -> None:
    r = await api_client.patch(  # type: ignore[attr-defined]
        "/v1/settings",
        json={"freshness_window_days": 1},
        headers=auth_headers(VIEWER_KEY),
    )
    assert r.status_code == 403

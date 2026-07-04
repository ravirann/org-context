"""User & access management endpoints: users, teams, api-keys, audit trail."""

from __future__ import annotations

from sqlalchemy import func, select

from context_engine.storage.models import AuditLog, Team, User
from tests.conftest import ENGINEER_KEY, VIEWER_KEY, auth_headers


async def _admin_id(seeded_session: object) -> str:
    admin = (
        await seeded_session.execute(  # type: ignore[attr-defined]
            select(User).where(User.email == "admin@demo.dev")
        )
    ).scalar_one()
    return str(admin.id)


async def _audit_count(seeded_session: object, action: str) -> int:
    return (
        await seeded_session.execute(  # type: ignore[attr-defined]
            select(func.count()).select_from(AuditLog).where(AuditLog.action == action)
        )
    ).scalar_one()


# --------------------------------------------------------------------------- #
# Users: create                                                                #
# --------------------------------------------------------------------------- #


async def test_create_user(api_client: object, seeded_session: object) -> None:
    before = await _audit_count(seeded_session, "user.create")
    r = await api_client.post(  # type: ignore[attr-defined]
        "/v1/admin/users",
        json={"email": "new.hire@demo.dev", "name": "New Hire", "role": "engineer"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["email"] == "new.hire@demo.dev"
    assert body["name"] == "New Hire"
    assert body["role"] == "engineer"
    assert body["is_active"] is True
    after = await _audit_count(seeded_session, "user.create")
    assert after == before + 1


async def test_create_user_duplicate_email_case_insensitive(api_client: object) -> None:
    r = await api_client.post(  # type: ignore[attr-defined]
        "/v1/admin/users",
        json={"email": "ADMIN@demo.dev", "name": "Dupe", "role": "viewer"},
    )
    assert r.status_code == 409


async def test_create_user_viewer_forbidden(api_client: object) -> None:
    r = await api_client.post(  # type: ignore[attr-defined]
        "/v1/admin/users",
        json={"email": "x@demo.dev", "name": "X", "role": "viewer"},
        headers=auth_headers(VIEWER_KEY),
    )
    assert r.status_code == 403


async def test_create_user_engineer_forbidden(api_client: object) -> None:
    r = await api_client.post(  # type: ignore[attr-defined]
        "/v1/admin/users",
        json={"email": "y@demo.dev", "name": "Y", "role": "viewer"},
        headers=auth_headers(ENGINEER_KEY),
    )
    assert r.status_code == 403


# --------------------------------------------------------------------------- #
# Users: update                                                                #
# --------------------------------------------------------------------------- #


async def test_update_user_role_and_team(api_client: object, seeded_session: object) -> None:
    growth = (
        await seeded_session.execute(  # type: ignore[attr-defined]
            select(Team).where(Team.name == "Growth")
        )
    ).scalar_one()
    lead = (
        await seeded_session.execute(  # type: ignore[attr-defined]
            select(User).where(User.email == "priya@demo.dev")
        )
    ).scalar_one()
    before = await _audit_count(seeded_session, "user.update")
    r = await api_client.patch(  # type: ignore[attr-defined]
        f"/v1/admin/users/{lead.id}",
        json={"role": "engineer", "team_id": str(growth.id)},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["role"] == "engineer"
    assert body["team_name"] == "Growth"
    after = await _audit_count(seeded_session, "user.update")
    assert after == before + 1


async def test_update_user_deactivate(api_client: object, seeded_session: object) -> None:
    engineer = (
        await seeded_session.execute(  # type: ignore[attr-defined]
            select(User).where(User.email == "jade@demo.dev")
        )
    ).scalar_one()
    r = await api_client.patch(  # type: ignore[attr-defined]
        f"/v1/admin/users/{engineer.id}", json={"is_active": False}
    )
    assert r.status_code == 200
    assert r.json()["is_active"] is False


async def test_update_user_self_demote_400(api_client: object, seeded_session: object) -> None:
    admin_id = await _admin_id(seeded_session)
    r = await api_client.patch(  # type: ignore[attr-defined]
        f"/v1/admin/users/{admin_id}", json={"role": "engineer"}
    )
    assert r.status_code == 400


async def test_update_user_self_deactivate_400(api_client: object, seeded_session: object) -> None:
    admin_id = await _admin_id(seeded_session)
    r = await api_client.patch(  # type: ignore[attr-defined]
        f"/v1/admin/users/{admin_id}", json={"is_active": False}
    )
    assert r.status_code == 400


async def test_update_user_404(api_client: object) -> None:
    r = await api_client.patch(  # type: ignore[attr-defined]
        "/v1/admin/users/00000000-0000-0000-0000-000000000000",
        json={"name": "Nobody"},
    )
    assert r.status_code == 404


# --------------------------------------------------------------------------- #
# Deactivated user's API key stops authenticating                             #
# --------------------------------------------------------------------------- #


async def test_deactivated_user_key_stops_authenticating(
    api_client: object, seeded_session: object
) -> None:
    create_resp = await api_client.post(  # type: ignore[attr-defined]
        "/v1/admin/users",
        json={"email": "temp.user@demo.dev", "name": "Temp User", "role": "engineer"},
    )
    assert create_resp.status_code == 201
    user_id = create_resp.json()["id"]

    key_resp = await api_client.post(  # type: ignore[attr-defined]
        "/v1/admin/api-keys",
        json={"label": "temp key", "kind": "api", "user_id": user_id},
    )
    assert key_resp.status_code == 201
    raw_key = key_resp.json()["raw_key"]
    assert raw_key.startswith("ce_api_")

    me_resp = await api_client.get(  # type: ignore[attr-defined]
        "/v1/me", headers=auth_headers(raw_key)
    )
    assert me_resp.status_code == 200
    assert me_resp.json()["email"] == "temp.user@demo.dev"

    deactivate_resp = await api_client.patch(  # type: ignore[attr-defined]
        f"/v1/admin/users/{user_id}", json={"is_active": False}
    )
    assert deactivate_resp.status_code == 200

    me_resp_2 = await api_client.get(  # type: ignore[attr-defined]
        "/v1/me", headers=auth_headers(raw_key)
    )
    assert me_resp_2.status_code == 401


# --------------------------------------------------------------------------- #
# Teams                                                                        #
# --------------------------------------------------------------------------- #


async def test_team_create(api_client: object, seeded_session: object) -> None:
    before = await _audit_count(seeded_session, "team.create")
    r = await api_client.post(  # type: ignore[attr-defined]
        "/v1/admin/teams", json={"name": "Security", "description": "Owns appsec."}
    )
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "Security"
    assert body["member_count"] == 0
    after = await _audit_count(seeded_session, "team.create")
    assert after == before + 1


async def test_team_rename(api_client: object, seeded_session: object) -> None:
    team = (
        await seeded_session.execute(  # type: ignore[attr-defined]
            select(Team).where(Team.name == "Payments")
        )
    ).scalar_one()
    before = await _audit_count(seeded_session, "team.update")
    r = await api_client.patch(  # type: ignore[attr-defined]
        f"/v1/admin/teams/{team.id}", json={"name": "Payments & Billing"}
    )
    assert r.status_code == 200
    assert r.json()["name"] == "Payments & Billing"
    after = await _audit_count(seeded_session, "team.update")
    assert after == before + 1


async def test_team_update_404(api_client: object) -> None:
    r = await api_client.patch(  # type: ignore[attr-defined]
        "/v1/admin/teams/00000000-0000-0000-0000-000000000000",
        json={"name": "Nope"},
    )
    assert r.status_code == 404


async def test_team_delete_nulls_member_team_id(api_client: object, seeded_session: object) -> None:
    growth = (
        await seeded_session.execute(  # type: ignore[attr-defined]
            select(Team).where(Team.name == "Growth")
        )
    ).scalar_one()
    member = (
        await seeded_session.execute(  # type: ignore[attr-defined]
            select(User).where(User.email == "jade@demo.dev")
        )
    ).scalar_one()
    assert member.team_id == growth.id

    before = await _audit_count(seeded_session, "team.delete")
    r = await api_client.delete(f"/v1/admin/teams/{growth.id}")  # type: ignore[attr-defined]
    assert r.status_code == 204
    after = await _audit_count(seeded_session, "team.delete")
    assert after == before + 1

    await seeded_session.refresh(member)  # type: ignore[attr-defined]
    assert member.team_id is None


async def test_team_delete_404(api_client: object) -> None:
    r = await api_client.delete(  # type: ignore[attr-defined]
        "/v1/admin/teams/00000000-0000-0000-0000-000000000000"
    )
    assert r.status_code == 404


# --------------------------------------------------------------------------- #
# API keys                                                                     #
# --------------------------------------------------------------------------- #


async def test_api_key_create_returns_raw_key_once_and_hides_from_list(
    api_client: object,
) -> None:
    admin_user = (await api_client.get("/v1/me")).json()  # type: ignore[attr-defined]
    r = await api_client.post(  # type: ignore[attr-defined]
        "/v1/admin/api-keys",
        json={"label": "ci bot", "kind": "mcp", "user_id": admin_user["id"]},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["raw_key"].startswith("ce_mcp_")
    assert "key_hash" not in body

    list_body = (await api_client.get("/v1/admin/api-keys")).json()  # type: ignore[attr-defined]
    for item in list_body["items"]:
        assert "raw_key" not in item
        assert "key_hash" not in item


async def test_api_key_create_inactive_user_400(api_client: object, seeded_session: object) -> None:
    user = (
        await seeded_session.execute(  # type: ignore[attr-defined]
            select(User).where(User.email == "maya@demo.dev")
        )
    ).scalar_one()
    user.is_active = False
    await seeded_session.flush()  # type: ignore[attr-defined]
    r = await api_client.post(  # type: ignore[attr-defined]
        "/v1/admin/api-keys",
        json={"label": "bad", "kind": "api", "user_id": str(user.id)},
    )
    assert r.status_code == 400


async def test_api_key_revoke_then_401_then_idempotent(
    api_client: object, seeded_session: object
) -> None:
    admin_user = (await api_client.get("/v1/me")).json()  # type: ignore[attr-defined]
    create_resp = await api_client.post(  # type: ignore[attr-defined]
        "/v1/admin/api-keys",
        json={"label": "revoke-me", "kind": "api", "user_id": admin_user["id"]},
    )
    key_id = create_resp.json()["id"]
    raw_key = create_resp.json()["raw_key"]

    ok = await api_client.get("/v1/me", headers=auth_headers(raw_key))  # type: ignore[attr-defined]
    assert ok.status_code == 200

    before = await _audit_count(seeded_session, "api_key.revoke")
    revoke_resp = await api_client.post(  # type: ignore[attr-defined]
        f"/v1/admin/api-keys/{key_id}/revoke"
    )
    assert revoke_resp.status_code == 200
    assert revoke_resp.json()["is_active"] is False
    after = await _audit_count(seeded_session, "api_key.revoke")
    assert after == before + 1

    denied = await api_client.get(  # type: ignore[attr-defined]
        "/v1/me", headers=auth_headers(raw_key)
    )
    assert denied.status_code == 401

    # Idempotent: revoking again succeeds without double-auditing.
    revoke_again = await api_client.post(  # type: ignore[attr-defined]
        f"/v1/admin/api-keys/{key_id}/revoke"
    )
    assert revoke_again.status_code == 200
    assert revoke_again.json()["is_active"] is False
    after_again = await _audit_count(seeded_session, "api_key.revoke")
    assert after_again == after

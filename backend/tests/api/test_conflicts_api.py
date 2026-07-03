"""Conflict endpoints: list, detail, resolve + audit."""

from __future__ import annotations

from sqlalchemy import func, select

from context_engine.storage.models import AuditLog, Conflict
from tests.conftest import ENGINEER_KEY, LEAD_KEY, auth_headers


async def _conflict(session: object) -> Conflict:
    return (await session.execute(select(Conflict))).scalars().first()  # type: ignore[attr-defined]


async def test_list_shape(api_client: object) -> None:
    r = await api_client.get("/v1/conflicts?page=1")  # type: ignore[attr-defined]
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"items", "total", "page", "page_size"}
    assert body["total"] >= 1
    item = body["items"][0]
    for key in ("id", "topic_key", "title", "status", "document_count", "affected", "created_at"):
        assert key in item
    assert item["document_count"] == 2


async def test_list_status_filter(api_client: object) -> None:
    body = (
        await api_client.get("/v1/conflicts?status=open")  # type: ignore[attr-defined]
    ).json()
    assert all(i["status"] == "open" for i in body["items"])


async def test_detail_shape(api_client: object, seeded_session: object) -> None:
    conflict = await _conflict(seeded_session)
    r = await api_client.get(f"/v1/conflicts/{conflict.id}")  # type: ignore[attr-defined]
    assert r.status_code == 200
    body = r.json()
    for key in (
        "id",
        "topic_key",
        "title",
        "status",
        "affected",
        "recommended_document_id",
        "documents",
    ):
        assert key in body
    assert len(body["documents"]) == 2
    doc = body["documents"][0]
    for key in (
        "id",
        "title",
        "doc_type",
        "source_name",
        "freshness_score",
        "authority_score",
        "excerpt",
    ):
        assert key in doc
    assert len(doc["excerpt"]) <= 300
    # Recommendation computed as highest authority*freshness.
    assert body["recommended_document_id"] is not None


async def test_resolve_lead_and_audit(api_client: object, seeded_session: object) -> None:
    conflict = await _conflict(seeded_session)
    before = (
        await seeded_session.execute(  # type: ignore[attr-defined]
            select(func.count()).select_from(AuditLog).where(AuditLog.action == "conflict.resolve")
        )
    ).scalar_one()
    r = await api_client.post(  # type: ignore[attr-defined]
        f"/v1/conflicts/{conflict.id}/resolve",
        json={"note": "ADR wins", "linked_adr_url": "https://demo.dev/adr/42"},
        headers=auth_headers(LEAD_KEY),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "resolved"
    assert body["resolution_note"] == "ADR wins"
    assert body["resolved_by_name"] == "Priya Sharma"
    after = (
        await seeded_session.execute(  # type: ignore[attr-defined]
            select(func.count()).select_from(AuditLog).where(AuditLog.action == "conflict.resolve")
        )
    ).scalar_one()
    assert after == before + 1


async def test_resolve_engineer_forbidden(api_client: object, seeded_session: object) -> None:
    conflict = await _conflict(seeded_session)
    r = await api_client.post(  # type: ignore[attr-defined]
        f"/v1/conflicts/{conflict.id}/resolve",
        json={"note": "no"},
        headers=auth_headers(ENGINEER_KEY),
    )
    assert r.status_code == 403


async def test_detail_404(api_client: object) -> None:
    r = await api_client.get(  # type: ignore[attr-defined]
        "/v1/conflicts/00000000-0000-0000-0000-000000000000"
    )
    assert r.status_code == 404

"""Document detail endpoint: full shape, ACL 404 vs 200, related/conflicts/usage."""

from __future__ import annotations

from sqlalchemy import select

from context_engine.storage.models import Document
from tests.conftest import ENGINEER_KEY, auth_headers


async def _doc_by_prefix(session: object, prefix: str) -> Document:
    stmt = select(Document).where(Document.title.startswith(prefix))
    return (await session.execute(stmt)).scalars().first()  # type: ignore[attr-defined]


async def test_document_detail_shape(api_client: object, seeded_session: object) -> None:
    adr = await _doc_by_prefix(seeded_session, "ADR-0042")
    r = await api_client.get(f"/v1/documents/{adr.id}")  # type: ignore[attr-defined]
    assert r.status_code == 200
    body = r.json()
    for key in (
        "id",
        "title",
        "content",
        "doc_type",
        "status",
        "source",
        "acl",
        "chunks",
        "citations_of",
        "related",
        "conflicts",
        "packet_usage",
    ):
        assert key in body
    assert body["source"]["name"] == "ADR Repository"
    assert set(body["acl"]) == {"public", "team_names", "user_count"}
    assert body["chunks"]  # ADR has at least one chunk
    ords = [c["ord"] for c in body["chunks"]]
    assert ords == sorted(ords)


async def test_document_detail_conflicts(api_client: object, seeded_session: object) -> None:
    adr = await _doc_by_prefix(seeded_session, "ADR-0042")
    body = (await api_client.get(f"/v1/documents/{adr.id}")).json()  # type: ignore[attr-defined]
    # ADR-0042 participates in the retry-policy conflict.
    assert any(c["topic_key"] == "payments-retry-policy" for c in body["conflicts"])


async def test_document_packet_usage(api_client: object, seeded_session: object) -> None:
    adr = await _doc_by_prefix(seeded_session, "ADR-0042")
    body = (await api_client.get(f"/v1/documents/{adr.id}")).json()  # type: ignore[attr-defined]
    # Seed packets select the ADR.
    assert any(u["was_selected"] for u in body["packet_usage"])


async def test_hidden_doc_404_for_engineer(api_client: object, seeded_session: object) -> None:
    secret = await _doc_by_prefix(seeded_session, "Secret infra credentials")
    r = await api_client.get(  # type: ignore[attr-defined]
        f"/v1/documents/{secret.id}", headers=auth_headers(ENGINEER_KEY)
    )
    assert r.status_code == 404


async def test_hidden_doc_200_for_admin(api_client: object, seeded_session: object) -> None:
    secret = await _doc_by_prefix(seeded_session, "Secret infra credentials")
    r = await api_client.get(f"/v1/documents/{secret.id}")  # type: ignore[attr-defined]
    assert r.status_code == 200
    body = r.json()
    assert body["acl"]["public"] is False
    assert body["acl"]["user_count"] == 1


async def test_team_restricted_acl_names(api_client: object, seeded_session: object) -> None:
    doc = await _doc_by_prefix(seeded_session, "Payments postmortem")
    body = (await api_client.get(f"/v1/documents/{doc.id}")).json()  # type: ignore[attr-defined]
    assert body["acl"]["public"] is False
    assert "Payments" in body["acl"]["team_names"]


async def test_missing_doc_404(api_client: object) -> None:
    r = await api_client.get(  # type: ignore[attr-defined]
        "/v1/documents/00000000-0000-0000-0000-000000000000"
    )
    assert r.status_code == 404

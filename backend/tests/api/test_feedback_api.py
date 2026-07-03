"""Feedback endpoint: all 8 types + document side effects."""

from __future__ import annotations

from sqlalchemy import select

from context_engine.storage.models import DocStatus, Document


async def _doc_by_prefix(session: object, prefix: str) -> Document:
    return (
        (
            await session.execute(  # type: ignore[attr-defined]
                select(Document).where(Document.title.startswith(prefix))
            )
        )
        .scalars()
        .first()
    )


async def _packet_id(session: object) -> str:
    from context_engine.storage.models import ContextPacket

    p = (
        (
            await session.execute(select(ContextPacket))  # type: ignore[attr-defined]
        )
        .scalars()
        .first()
    )
    return str(p.id)


async def test_feedback_out_shape(api_client: object, seeded_session: object) -> None:
    pid = await _packet_id(seeded_session)
    r = await api_client.post(  # type: ignore[attr-defined]
        "/v1/feedback",
        json={"type": "useful", "context_packet_id": pid, "comment": "great"},
    )
    assert r.status_code == 201
    body = r.json()
    for key in (
        "id",
        "type",
        "context_packet_id",
        "document_id",
        "comment",
        "user_name",
        "created_at",
    ):
        assert key in body
    assert body["user_name"] == "Ava Admin"


async def test_all_non_document_types(api_client: object, seeded_session: object) -> None:
    pid = await _packet_id(seeded_session)
    for ftype in (
        "useful",
        "irrelevant",
        "missing_context",
        "permission_issue",
        "suggest_source",
    ):
        r = await api_client.post(  # type: ignore[attr-defined]
            "/v1/feedback", json={"type": ftype, "context_packet_id": pid}
        )
        assert r.status_code == 201, (ftype, r.text)
        assert r.json()["type"] == ftype


async def test_promote_authoritative_side_effect(
    api_client: object, seeded_session: object
) -> None:
    doc = await _doc_by_prefix(seeded_session, "Payments guide 1")
    r = await api_client.post(  # type: ignore[attr-defined]
        "/v1/feedback",
        json={"type": "promote_authoritative", "document_id": str(doc.id)},
    )
    assert r.status_code == 201
    await seeded_session.refresh(doc)  # type: ignore[attr-defined]
    assert doc.authority_score == 1.0


async def test_mark_deprecated_side_effect(api_client: object, seeded_session: object) -> None:
    doc = await _doc_by_prefix(seeded_session, "Payments guide 2")
    r = await api_client.post(  # type: ignore[attr-defined]
        "/v1/feedback",
        json={"type": "mark_deprecated", "document_id": str(doc.id)},
    )
    assert r.status_code == 201
    await seeded_session.refresh(doc)  # type: ignore[attr-defined]
    assert doc.status == DocStatus.deprecated


async def test_stale_context_side_effect(api_client: object, seeded_session: object) -> None:
    doc = await _doc_by_prefix(seeded_session, "Payments guide 3")
    r = await api_client.post(  # type: ignore[attr-defined]
        "/v1/feedback",
        json={"type": "stale_context", "document_id": str(doc.id)},
    )
    assert r.status_code == 201
    await seeded_session.refresh(doc)  # type: ignore[attr-defined]
    assert doc.status == DocStatus.stale

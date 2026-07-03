"""Relationship graph and path endpoints (entities/edges created in-test)."""

from __future__ import annotations

from sqlalchemy import select

from context_engine.storage.models import (
    Document,
    Edge,
    EdgeType,
    Entity,
    EntityType,
)


async def _make_graph(session: object) -> tuple[Entity, Entity, Entity]:
    """Build repo -> service -> doc entities linked by edges, using a seeded stale doc."""
    stale_doc = (
        (
            await session.execute(  # type: ignore[attr-defined]
                select(Document).where(Document.status == "stale")
            )
        )
        .scalars()
        .first()
    )

    repo = Entity(type=EntityType.repo, name="payments-api", external_ref=None)
    service = Entity(type=EntityType.service, name="payments-svc", external_ref=None)
    doc_entity = Entity(type=EntityType.doc, name="legacy runbook", external_ref=str(stale_doc.id))
    session.add_all([repo, service, doc_entity])  # type: ignore[attr-defined]
    await session.flush()  # type: ignore[attr-defined]

    e1 = Edge(source_entity_id=repo.id, target_entity_id=service.id, type=EdgeType.depends_on)
    e2 = Edge(source_entity_id=service.id, target_entity_id=doc_entity.id, type=EdgeType.documents)
    session.add_all([e1, e2])  # type: ignore[attr-defined]
    await session.flush()  # type: ignore[attr-defined]
    return repo, service, doc_entity


async def test_graph_shape(api_client: object, seeded_session: object) -> None:
    await _make_graph(seeded_session)
    r = await api_client.get("/v1/relationships/graph?limit=300")  # type: ignore[attr-defined]
    assert r.status_code == 200
    body = r.json()
    assert "nodes" in body and "edges" in body
    node = body["nodes"][0]
    for key in ("id", "type", "label", "ref", "stale", "conflicted", "degree"):
        assert key in node
    if body["edges"]:
        edge = body["edges"][0]
        for key in ("id", "source", "target", "type", "weight"):
            assert key in edge


async def test_graph_stale_and_degree(api_client: object, seeded_session: object) -> None:
    _, service, doc_entity = await _make_graph(seeded_session)
    body = (await api_client.get("/v1/relationships/graph")).json()  # type: ignore[attr-defined]
    nodes = {n["id"]: n for n in body["nodes"]}
    # The doc entity links to a stale document.
    assert nodes[str(doc_entity.id)]["stale"] is True
    # Service is connected to two edges -> degree 2.
    assert nodes[str(service.id)]["degree"] == 2


async def test_graph_node_type_filter(api_client: object, seeded_session: object) -> None:
    await _make_graph(seeded_session)
    body = (
        await api_client.get("/v1/relationships/graph?node_types=repo")  # type: ignore[attr-defined]
    ).json()
    assert all(n["type"] == "repo" for n in body["nodes"])


async def test_path_found(api_client: object, seeded_session: object) -> None:
    repo, _, doc_entity = await _make_graph(seeded_session)
    r = await api_client.get(  # type: ignore[attr-defined]
        f"/v1/relationships/path?from_id={repo.id}&to_id={doc_entity.id}"
    )
    assert r.status_code == 200
    body = r.json()
    assert body["found"] is True
    assert len(body["path"]) == 3  # repo -> service -> doc
    assert body["path"][0]["edge"] is None  # first node has no incoming edge


async def test_path_not_found(api_client: object, seeded_session: object) -> None:
    repo, _, _ = await _make_graph(seeded_session)
    isolated = Entity(type=EntityType.api, name="orphan-api", external_ref=None)
    seeded_session.add(isolated)  # type: ignore[attr-defined]
    await seeded_session.flush()  # type: ignore[attr-defined]
    body = (
        await api_client.get(  # type: ignore[attr-defined]
            f"/v1/relationships/path?from_id={repo.id}&to_id={isolated.id}"
        )
    ).json()
    assert body["found"] is False
    assert body["path"] == []

"""Relationship graph endpoints: subgraph query and shortest-path BFS.

Nodes are entities. A node is ``stale`` if it links (via ``external_ref``) to a stale
document, and ``conflicted`` if that document participates in an open conflict. Edges
are only emitted between nodes present in the returned set.
"""

from __future__ import annotations

import uuid
from collections import defaultdict, deque

from fastapi import APIRouter, Query
from sqlalchemy import select

from context_engine.api.deps import SessionDep, UserDep
from context_engine.api.schemas import (
    GraphEdge,
    GraphNode,
    GraphResponse,
    PathResponse,
    PathStep,
)
from context_engine.storage.models import (
    Conflict,
    ConflictStatus,
    DocStatus,
    Document,
    Edge,
    Entity,
)

router = APIRouter(tags=["relationships"])

DEFAULT_LIMIT = 300


async def _stale_conflicted_refs(session: SessionDep) -> tuple[set[str], set[str]]:
    """Return (stale document-ref strings, conflicted document-ref strings)."""
    stale_ids = (
        (await session.execute(select(Document.id).where(Document.status == DocStatus.stale)))
        .scalars()
        .all()
    )
    stale_refs = {str(i) for i in stale_ids}

    conflicted_refs: set[str] = set()
    conflicts = (
        (
            await session.execute(
                select(Conflict.document_ids).where(Conflict.status == ConflictStatus.open)
            )
        )
        .scalars()
        .all()
    )
    for doc_ids in conflicts:
        conflicted_refs.update(doc_ids or [])
    return stale_refs, conflicted_refs


@router.get("/relationships/graph", response_model=GraphResponse)
async def graph(
    session: SessionDep,
    user: UserDep,
    node_types: str | None = None,
    edge_types: str | None = None,
    q: str | None = None,
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=2000),
) -> GraphResponse:
    node_type_filter = (
        {t.strip() for t in node_types.split(",") if t.strip()} if node_types else None
    )
    edge_type_filter = (
        {t.strip() for t in edge_types.split(",") if t.strip()} if edge_types else None
    )

    clauses = []
    if node_type_filter:
        clauses.append(Entity.type.in_(node_type_filter))
    if q:
        clauses.append(Entity.name.ilike(f"%{q}%"))

    entities = (
        (await session.execute(select(Entity).where(*clauses).order_by(Entity.name).limit(limit)))
        .scalars()
        .all()
    )
    node_ids = {e.id for e in entities}

    edge_clauses = [
        Edge.source_entity_id.in_(node_ids),
        Edge.target_entity_id.in_(node_ids),
    ]
    if edge_type_filter:
        edge_clauses.append(Edge.type.in_(edge_type_filter))
    edges = (
        (await session.execute(select(Edge).where(*edge_clauses))).scalars().all()
        if node_ids
        else []
    )

    degree: dict[uuid.UUID, int] = defaultdict(int)
    for edge in edges:
        degree[edge.source_entity_id] += 1
        degree[edge.target_entity_id] += 1

    stale_refs, conflicted_refs = await _stale_conflicted_refs(session)

    nodes = [
        GraphNode(
            id=str(e.id),
            type=e.type.value,
            label=e.name,
            ref=e.external_ref,
            stale=bool(e.external_ref and e.external_ref in stale_refs),
            conflicted=bool(e.external_ref and e.external_ref in conflicted_refs),
            degree=degree.get(e.id, 0),
        )
        for e in entities
    ]
    edge_out = [
        GraphEdge(
            id=str(edge.id),
            source=str(edge.source_entity_id),
            target=str(edge.target_entity_id),
            type=edge.type.value,
            weight=edge.weight,
        )
        for edge in edges
    ]
    return GraphResponse(nodes=nodes, edges=edge_out)


@router.get("/relationships/path", response_model=PathResponse)
async def path(
    session: SessionDep,
    user: UserDep,
    from_id: uuid.UUID,
    to_id: uuid.UUID,
) -> PathResponse:
    max_hops = 6

    all_edges = (await session.execute(select(Edge))).scalars().all()
    adjacency: dict[uuid.UUID, list[tuple[uuid.UUID, Edge]]] = defaultdict(list)
    for edge in all_edges:
        adjacency[edge.source_entity_id].append((edge.target_entity_id, edge))
        adjacency[edge.target_entity_id].append((edge.source_entity_id, edge))

    # BFS tracking the edge used to reach each node.
    prev: dict[uuid.UUID, tuple[uuid.UUID, Edge] | None] = {from_id: None}
    queue: deque[tuple[uuid.UUID, int]] = deque([(from_id, 0)])
    found = from_id == to_id
    while queue:
        current, depth = queue.popleft()
        if current == to_id:
            found = True
            break
        if depth >= max_hops:
            continue
        for neighbour, edge in adjacency.get(current, []):
            if neighbour not in prev:
                prev[neighbour] = (current, edge)
                queue.append((neighbour, depth + 1))

    if not found or to_id not in prev:
        return PathResponse(path=[], found=False)

    # Reconstruct node chain from to_id back to from_id.
    chain: list[tuple[uuid.UUID, Edge | None]] = []
    node = to_id
    while True:
        step = prev.get(node)
        if step is None:
            chain.append((node, None))
            break
        parent, edge = step
        chain.append((node, edge))
        node = parent
    chain.reverse()

    entity_ids = {nid for nid, _ in chain}
    entities = (
        (await session.execute(select(Entity).where(Entity.id.in_(entity_ids)))).scalars().all()
    )
    entity_map = {e.id: e for e in entities}
    stale_refs, conflicted_refs = await _stale_conflicted_refs(session)

    def _node(entity: Entity) -> GraphNode:
        return GraphNode(
            id=str(entity.id),
            type=entity.type.value,
            label=entity.name,
            ref=entity.external_ref,
            stale=bool(entity.external_ref and entity.external_ref in stale_refs),
            conflicted=bool(entity.external_ref and entity.external_ref in conflicted_refs),
            degree=0,
        )

    steps: list[PathStep] = []
    for nid, chain_edge in chain:
        entity = entity_map.get(nid)
        if entity is None:
            continue
        edge_out = (
            GraphEdge(
                id=str(chain_edge.id),
                source=str(chain_edge.source_entity_id),
                target=str(chain_edge.target_entity_id),
                type=chain_edge.type.value,
                weight=chain_edge.weight,
            )
            if chain_edge is not None
            else None
        )
        steps.append(PathStep(node=_node(entity), edge=edge_out))

    return PathResponse(path=steps, found=True)

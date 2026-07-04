"""GET /v1/context-debt — the 8-section organizational context-debt report.

Section notes:
- ``repeated_misses``: zero-result searches (``SearchEvent`` rows with
  ``result_count == 0``) grouped by lowercased query, most-frequent first (top 10).
- ``undocumented_apis``: ``api`` entities that have no outgoing/incoming ``documents`` edge.
"""

from __future__ import annotations

import uuid
from collections import Counter, defaultdict

from fastapi import APIRouter
from sqlalchemy import func, select

from context_engine.api.deps import SessionDep, UserDep
from context_engine.api.routes._common import team_name_map
from context_engine.api.schemas import (
    ConflictsBySourceTypeRow,
    ContextDebtReport,
    FailedAgentAreaRow,
    FrequentlyRejectedDocRow,
    MissingOwnerRow,
    NeverUsedDocRow,
    RepeatedMissRow,
    StaleDocsRow,
    UndocumentedApiRow,
)
from context_engine.storage.models import (
    AgentRun,
    AgentRunStatus,
    Conflict,
    DocStatus,
    Document,
    Edge,
    EdgeType,
    Entity,
    EntityType,
    SearchEvent,
    Source,
)

router = APIRouter(tags=["context-debt"])

NEVER_USED_CAP = 20
REJECTED_CAP = 20
REPEATED_MISS_CAP = 10


@router.get("/context-debt", response_model=ContextDebtReport)
async def context_debt(session: SessionDep, user: UserDep) -> ContextDebtReport:
    # 1. Stale docs grouped by repo/service/team.
    stale_rows = (
        await session.execute(
            select(
                Document.repo,
                Document.service,
                Document.team_id,
                func.count().label("count"),
            )
            .where(Document.status == DocStatus.stale)
            .group_by(Document.repo, Document.service, Document.team_id)
        )
    ).all()
    team_ids = {r.team_id for r in stale_rows if r.team_id}
    team_names = await team_name_map(session, team_ids)
    stale_docs = [
        StaleDocsRow(
            repo=r.repo,
            service=r.service,
            team_name=team_names.get(r.team_id) if r.team_id else None,
            count=int(r[3]),
        )
        for r in stale_rows
    ]

    # 2. Missing owners: repo/service keys with no team-owned documents.
    key_docs = (
        await session.execute(select(Document.repo, Document.service, Document.team_id))
    ).all()
    key_total: dict[str, int] = defaultdict(int)
    key_owned: dict[str, int] = defaultdict(int)
    for repo, service, team_id in key_docs:
        for key in {k for k in (repo, service) if k}:
            key_total[key] += 1
            if team_id is not None:
                key_owned[key] += 1
    missing_owners = [
        MissingOwnerRow(key=key, doc_count=key_total[key])
        for key in sorted(key_total)
        if key_owned[key] == 0
    ]

    # 3. Undocumented APIs: api entities without a 'documents' edge.
    api_entities = (
        (await session.execute(select(Entity).where(Entity.type == EntityType.api))).scalars().all()
    )
    documented_entity_ids: set[uuid.UUID] = set()
    if api_entities:
        doc_edges = (
            await session.execute(
                select(Edge.source_entity_id, Edge.target_entity_id).where(
                    Edge.type == EdgeType.documents
                )
            )
        ).all()
        for src, tgt in doc_edges:
            documented_entity_ids.add(src)
            documented_entity_ids.add(tgt)
    undocumented_apis = [
        UndocumentedApiRow(
            name=e.name,
            service=str((e.entity_metadata or {}).get("service", "")),
        )
        for e in api_entities
        if e.id not in documented_entity_ids
    ]

    # 4. Repeated misses: zero-result searches grouped by lowercased query (top 10).
    normalized_query = func.lower(SearchEvent.query)
    miss_rows = (
        await session.execute(
            select(normalized_query.label("query"), func.count().label("miss_count"))
            .where(SearchEvent.result_count == 0)
            .group_by(normalized_query)
            .order_by(func.count().desc())
            .limit(REPEATED_MISS_CAP)
        )
    ).all()
    repeated_misses = [RepeatedMissRow(query=r.query, count=int(r[1])) for r in miss_rows]

    # 5. Failed agent areas: failed/total per repo+service pair.
    run_rows = (
        await session.execute(select(AgentRun.repo, AgentRun.service, AgentRun.status))
    ).all()
    area_total: dict[tuple[str | None, str | None], int] = defaultdict(int)
    area_failed: dict[tuple[str | None, str | None], int] = defaultdict(int)
    for repo, service, run_status in run_rows:
        key = (repo, service)
        area_total[key] += 1
        if run_status == AgentRunStatus.failed:
            area_failed[key] += 1
    failed_agent_areas = [
        FailedAgentAreaRow(
            repo=repo,
            service=service,
            failed=area_failed[(repo, service)],
            total=total,
        )
        for (repo, service), total in sorted(
            area_total.items(), key=lambda kv: area_failed[kv[0]], reverse=True
        )
        if area_failed[(repo, service)] > 0
    ]

    # 6. Never-used docs (usage_count == 0).
    never_used_rows = (
        (
            await session.execute(
                select(Document)
                .where(Document.usage_count == 0)
                .order_by(Document.created_at.desc())
                .limit(NEVER_USED_CAP)
            )
        )
        .scalars()
        .all()
    )
    never_used_docs = [
        NeverUsedDocRow(
            id=str(d.id), title=d.title, doc_type=d.doc_type.value, created_at=d.created_at
        )
        for d in never_used_rows
    ]

    # 7. Frequently rejected docs (rejection_count > 0).
    rejected_rows = (
        (
            await session.execute(
                select(Document)
                .where(Document.rejection_count > 0)
                .order_by(Document.rejection_count.desc())
                .limit(REJECTED_CAP)
            )
        )
        .scalars()
        .all()
    )
    frequently_rejected_docs = [
        FrequentlyRejectedDocRow(id=str(d.id), title=d.title, rejection_count=d.rejection_count)
        for d in rejected_rows
    ]

    # 8. Conflicts by source type: count conflicts by the source types of their docs.
    conflicts = (await session.execute(select(Conflict))).scalars().all()
    doc_source_type: dict[str, str] = {}
    all_doc_ids: set[uuid.UUID] = set()
    for c in conflicts:
        for did in c.document_ids or []:
            try:
                all_doc_ids.add(uuid.UUID(did))
            except (ValueError, TypeError):
                continue
    if all_doc_ids:
        st_rows = (
            await session.execute(
                select(Document.id, Source.type)
                .join(Source, Document.source_id == Source.id)
                .where(Document.id.in_(all_doc_ids))
            )
        ).all()
        doc_source_type = {str(did): stype.value for did, stype in st_rows}
    source_type_counter: Counter[str] = Counter()
    for c in conflicts:
        seen: set[str] = set()
        for did in c.document_ids or []:
            stype = doc_source_type.get(did)
            if stype:
                seen.add(stype)
        for stype in seen:
            source_type_counter[stype] += 1
    conflicts_by_source_type = [
        ConflictsBySourceTypeRow(source_type=stype, count=count)
        for stype, count in source_type_counter.most_common()
    ]

    return ContextDebtReport(
        stale_docs=stale_docs,
        missing_owners=missing_owners,
        undocumented_apis=undocumented_apis,
        repeated_misses=repeated_misses,
        failed_agent_areas=failed_agent_areas,
        never_used_docs=never_used_docs,
        frequently_rejected_docs=frequently_rejected_docs,
        conflicts_by_source_type=conflicts_by_source_type,
    )

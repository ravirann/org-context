"""POST /v1/search — ACL-filtered hybrid retrieval."""

from __future__ import annotations

from fastapi import APIRouter

from context_engine.api.deps import SessionDep, UserDep
from context_engine.api.schemas import SearchRequest, SearchResponse, SearchResult
from context_engine.retrieval.service import SearchFilters, search_chunks

router = APIRouter(tags=["search"])


@router.post("/search", response_model=SearchResponse)
async def search(body: SearchRequest, session: SessionDep, user: UserDep) -> SearchResponse:
    filters = SearchFilters(
        doc_types=body.doc_types,
        source_ids=body.source_ids,
        repo=body.repo,
        service=body.service,
        status=body.status,
        page=body.page,
        page_size=body.page_size,
    )
    result = await search_chunks(session, user, body.query, filters)
    items = [
        SearchResult(
            document_id=hit.document_id,
            chunk_id=hit.chunk_id,
            title=hit.title,
            doc_type=hit.doc_type,
            source_name=hit.source_name,
            snippet=hit.snippet,
            score=hit.score,
            url=hit.url,
            repo=hit.repo,
            service=hit.service,
            status=hit.status,
            freshness_score=hit.freshness_score,
            authority_score=hit.authority_score,
            last_activity_at=hit.last_activity_at,
        )
        for hit in result.items
    ]
    return SearchResponse(
        items=items,
        total=result.total,
        page=body.page,
        page_size=body.page_size,
        acl_blocked_count=result.acl_blocked_count,
    )

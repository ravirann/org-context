"""MCP server exposing context-engine tools to coding agents.

Transport-agnostic: ``main()`` runs stdio by default, or streamable-http on
:8765 when ``http=True``. Every tool resolves the acting user once per call
from the ``CE_MCP_TOKEN`` env var (default ``demo-mcp-token``, a ``kind=mcp``
API key created by the seed data) via
``context_engine.storage.repositories.get_user_by_api_key``, then opens its
own session via ``session_scope()``. All ACL enforcement is delegated to the
underlying retrieval/compiler/repository functions — this module never
bypasses it.
"""

from __future__ import annotations

import json
import os
import uuid

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from context_engine.context_compiler.compiler import compile_context as compile_context_service
from context_engine.observability.logging import get_logger
from context_engine.retrieval.service import SearchFilters, search_chunks
from context_engine.storage.db import session_scope
from context_engine.storage.models import Document, Feedback, FeedbackType, User
from context_engine.storage.repositories import acl_filter_clause, get_user_by_api_key

logger = get_logger(__name__)

MCP_TOKEN_ENV = "CE_MCP_TOKEN"
DEFAULT_MCP_TOKEN = "demo-mcp-token"
DEFAULT_HTTP_PORT = 8765

mcp = FastMCP("org-context")


async def _resolve_user(session: AsyncSession) -> User:
    """Resolve the acting user from ``CE_MCP_TOKEN``, raising ``ToolError`` if invalid."""
    raw_key = os.environ.get(MCP_TOKEN_ENV, DEFAULT_MCP_TOKEN)
    user = await get_user_by_api_key(session, raw_key)
    if user is None:
        raise ToolError("invalid or inactive CE_MCP_TOKEN")
    return user


@mcp.tool()
async def compile_context(
    task: str,
    repo: str | None = None,
    service: str | None = None,
    max_tokens: int | None = None,
) -> str:
    """Compile a decision-grade, ACL-enforced, source-backed context packet for a task.

    Runs intent classification, hybrid retrieval, conflict resolution and token
    budgeting, then returns the full packet as a JSON string with fields: id,
    intent, compiled_context, selected_sources, rejected_sources, citations,
    conflict_notes, acl_notes, token_estimate, confidence_score, risks,
    recommended_tests. Use this before starting an engineering task to get
    grounded context instead of guessing.
    """
    async with session_scope() as session:
        user = await _resolve_user(session)
        packet = await compile_context_service(
            session, user, task, repo=repo, service=service, max_tokens=max_tokens
        )
        payload = {
            "id": str(packet.id),
            "intent": packet.intent.value,
            "compiled_context": packet.compiled_context,
            "selected_sources": packet.selected_sources,
            "rejected_sources": packet.rejected_sources,
            "citations": packet.citations,
            "conflict_notes": packet.conflict_notes,
            "acl_notes": packet.acl_notes,
            "token_estimate": packet.token_estimate,
            "confidence_score": packet.confidence_score,
            "risks": packet.risks,
            "recommended_tests": packet.recommended_tests,
        }
        return json.dumps(payload)


@mcp.tool()
async def search_context(
    query: str,
    repo: str | None = None,
    service: str | None = None,
) -> str:
    """Search the org's ingested engineering knowledge (code, PRs, tickets, docs, ADRs, incidents).

    ACL-enforced hybrid (vector + full-text + freshness + authority) search.
    Returns a JSON string: a list of hits (document_id, title, doc_type,
    snippet, score, url) plus acl_blocked_count (documents that matched but
    were hidden from the caller by access control — never their content).
    """
    async with session_scope() as session:
        user = await _resolve_user(session)
        page = await search_chunks(session, user, query, SearchFilters(repo=repo, service=service))
        payload = {
            "hits": [
                {
                    "document_id": hit.document_id,
                    "title": hit.title,
                    "doc_type": hit.doc_type,
                    "snippet": hit.snippet,
                    "score": hit.score,
                    "url": hit.url,
                }
                for hit in page.items
            ],
            "acl_blocked_count": page.acl_blocked_count,
        }
        return json.dumps(payload)


@mcp.tool()
async def get_document(document_id: str) -> str:
    """Fetch a single document by id, enforcing ACL for the calling user.

    Returns a JSON string with title, content, doc_type, url, status,
    freshness_score and authority_score. If the document does not exist or is
    not accessible to the caller, returns {"error": "not found or not
    accessible"} (a 404-shaped response, never leaking existence).
    """
    async with session_scope() as session:
        user = await _resolve_user(session)
        try:
            doc_uuid = uuid.UUID(document_id)
        except ValueError:
            return json.dumps({"error": "not found or not accessible"})

        stmt = select(Document).where(Document.id == doc_uuid, acl_filter_clause(user))
        document = (await session.execute(stmt)).scalar_one_or_none()
        if document is None:
            return json.dumps({"error": "not found or not accessible"})

        payload = {
            "title": document.title,
            "content": document.content,
            "doc_type": document.doc_type.value,
            "url": document.url,
            "status": document.status.value,
            "freshness_score": document.freshness_score,
            "authority_score": document.authority_score,
        }
        return json.dumps(payload)


@mcp.tool()
async def report_feedback(
    type: str,
    context_packet_id: str | None = None,
    document_id: str | None = None,
    comment: str | None = None,
) -> str:
    """Record feedback on a context packet or document (e.g. useful, stale_context).

    ``type`` must be one of the FeedbackType enum values. At least one of
    context_packet_id or document_id must be supplied. Returns a JSON string
    {"status": "recorded", "id": <feedback id>} on success, or
    {"error": ...} for invalid input.
    """
    valid_types = {member.value for member in FeedbackType}
    if type not in valid_types:
        return json.dumps({"error": f"invalid feedback type '{type}'"})
    if context_packet_id is None and document_id is None:
        return json.dumps({"error": "at least one of context_packet_id or document_id is required"})

    async with session_scope() as session:
        user = await _resolve_user(session)
        try:
            packet_uuid = uuid.UUID(context_packet_id) if context_packet_id else None
            doc_uuid = uuid.UUID(document_id) if document_id else None
        except ValueError:
            return json.dumps({"error": "invalid uuid"})

        feedback = Feedback(
            user_id=user.id,
            context_packet_id=packet_uuid,
            document_id=doc_uuid,
            type=FeedbackType(type),
            comment=comment,
        )
        session.add(feedback)
        await session.flush()
        return json.dumps({"status": "recorded", "id": str(feedback.id)})


def main(http: bool = False) -> None:
    """Run the MCP server: stdio by default, streamable-http on :8765 if ``http``."""
    if http:
        mcp.settings.host = "0.0.0.0"
        mcp.settings.port = DEFAULT_HTTP_PORT
        logger.info("mcp_server_start", transport="streamable-http", port=DEFAULT_HTTP_PORT)
        mcp.run(transport="streamable-http")
    else:
        logger.info("mcp_server_start", transport="stdio")
        mcp.run(transport="stdio")

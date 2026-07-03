"""Integration tests for the MCP server tools (real seeded db, monkeypatched session_scope)."""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from context_engine.mcp_server import server as mcp_server
from context_engine.storage.models import Document, User

MCP_TOKEN = "demo-mcp-token"


@pytest.fixture(autouse=True)
def _mcp_token_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CE_MCP_TOKEN", MCP_TOKEN)


@pytest.fixture(autouse=True)
def _patch_session_scope(monkeypatch: pytest.MonkeyPatch, seeded_session: AsyncSession) -> None:
    @asynccontextmanager
    async def _scope() -> AsyncIterator[AsyncSession]:
        yield seeded_session

    monkeypatch.setattr(mcp_server, "session_scope", _scope)


async def get_user(session: AsyncSession, email: str) -> User:
    return (await session.execute(select(User).where(User.email == email))).scalar_one()


# ---------------------------------------------------------------------------
# Tool registration
# ---------------------------------------------------------------------------


async def test_tools_are_registered_with_docstrings() -> None:
    tools = await mcp_server.mcp.list_tools()
    names = {tool.name for tool in tools}
    assert names == {"compile_context", "search_context", "get_document", "report_feedback"}
    for tool in tools:
        assert tool.description, f"{tool.name} must have a docstring"


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


async def test_invalid_token_raises_tool_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CE_MCP_TOKEN", "not-a-real-token")
    from mcp.server.fastmcp.exceptions import ToolError

    with pytest.raises(ToolError):
        await mcp_server.search_context("payments retries")


# ---------------------------------------------------------------------------
# compile_context
# ---------------------------------------------------------------------------


async def test_compile_context_returns_parseable_packet() -> None:
    raw = await mcp_server.compile_context("fix the payments retry bug")
    payload = json.loads(raw)
    assert uuid.UUID(payload["id"])
    assert payload["intent"]
    assert "compiled_context" in payload and payload["compiled_context"]
    assert isinstance(payload["citations"], list)
    assert isinstance(payload["selected_sources"], list)
    assert "token_estimate" in payload
    assert "confidence_score" in payload


# ---------------------------------------------------------------------------
# search_context
# ---------------------------------------------------------------------------


async def test_search_context_finds_seeded_docs() -> None:
    raw = await mcp_server.search_context("idempotency and webhooks")
    payload = json.loads(raw)
    titles = [hit["title"] for hit in payload["hits"]]
    assert any("idempotency" in title.lower() for title in titles)


async def test_search_context_respects_acl_for_mcp_user(
    seeded_session: AsyncSession,
) -> None:
    # The mcp demo key resolves to the admin user, who can see the admin-only secret doc.
    raw = await mcp_server.search_context("credentials rotation plan")
    payload = json.loads(raw)
    titles = [hit["title"] for hit in payload["hits"]]
    assert any("Secret infra credentials rotation plan" in title for title in titles)
    assert payload["acl_blocked_count"] == 0


# ---------------------------------------------------------------------------
# get_document
# ---------------------------------------------------------------------------


async def test_get_document_returns_full_document(seeded_session: AsyncSession) -> None:
    doc = (
        (
            await seeded_session.execute(
                select(Document).where(Document.title.ilike("%idempotency and webhooks%"))
            )
        )
        .scalars()
        .first()
    )
    assert doc is not None

    raw = await mcp_server.get_document(str(doc.id))
    payload = json.loads(raw)
    assert payload["title"] == doc.title
    assert payload["content"] == doc.content
    assert payload["doc_type"] == doc.doc_type.value
    assert "freshness_score" in payload
    assert "authority_score" in payload


async def test_get_document_unknown_id_is_error(seeded_session: AsyncSession) -> None:
    raw = await mcp_server.get_document(str(uuid.uuid4()))
    payload = json.loads(raw)
    assert payload == {"error": "not found or not accessible"}


async def test_get_document_hidden_doc_errors_for_non_privileged_user(
    monkeypatch: pytest.MonkeyPatch, seeded_session: AsyncSession
) -> None:
    # Resolve the acting user to the non-admin engineer instead of the mcp token's
    # admin, to exercise ACL enforcement for a non-privileged caller.
    engineer = await get_user(seeded_session, "jade@demo.dev")

    async def _fake_resolve_user(_session: AsyncSession) -> User:
        return engineer

    monkeypatch.setattr(mcp_server, "_resolve_user", _fake_resolve_user)

    secret_doc = (
        (
            await seeded_session.execute(
                select(Document).where(Document.title == "Secret infra credentials rotation plan")
            )
        )
        .scalars()
        .first()
    )
    assert secret_doc is not None

    raw = await mcp_server.get_document(str(secret_doc.id))
    payload = json.loads(raw)
    assert payload == {"error": "not found or not accessible"}


# ---------------------------------------------------------------------------
# report_feedback
# ---------------------------------------------------------------------------


async def test_report_feedback_creates_row(seeded_session: AsyncSession) -> None:
    doc = (
        (
            await seeded_session.execute(
                select(Document).where(Document.title.ilike("%idempotency and webhooks%"))
            )
        )
        .scalars()
        .first()
    )
    assert doc is not None

    raw = await mcp_server.report_feedback(
        type="useful", document_id=str(doc.id), comment="Helped a lot."
    )
    payload = json.loads(raw)
    assert payload["status"] == "recorded"
    assert uuid.UUID(payload["id"])

    from context_engine.storage.models import Feedback

    row = await seeded_session.get(Feedback, uuid.UUID(payload["id"]))
    assert row is not None
    assert row.type.value == "useful"
    assert row.document_id == doc.id
    assert row.comment == "Helped a lot."


async def test_report_feedback_invalid_type_is_error() -> None:
    raw = await mcp_server.report_feedback(type="not-a-real-type", document_id=str(uuid.uuid4()))
    payload = json.loads(raw)
    assert "error" in payload


async def test_report_feedback_requires_a_target() -> None:
    raw = await mcp_server.report_feedback(type="useful")
    payload = json.loads(raw)
    assert "error" in payload

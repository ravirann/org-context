"""Integration tests for the ``ctx`` CLI against a seeded Postgres database.

``cli.main._run`` wraps every command body in ``asyncio.run(...)``, which is
correct for the real CLI (one fresh loop per invocation) but would fight the
session-scoped event loop that the ``seeded_session`` fixture chain (and its
asyncpg connection) is already bound to. Tests therefore patch ``_run`` to
execute on that same loop via ``run_until_complete`` instead of spinning up a
new one — behaviorally equivalent, just loop-reuse-safe for the test process.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncIterator, Coroutine
from contextlib import asynccontextmanager
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typer.testing import CliRunner

from context_engine.cli import main as cli_main
from context_engine.storage import models as m

runner = CliRunner()


def _run_on_current_loop(coro: Coroutine[Any, Any, Any]) -> Any:
    return asyncio.get_event_loop().run_until_complete(coro)


async def _get_doc_by_title_prefix(session: AsyncSession, prefix: str) -> m.Document:
    stmt = select(m.Document).where(m.Document.title.startswith(prefix))
    return (await session.execute(stmt)).scalars().first() or pytest.fail(
        f"seed document {prefix!r} not found"
    )


async def _create_golden_tasks(session: AsyncSession) -> list[m.EvalTask]:
    adr = await _get_doc_by_title_prefix(session, "ADR-0042")
    guide = await _get_doc_by_title_prefix(session, "Payments guide 1")
    tasks = [
        m.EvalTask(
            name="it-retry-policy",
            task="What backoff do payment charge retries use?",
            repo="payments-api",
            service="payments-api",
            expected_document_ids=[str(adr.id)],
            expected_keywords=["exponential", "backoff", "jitter"],
            is_active=True,
        ),
        m.EvalTask(
            name="it-idempotency",
            task="How does the charge endpoint validate idempotency keys?",
            repo="payments-api",
            service="payments-api",
            expected_document_ids=[str(guide.id)],
            expected_keywords=["idempotency", "event_id"],
            is_active=True,
        ),
    ]
    session.add_all(tasks)
    await session.flush()
    return tasks


@pytest.fixture
def _patch_session_scope(
    monkeypatch: pytest.MonkeyPatch, seeded_session: AsyncSession
) -> AsyncSession:
    @asynccontextmanager
    async def _scope() -> AsyncIterator[AsyncSession]:
        yield seeded_session

    monkeypatch.setattr(cli_main, "session_scope", _scope)
    monkeypatch.setattr(cli_main, "_run", _run_on_current_loop)
    return seeded_session


@pytest.fixture
async def _with_golden_tasks(_patch_session_scope: AsyncSession) -> None:
    await _create_golden_tasks(_patch_session_scope)


def test_ctx_search_against_seeded_db(_patch_session_scope: AsyncSession) -> None:
    result = runner.invoke(cli_main.app, ["search", "idempotency webhooks", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["total"] >= 1
    assert any("idempotency" in item["title"].lower() for item in payload["items"])


def test_ctx_search_plain_text(_patch_session_scope: AsyncSession) -> None:
    result = runner.invoke(cli_main.app, ["search", "idempotency webhooks"])

    assert result.exit_code == 0
    assert "result(s)" in result.output
    assert "blocked by ACL" in result.output


def test_ctx_compile_json_against_seeded_db(_patch_session_scope: AsyncSession) -> None:
    result = runner.invoke(cli_main.app, ["compile", "fix the payments retry bug", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert uuid.UUID(payload["id"])
    assert payload["compiled_context"]
    assert isinstance(payload["citations"], list)


def test_ctx_compile_plain_against_seeded_db(_patch_session_scope: AsyncSession) -> None:
    result = runner.invoke(cli_main.app, ["compile", "fix the payments retry bug"])

    assert result.exit_code == 0
    assert "Packet " in result.output
    assert "token_estimate=" in result.output


def test_ctx_eval_run_baseline_against_seeded_db(
    _patch_session_scope: AsyncSession,
    _with_golden_tasks: None,
) -> None:
    result = runner.invoke(cli_main.app, ["eval", "run", "--mode", "baseline"])

    assert result.exit_code == 0
    assert "it-retry-policy" in result.output
    assert "it-idempotency" in result.output
    assert "Summary:" in result.output


def test_ctx_search_invalid_api_key(_patch_session_scope: AsyncSession) -> None:
    result = runner.invoke(cli_main.app, ["search", "anything", "--api-key", "totally-bogus-key"])

    assert result.exit_code != 0
    assert "invalid or inactive api key" in result.output

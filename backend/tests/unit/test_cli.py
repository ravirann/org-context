"""Unit tests for the ``ctx`` Typer CLI (no database; everything monkeypatched)."""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock

import pytest
from typer.testing import CliRunner

from context_engine.cli import main as cli_main
from context_engine.storage.models import (
    EvalMode,
    EvalResult,
    EvalRun,
    EvalRunStatus,
    UserRole,
)

runner = CliRunner()


class _FakeUser:
    def __init__(self, user_id: uuid.UUID | None = None, role: UserRole = UserRole.admin) -> None:
        self.id = user_id or uuid.uuid4()
        self.role = role
        self.email = "admin@demo.dev"
        self.name = "Ava Admin"


@asynccontextmanager
async def _fake_session_scope() -> AsyncIterator[object]:
    yield object()


def _patch_session_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli_main, "session_scope", _fake_session_scope)


# ---------------------------------------------------------------------------
# Help / smoke
# ---------------------------------------------------------------------------


def test_help_renders_all_commands() -> None:
    result = runner.invoke(cli_main.app, ["--help"])
    assert result.exit_code == 0
    for command in ("seed", "sync", "search", "compile", "eval", "serve-api", "serve-mcp"):
        assert command in result.output


def test_eval_help_renders_subcommands() -> None:
    result = runner.invoke(cli_main.app, ["eval", "--help"])
    assert result.exit_code == 0
    assert "run" in result.output
    assert "report" in result.output


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------


def test_search_invalid_api_key_exits_nonzero(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_session_scope(monkeypatch)
    monkeypatch.setattr(cli_main, "get_user_by_api_key", AsyncMock(return_value=None))

    result = runner.invoke(cli_main.app, ["search", "payments retries", "--api-key", "bad-key"])

    assert result.exit_code != 0
    assert "invalid or inactive api key" in result.output


def test_search_plain_output(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_session_scope(monkeypatch)
    monkeypatch.setattr(cli_main, "get_user_by_api_key", AsyncMock(return_value=_FakeUser()))

    from context_engine.retrieval.service import SearchHit, SearchPage

    hit = SearchHit(
        document_id=str(uuid.uuid4()),
        chunk_id=str(uuid.uuid4()),
        title="Payments retry policy",
        doc_type="doc",
        source_name="Confluence",
        snippet="Retries use exponential backoff...",
        score=0.87,
        url="https://example.com/doc/1",
        repo="payments-api",
        service="payments",
        status="active",
        freshness_score=0.9,
        authority_score=0.8,
        last_activity_at=__import__("datetime").datetime.now(__import__("datetime").UTC),
    )
    page = SearchPage(items=[hit], total=1, acl_blocked_count=2)

    fake_search_chunks = AsyncMock(return_value=page)
    monkeypatch.setattr("context_engine.retrieval.service.search_chunks", fake_search_chunks)

    result = runner.invoke(cli_main.app, ["search", "retry policy"])

    assert result.exit_code == 0
    assert "Payments retry policy" in result.output
    assert "0.870" in result.output
    assert "1 result(s), 2 blocked by ACL." in result.output


def test_search_json_output(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_session_scope(monkeypatch)
    monkeypatch.setattr(cli_main, "get_user_by_api_key", AsyncMock(return_value=_FakeUser()))

    from context_engine.retrieval.service import SearchHit, SearchPage

    hit = SearchHit(
        document_id=str(uuid.uuid4()),
        chunk_id=str(uuid.uuid4()),
        title="Payments retry policy",
        doc_type="doc",
        source_name="Confluence",
        snippet="Retries use exponential backoff...",
        score=0.87,
        url="https://example.com/doc/1",
        repo="payments-api",
        service="payments",
        status="active",
        freshness_score=0.9,
        authority_score=0.8,
        last_activity_at=__import__("datetime").datetime.now(__import__("datetime").UTC),
    )
    page = SearchPage(items=[hit], total=1, acl_blocked_count=0)
    monkeypatch.setattr(
        "context_engine.retrieval.service.search_chunks", AsyncMock(return_value=page)
    )

    result = runner.invoke(cli_main.app, ["search", "retry policy", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["total"] == 1
    assert payload["items"][0]["title"] == "Payments retry policy"
    assert payload["acl_blocked_count"] == 0


# ---------------------------------------------------------------------------
# compile
# ---------------------------------------------------------------------------


class _FakePacket:
    def __init__(self) -> None:
        self.id = uuid.uuid4()

        class _Intent:
            value = "bugfix"

        self.intent = _Intent()
        self.compiled_context = "# Task: fix the retry bug\n\nSome context body."
        self.selected_sources: list[dict[str, Any]] = [
            {"document_id": str(uuid.uuid4()), "title": "Doc A", "doc_type": "doc", "score": 0.9}
        ]
        self.rejected_sources: list[dict[str, Any]] = []
        self.citations: list[dict[str, Any]] = [
            {"marker": "S1", "title": "Doc A", "url": "https://example.com/a", "quote": "..."}
        ]
        self.conflict_notes: list[dict[str, Any]] = []
        self.acl_notes: dict[str, Any] = {"blocked_count": 0, "note": "No documents were blocked"}
        self.token_estimate = 123
        self.confidence_score = 0.75
        self.freshness_score = 0.6
        self.authority_score = 0.8
        self.risks: list[str] = []
        self.recommended_tests: list[str] = ["Write a regression test."]


def test_compile_invalid_api_key_exits_nonzero(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_session_scope(monkeypatch)
    monkeypatch.setattr(cli_main, "get_user_by_api_key", AsyncMock(return_value=None))

    result = runner.invoke(cli_main.app, ["compile", "fix the retry bug", "--api-key", "bad-key"])

    assert result.exit_code != 0
    assert "invalid or inactive api key" in result.output


def test_compile_plain_output(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_session_scope(monkeypatch)
    monkeypatch.setattr(cli_main, "get_user_by_api_key", AsyncMock(return_value=_FakeUser()))

    packet = _FakePacket()
    monkeypatch.setattr(
        "context_engine.context_compiler.compiler.compile_context",
        AsyncMock(return_value=packet),
    )

    result = runner.invoke(cli_main.app, ["compile", "fix the retry bug"])

    assert result.exit_code == 0
    assert str(packet.id) in result.output
    assert "Some context body." in result.output
    assert "[S1] Doc A" in result.output
    assert "confidence=0.75" in result.output


def test_compile_json_output(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_session_scope(monkeypatch)
    monkeypatch.setattr(cli_main, "get_user_by_api_key", AsyncMock(return_value=_FakeUser()))

    packet = _FakePacket()
    monkeypatch.setattr(
        "context_engine.context_compiler.compiler.compile_context",
        AsyncMock(return_value=packet),
    )

    result = runner.invoke(cli_main.app, ["compile", "fix the retry bug", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["id"] == str(packet.id)
    assert payload["intent"] == "bugfix"
    assert payload["token_estimate"] == 123


# ---------------------------------------------------------------------------
# eval run / report
# ---------------------------------------------------------------------------


def test_eval_run_invalid_api_key_exits_nonzero(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_session_scope(monkeypatch)
    monkeypatch.setattr(cli_main, "get_user_by_api_key", AsyncMock(return_value=None))

    result = runner.invoke(cli_main.app, ["eval", "run", "--api-key", "bad-key"])

    assert result.exit_code != 0
    assert "invalid or inactive api key" in result.output


def test_eval_run_baseline_prints_report(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_session_scope(monkeypatch)
    monkeypatch.setattr(cli_main, "get_user_by_api_key", AsyncMock(return_value=_FakeUser()))

    eval_run_row = EvalRun(
        id=uuid.uuid4(), mode=EvalMode.baseline, status=EvalRunStatus.completed, summary={}
    )
    monkeypatch.setattr(
        "context_engine.evals.harness.run_eval", AsyncMock(return_value=eval_run_row)
    )

    class _Result:
        def scalars(self) -> Any:
            class _Scalars:
                def all(self) -> list[EvalResult]:
                    return []

            return _Scalars()

    fake_session = AsyncMock()
    fake_session.execute = AsyncMock(return_value=_Result())

    @asynccontextmanager
    async def _scope() -> AsyncIterator[object]:
        yield fake_session

    monkeypatch.setattr(cli_main, "session_scope", _scope)
    monkeypatch.setattr(
        "context_engine.evals.report.format_report",
        lambda run, results: f"REPORT for run {run.id} mode={run.mode.value}",
    )

    result = runner.invoke(cli_main.app, ["eval", "run", "--mode", "baseline"])

    assert result.exit_code == 0
    assert f"REPORT for run {eval_run_row.id} mode=baseline" in result.output


def test_eval_report_no_matching_run_exits_nonzero(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_session = AsyncMock()

    class _Result:
        def scalar_one_or_none(self) -> None:
            return None

    fake_session.execute = AsyncMock(return_value=_Result())

    @asynccontextmanager
    async def _scope() -> AsyncIterator[object]:
        yield fake_session

    monkeypatch.setattr(cli_main, "session_scope", _scope)

    result = runner.invoke(cli_main.app, ["eval", "report"])

    assert result.exit_code != 0
    assert "no matching eval run found" in result.output


# ---------------------------------------------------------------------------
# serve-api / serve-mcp
# ---------------------------------------------------------------------------


def test_serve_mcp_delegates_to_mcp_server_main(monkeypatch: pytest.MonkeyPatch) -> None:
    called: dict[str, bool] = {}

    def _fake_main(http: bool = False) -> None:
        called["http"] = http

    monkeypatch.setattr("context_engine.mcp_server.server.main", _fake_main)

    result = runner.invoke(cli_main.app, ["serve-mcp", "--http"])

    assert result.exit_code == 0
    assert called == {"http": True}


def test_serve_api_missing_api_package_errors_cleanly(monkeypatch: pytest.MonkeyPatch) -> None:
    import builtins

    real_import = builtins.__import__

    def _fake_import(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "context_engine.api.app":
            raise ImportError("no api yet")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _fake_import)

    result = runner.invoke(cli_main.app, ["serve-api"])

    assert result.exit_code != 0
    assert "context_engine.api.app is not available" in result.output

"""``ctx`` Typer CLI — admin-facing operations for the context engine.

Plain-text output (no rich formatting) via ``typer.echo``. The acting user is
resolved once per invocation from ``--api-key`` (default ``demo-admin-key``)
via ``context_engine.storage.repositories.get_user_by_api_key``.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from collections.abc import Coroutine
from typing import Annotated, Any

import structlog
import typer
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from context_engine.observability import logging as ce_logging
from context_engine.storage.db import session_scope
from context_engine.storage.models import EvalMode, EvalResult, EvalRun, EvalRunStatus, Source
from context_engine.storage.repositories import get_user_by_api_key


def _configure_cli_logging() -> None:
    """Route structlog output to stderr so ``--json`` stdout stays parseable.

    ``context_engine.observability.logging.configure_logging`` is idempotent
    and otherwise binds the logger factory to stdout on first use by any
    module (e.g. the compiler). Configuring here first — before any service
    import runs — wins that race and keeps CLI stdout clean for JSON output.
    """
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        logger_factory=structlog.PrintLoggerFactory(sys.stderr),
        cache_logger_on_first_use=True,
    )
    ce_logging._configured = True


_configure_cli_logging()

app = typer.Typer(no_args_is_help=True, add_completion=False)
eval_app = typer.Typer(no_args_is_help=True, help="Run and inspect eval runs.")
app.add_typer(eval_app, name="eval")

DEFAULT_API_KEY = "demo-admin-key"


def app_entry() -> None:
    """Console-script entrypoint (``ctx``)."""
    app()


def _run[T](coro: Coroutine[Any, Any, T]) -> T:
    """Run an async coroutine to completion (thin wrapper around asyncio.run)."""
    return asyncio.run(coro)


ApiKeyOption = Annotated[str, typer.Option("--api-key", help="API key of the acting user.")]


@app.command()
def seed(
    reset: Annotated[bool, typer.Option("--reset", help="Truncate all tables before seeding.")] = (
        False
    ),
    if_empty: Annotated[
        bool, typer.Option("--if-empty", help="Only seed if the database is currently empty.")
    ] = False,
) -> None:
    """Seed the demo organization dataset."""
    from seeds.demo_data import seed_demo

    counts = _run(seed_demo(reset=reset, if_empty=if_empty))
    if not counts:
        typer.echo("Seed skipped (database not empty).")
        return
    typer.echo("Seeded:")
    for table, count in counts.items():
        typer.echo(f"  {table}: {count}")


@app.command()
def sync(
    source_name: Annotated[str | None, typer.Argument(help="Name of the source to sync.")] = None,
    all_sources: Annotated[bool, typer.Option("--all", help="Sync every enabled source.")] = False,
) -> None:
    """Sync one named source, or every enabled source with --all."""
    if not all_sources and not source_name:
        typer.echo("Error: pass a source name or --all.", err=True)
        raise typer.Exit(code=1)

    async def _do() -> None:
        from context_engine.ingestion.pipeline import sync_all, sync_source

        async with session_scope() as session:
            if all_sources:
                results = await sync_all(session)
                for name, count in results.items():
                    typer.echo(f"{name}: {count} document(s) synced")
                return
            assert source_name is not None
            stmt = select(Source).where(Source.name == source_name)
            source = (await session.execute(stmt)).scalar_one_or_none()
            if source is None:
                typer.echo(f"Error: no source named {source_name!r}", err=True)
                raise typer.Exit(code=1)
            count = await sync_source(session, source)
            typer.echo(f"{source.name}: {count} document(s) synced")

    _run(_do())


@app.command()
def search(
    query: Annotated[str, typer.Argument(help="Search query text.")],
    repo: Annotated[str | None, typer.Option("--repo", help="Filter by repo.")] = None,
    service: Annotated[str | None, typer.Option("--service", help="Filter by service.")] = None,
    as_json: Annotated[bool, typer.Option("--json", help="Print raw JSON output.")] = False,
    api_key: ApiKeyOption = DEFAULT_API_KEY,
) -> None:
    """Search ingested context (ACL-enforced as the acting user)."""

    async def _do() -> None:
        from context_engine.retrieval.service import SearchFilters, search_chunks

        async with session_scope() as session:
            user = await get_user_by_api_key(session, api_key)
            if user is None:
                typer.echo(f"Error: invalid or inactive api key: {api_key!r}", err=True)
                raise typer.Exit(code=1)
            page = await search_chunks(
                session, user, query, SearchFilters(repo=repo, service=service)
            )

        if as_json:
            payload = {
                "items": [
                    {
                        "document_id": hit.document_id,
                        "title": hit.title,
                        "doc_type": hit.doc_type,
                        "score": hit.score,
                        "url": hit.url,
                        "snippet": hit.snippet,
                    }
                    for hit in page.items
                ],
                "total": page.total,
                "acl_blocked_count": page.acl_blocked_count,
            }
            typer.echo(json.dumps(payload))
            return

        if not page.items:
            typer.echo("No results.")
        for hit in page.items:
            typer.echo(f"{hit.score:.3f}  {hit.title}  [{hit.doc_type}]  {hit.url}")
        typer.echo(f"\n{page.total} result(s), {page.acl_blocked_count} blocked by ACL.")

    _run(_do())


@app.command()
def compile(
    task: Annotated[str, typer.Argument(help="Task description to compile context for.")],
    repo: Annotated[str | None, typer.Option("--repo", help="Filter by repo.")] = None,
    service: Annotated[str | None, typer.Option("--service", help="Filter by service.")] = None,
    max_tokens: Annotated[
        int | None, typer.Option("--max-tokens", help="Override the token budget.")
    ] = None,
    as_json: Annotated[bool, typer.Option("--json", help="Print the full packet as JSON.")] = False,
    api_key: ApiKeyOption = DEFAULT_API_KEY,
) -> None:
    """Compile a decision-grade context packet for a task."""

    async def _do() -> None:
        from context_engine.context_compiler.compiler import compile_context as compile_service

        async with session_scope() as session:
            user = await get_user_by_api_key(session, api_key)
            if user is None:
                typer.echo(f"Error: invalid or inactive api key: {api_key!r}", err=True)
                raise typer.Exit(code=1)
            packet = await compile_service(
                session, user, task, repo=repo, service=service, max_tokens=max_tokens
            )

            if as_json:
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
                typer.echo(json.dumps(payload))
                return

            typer.echo(f"Packet {packet.id} (intent={packet.intent.value})")
            typer.echo("")
            typer.echo(packet.compiled_context)
            typer.echo("Citations:")
            for citation in packet.citations:
                typer.echo(f"  [{citation['marker']}] {citation['title']} — {citation['url']}")
            typer.echo("")
            typer.echo(
                f"token_estimate={packet.token_estimate} "
                f"confidence={packet.confidence_score:.2f} "
                f"freshness={packet.freshness_score:.2f} "
                f"authority={packet.authority_score:.2f}"
            )

    _run(_do())


@eval_app.command("run")
def eval_run(
    mode: Annotated[
        EvalMode, typer.Option("--mode", help="Eval mode to run.")
    ] = EvalMode.comparison,
    api_key: ApiKeyOption = DEFAULT_API_KEY,
) -> None:
    """Run the golden-task eval harness and print the resulting report."""

    async def _do() -> None:
        from context_engine.evals.harness import run_eval
        from context_engine.evals.report import format_report

        async with session_scope() as session:
            user = await get_user_by_api_key(session, api_key)
            if user is None:
                typer.echo(f"Error: invalid or inactive api key: {api_key!r}", err=True)
                raise typer.Exit(code=1)
            eval_run_row = await run_eval(session, mode, triggered_by=user.id)
            results = list(
                (
                    await session.execute(
                        select(EvalResult)
                        .where(EvalResult.eval_run_id == eval_run_row.id)
                        .options(selectinload(EvalResult.eval_task))
                    )
                )
                .scalars()
                .all()
            )
            typer.echo(format_report(eval_run_row, results))

    _run(_do())


@eval_app.command("report")
def eval_report(
    run_id: Annotated[
        str | None, typer.Argument(help="Eval run id; defaults to the latest completed run.")
    ] = None,
) -> None:
    """Print the report for a given eval run, or the latest completed run."""

    async def _do() -> None:
        from context_engine.evals.report import format_report

        async with session_scope() as session:
            if run_id is not None:
                eval_run_row = await session.get(EvalRun, run_id)
            else:
                stmt = (
                    select(EvalRun)
                    .where(EvalRun.status == EvalRunStatus.completed)
                    .order_by(EvalRun.finished_at.desc())
                    .limit(1)
                )
                eval_run_row = (await session.execute(stmt)).scalar_one_or_none()

            if eval_run_row is None:
                typer.echo("Error: no matching eval run found.", err=True)
                raise typer.Exit(code=1)

            results = list(
                (
                    await session.execute(
                        select(EvalResult)
                        .where(EvalResult.eval_run_id == eval_run_row.id)
                        .options(selectinload(EvalResult.eval_task))
                    )
                )
                .scalars()
                .all()
            )
            typer.echo(format_report(eval_run_row, results))

    _run(_do())


@app.command()
def reindex(
    yes: Annotated[bool, typer.Option("--yes", help="Skip the confirmation prompt.")] = False,
    api_key: ApiKeyOption = DEFAULT_API_KEY,
) -> None:
    """Re-chunk and re-embed all active documents with the configured provider."""
    from context_engine.indexing.embeddings import current_embedding_version

    version = current_embedding_version()
    if not yes:
        confirmed = typer.confirm(
            f"Re-index ALL active documents with embedding version {version!r}?"
        )
        if not confirmed:
            typer.echo("Aborted.")
            raise typer.Exit(code=1)

    async def _do() -> None:
        from context_engine.indexing.reindex import reindex_all
        from context_engine.storage.models import UserRole

        async with session_scope() as session:
            user = await get_user_by_api_key(session, api_key)
            if user is None:
                typer.echo(f"Error: invalid or inactive api key: {api_key!r}", err=True)
                raise typer.Exit(code=1)
            if user.role != UserRole.admin:
                typer.echo("Error: reindex requires an admin api key.", err=True)
                raise typer.Exit(code=1)
            count = await reindex_all(session)
            typer.echo(f"Re-indexed {count} document(s) at {version}.")

    _run(_do())


@app.command("serve-api")
def serve_api(
    port: Annotated[int, typer.Option("--port", help="Port to listen on.")] = 8000,
) -> None:
    """Run the REST API with uvicorn (factory mode)."""
    try:
        import uvicorn
    except ImportError:
        typer.echo("Error: uvicorn is not installed.", err=True)
        raise typer.Exit(code=1) from None

    try:
        import context_engine.api.app  # noqa: F401
    except ImportError:
        typer.echo(
            "Error: context_engine.api.app is not available yet "
            "(the API package may still be under construction).",
            err=True,
        )
        raise typer.Exit(code=1) from None

    uvicorn.run(
        "context_engine.api.app:create_app",
        host="0.0.0.0",
        port=port,
        factory=True,
    )


@app.command("serve-mcp")
def serve_mcp(
    http: Annotated[
        bool, typer.Option("--http", help="Serve streamable-http on :8765 instead of stdio.")
    ] = False,
) -> None:
    """Run the MCP server (stdio by default, or streamable-http with --http)."""
    from context_engine.mcp_server.server import main as mcp_main

    mcp_main(http=http)

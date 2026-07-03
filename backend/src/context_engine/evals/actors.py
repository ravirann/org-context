"""Dramatiq actors for the eval harness (see docs/INTERFACES.md)."""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime

import dramatiq

import context_engine.observability.worker  # noqa: F401  (configures the dramatiq broker)
from context_engine.evals.harness import execute_eval_run
from context_engine.observability.logging import get_logger
from context_engine.storage.db import session_scope
from context_engine.storage.models import EvalRun, EvalRunStatus

logger = get_logger(__name__)


async def execute_eval_run_by_id(eval_run_id: str) -> None:
    """Load the pre-created EvalRun in its own session and execute it."""
    async with session_scope() as session:
        eval_run = await session.get(EvalRun, uuid.UUID(eval_run_id))
        if eval_run is None:
            logger.warning("eval_run_not_found", eval_run_id=eval_run_id)
            return
        await execute_eval_run(session, eval_run)


async def _mark_failed(eval_run_id: str, error: str) -> None:
    """Best-effort: persist a failed status when execution blew up entirely."""
    try:
        async with session_scope() as session:
            eval_run = await session.get(EvalRun, uuid.UUID(eval_run_id))
            if eval_run is None:
                return
            eval_run.status = EvalRunStatus.failed
            eval_run.summary = {"error": error}
            eval_run.finished_at = datetime.now(UTC)
    except Exception:
        logger.error("eval_run_mark_failed_error", eval_run_id=eval_run_id, exc_info=True)


@dramatiq.actor(max_retries=0)
def run_eval_actor(eval_run_id: str, mode: str) -> None:
    """Worker entrypoint: execute a pre-created eval run in its own session.

    ``execute_eval_run`` already converts task-level errors into a failed run;
    this wrapper additionally marks the run failed if execution itself raises
    (e.g. the database went away mid-run).
    """
    logger.info("run_eval_actor_start", eval_run_id=eval_run_id, mode=mode)
    try:
        asyncio.run(execute_eval_run_by_id(eval_run_id))
    except Exception as exc:
        logger.error("run_eval_actor_failed", eval_run_id=eval_run_id, error=str(exc))
        asyncio.run(_mark_failed(eval_run_id, str(exc)))

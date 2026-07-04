"""Aggregated /v1 routers for the context engine API."""

from __future__ import annotations

from fastapi import APIRouter

from context_engine.api.routes import (
    admin,
    agent_runs,
    auth,
    conflicts,
    context,
    context_debt,
    dashboard,
    documents,
    evals,
    feedback,
    heatmaps,
    me,
    relationships,
    search,
    settings,
    sources,
    system,
)

ALL_ROUTERS: list[APIRouter] = [
    auth.router,
    dashboard.router,
    context.router,
    search.router,
    documents.router,
    relationships.router,
    heatmaps.router,
    agent_runs.router,
    evals.router,
    sources.router,
    conflicts.router,
    context_debt.router,
    feedback.router,
    admin.router,
    settings.router,
    system.router,
    me.router,
]

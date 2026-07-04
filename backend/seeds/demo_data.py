"""Deterministic, realistic demo organization seed data.

Usage:
    python -m seeds.demo_data [--reset | --if-empty]

Public API:
    seed_demo(reset=False, if_empty=False) -> dict[str, int]
    seed_minimal(session) -> dict[str, int]   (fast seed for tests)
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import math
import random
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from context_engine.config.constants import CHUNK_SIZE_CHARS, DEMO_API_KEYS
from context_engine.indexing.embeddings import embed_text
from context_engine.indexing.tokens import estimate_tokens
from context_engine.observability.logging import get_logger
from context_engine.storage import models as m
from context_engine.storage.db import session_scope

logger = get_logger(__name__)

SEED = 42

# ---------------------------------------------------------------------------
# Static demo-org fixtures
# ---------------------------------------------------------------------------

TEAMS: list[tuple[str, str]] = [
    ("Payments", "Owns charging, refunds, invoicing and payment provider integrations."),
    ("Platform", "Owns auth, infra, CI/CD and shared platform services."),
    ("Growth", "Owns web app, onboarding funnels and experimentation."),
    ("Mobile", "Owns the mobile apps and the mobile BFF."),
    ("Data", "Owns pipelines, warehouse models and ML infrastructure."),
    ("SRE", "Owns reliability, observability and incident response."),
]

AVATAR_COLORS = [
    "#ef4444",
    "#f97316",
    "#f59e0b",
    "#84cc16",
    "#22c55e",
    "#14b8a6",
    "#06b6d4",
    "#3b82f6",
    "#6366f1",
    "#8b5cf6",
    "#d946ef",
    "#ec4899",
]

# (name, email, role, team)
USERS: list[tuple[str, str, str, str]] = [
    ("Ava Admin", "admin@demo.dev", "admin", "Platform"),
    ("Priya Sharma", "priya@demo.dev", "lead", "Payments"),
    ("Marcus Webb", "marcus@demo.dev", "lead", "Platform"),
    ("Elena Fischer", "elena@demo.dev", "lead", "Growth"),
    ("Kenji Tanaka", "kenji@demo.dev", "lead", "Mobile"),
    ("Sofia Rossi", "sofia@demo.dev", "lead", "Data"),
    ("Omar Haddad", "omar@demo.dev", "lead", "SRE"),
    ("Liam O'Brien", "liam@demo.dev", "engineer", "Payments"),
    ("Nina Petrov", "nina@demo.dev", "engineer", "Payments"),
    ("Dev Patel", "dev@demo.dev", "engineer", "Payments"),
    ("Grace Kim", "grace@demo.dev", "engineer", "Platform"),
    ("Tomás Silva", "tomas@demo.dev", "engineer", "Platform"),
    ("Jade Nguyen", "jade@demo.dev", "engineer", "Growth"),
    ("Felix Braun", "felix@demo.dev", "engineer", "Growth"),
    ("Ines Moreau", "ines@demo.dev", "engineer", "Mobile"),
    ("Ravi Iyer", "ravi@demo.dev", "engineer", "Mobile"),
    ("Lena Vogel", "lena@demo.dev", "engineer", "Data"),
    ("Chen Wei", "chen@demo.dev", "engineer", "Data"),
    ("Aisha Bello", "aisha@demo.dev", "engineer", "SRE"),
    ("Piotr Nowak", "piotr@demo.dev", "engineer", "SRE"),
    ("Maya Levi", "maya@demo.dev", "viewer", "Growth"),
    ("Sam Carter", "sam@demo.dev", "viewer", "Platform"),
    ("Yuki Mori", "yuki@demo.dev", "viewer", "Mobile"),
    ("Noor Khan", "noor@demo.dev", "viewer", "Data"),
]

# Demo raw API keys -> (user email, kind)
DEMO_KEY_OWNERS: dict[str, tuple[str, str]] = {
    DEMO_API_KEYS["admin"]: ("admin@demo.dev", "api"),
    DEMO_API_KEYS["lead"]: ("priya@demo.dev", "api"),
    DEMO_API_KEYS["engineer"]: ("jade@demo.dev", "api"),
    DEMO_API_KEYS["viewer"]: ("maya@demo.dev", "api"),
    DEMO_API_KEYS["mcp"]: ("admin@demo.dev", "mcp"),
}

# (type, name, authority_rank)
SOURCES: list[tuple[str, str, int]] = [
    ("adr", "ADR Repository", 95),
    ("incident", "Incident Tracker", 85),
    ("confluence", "Confluence Wiki", 80),
    ("github", "GitHub (demo-org)", 75),
    ("jira", "Jira (ENG)", 60),
    ("ci", "CI (Jenkins)", 50),
    ("feedback", "Agent Feedback", 40),
    ("slack", "Slack #engineering", 35),
]

DOC_TYPE_SOURCE: dict[str, str] = {
    "code": "github",
    "pr": "github",
    "ticket": "jira",
    "doc": "confluence",
    "message": "slack",
    "adr": "adr",
    "incident": "incident",
    "ci_run": "ci",
    "feedback": "feedback",
}

REPOS: list[str] = [
    "payments-api",
    "auth-service",
    "billing-worker",
    "notifications",
    "search-svc",
    "mobile-bff",
    "data-pipeline",
    "web-app",
    "infra-terraform",
    "design-system",
    "ml-models",
    "analytics-dashboard",
]

SERVICES: list[str] = [
    "payments-api",
    "auth-service",
    "billing-worker",
    "notifications",
    "search-svc",
    "mobile-bff",
    "data-pipeline",
    "web-app",
]

REPO_TEAM: dict[str, str] = {
    "payments-api": "Payments",
    "billing-worker": "Payments",
    "auth-service": "Platform",
    "infra-terraform": "SRE",
    "notifications": "Platform",
    "search-svc": "Growth",
    "web-app": "Growth",
    "design-system": "Growth",
    "mobile-bff": "Mobile",
    "data-pipeline": "Data",
    "ml-models": "Data",
    "analytics-dashboard": "Data",
}

REPO_SERVICE: dict[str, str] = {
    "payments-api": "payments-api",
    "billing-worker": "billing-worker",
    "auth-service": "auth-service",
    "notifications": "notifications",
    "search-svc": "search-svc",
    "web-app": "web-app",
    "mobile-bff": "mobile-bff",
    "data-pipeline": "data-pipeline",
    "infra-terraform": "auth-service",
    "design-system": "web-app",
    "ml-models": "data-pipeline",
    "analytics-dashboard": "data-pipeline",
}

ENDPOINTS = [
    "POST /v1/payments/charge",
    "POST /v1/payments/refunds",
    "POST /v1/auth/token",
    "POST /v1/auth/refresh",
    "POST /v1/notifications/send",
    "GET /v1/search",
    "GET /v1/billing/invoices",
    "GET /v1/mobile/home",
    "GET /v1/users/{id}",
    "POST /v1/webhooks/stripe",
]

TABLES = [
    "payments",
    "payment_attempts",
    "invoices",
    "users",
    "sessions",
    "notification_jobs",
    "search_index",
    "events_raw",
    "feature_flags",
    "refunds",
]

FLAGS = [
    "enable_retry_v2",
    "new_checkout_flow",
    "async_webhooks",
    "search_rerank",
    "dark_mode_mobile",
    "batch_invoicing",
    "strict_idempotency",
    "edge_caching",
]

PARAGRAPHS = [
    "The {endpoint} endpoint now validates idempotency keys before hitting the {table} table. "
    "Requests without an Idempotency-Key header are rejected with a 400 and the failure is "
    "recorded in {table2} for later analysis. Rollout is gated behind the {flag} feature flag.",
    "We observed p95 latency of {ms}ms on {service} after the last deploy. Profiling pointed at "
    "an N+1 query against {table}; the fix batches lookups and adds a covering index. Error rate "
    "dropped from {pct}% to under 0.2% within an hour of the rollout.",
    "Ownership note: {repo} is maintained by the {team} team. Changes touching {endpoint} require "
    "a review from a code owner, and any schema change to {table} must ship with an expand-"
    "contract migration plan and a rollback script.",
    "During {incident} the {service} service exhausted its connection pool because retries were "
    "not jittered. The remediation added exponential backoff with a 30s cap, and an alert now "
    "fires when pool utilization stays above {pct}% for five minutes.",
    "The {flag} flag controls the new behavior. When enabled, writes go through the outbox in "
    "{table} and a worker publishes events asynchronously. Consumers must tolerate at-least-once "
    "delivery; deduplicate on the event_id column.",
    "Integration tests cover the happy path plus 429 and 5xx retries against {endpoint}. Contract "
    "tests pin the response schema so downstream {service2} consumers do not break. See the "
    "runbook for how to replay failed jobs from {table}.",
    "Decision: we standardize on cursor-based pagination for {endpoint}. Offset pagination against "
    "{table} caused timeouts beyond 100k rows. Clients should send the opaque next_cursor token "
    "returned by the previous page.",
    "Deploys of {service} go out via the {repo} pipeline. Canary receives 5% of traffic for 15 "
    "minutes; automatic rollback triggers when the 5xx ratio exceeds {pct}% or p99 latency "
    "doubles against the control group.",
    "Security review flagged that {endpoint} logged raw PAN data in debug mode. Logging is now "
    "scrubbed by the pii_redaction middleware and an audit entry is written whenever a redaction "
    "pattern matches in {service} logs.",
    "Backfill guidance: replay events from {table} in day-sized batches to keep the {service} "
    "consumer lag under a minute. The {flag} flag pauses real-time ingestion while a backfill "
    "is running to avoid double counting.",
]

TITLES: dict[str, list[str]] = {
    "code": [
        "{repo}: charge flow module",
        "{repo}: retry helper",
        "{repo}: webhook handler",
        "{repo}: pagination utils",
        "{repo}: session middleware",
        "{repo}: outbox publisher",
        "{repo}: config loader",
        "{repo}: rate limiter",
    ],
    "pr": [
        "Add idempotency keys to {endpoint_short}",
        "Fix N+1 queries in {repo}",
        "Introduce outbox pattern for {service}",
        "Bump retry backoff cap in {repo}",
        "Add covering index on {table}",
        "Migrate {repo} to cursor pagination",
        "Scrub PII from {service} logs",
        "Canary rollout tooling for {repo}",
        "Harden webhook signature checks",
        "Add contract tests for {service}",
    ],
    "ticket": [
        "Investigate p95 regression on {service}",
        "Backfill {table} for March",
        "Rotate credentials for {service}",
        "Customers report duplicate charges",
        "Add alerting for {service} pool saturation",
        "Flaky test in {repo} CI",
        "Documentation gap: {service} runbook",
        "Cleanup deprecated {flag} flag",
    ],
    "doc": [
        "{service} runbook",
        "{service} architecture overview",
        "How to deploy {repo}",
        "On-call guide: {team} team",
        "Schema reference: {table}",
        "Testing strategy for {repo}",
        "Feature flag catalog",
        "Postmortem process",
    ],
    "message": [
        "heads up: {service} deploy going out",
        "who owns {table} these days?",
        "seeing 429s from {endpoint_short}",
        "canary for {repo} looks green",
        "reminder: freeze starts friday",
        "{flag} is now enabled in prod",
        "pool saturation alert on {service}",
        "retro notes from {incident}",
    ],
    "adr": [
        "ADR-{n}: Retry policy for {service}",
        "ADR-{n}: Pagination standard",
        "ADR-{n}: Outbox pattern for events",
        "ADR-{n}: Token TTL policy",
        "ADR-{n}: Canary deploy strategy",
        "ADR-{n}: PII redaction in logs",
        "ADR-{n}: Schema migration policy",
        "ADR-{n}: Idempotency requirements",
    ],
    "incident": [
        "{incident}: {service} elevated 5xx",
        "{incident}: duplicate charges on {service}",
        "{incident}: {service} connection pool exhaustion",
        "{incident}: webhook storm",
        "{incident}: stale cache served after deploy",
        "{incident}: {service} OOM loop",
    ],
    "ci_run": [
        "Build #{n}: {repo} main",
        "Nightly e2e: {repo}",
        "Release {repo} v1.{n}",
        "Coverage gate: {repo}",
        "Canary verify: {service}",
    ],
    "feedback": [
        "Agent feedback: missing {service} context",
        "Agent feedback: stale doc cited for {repo}",
        "Agent feedback: {service} packet was spot on",
        "Agent feedback: ACL blocked needed doc",
        "Agent feedback: wrong retry advice for {service}",
    ],
}

DOC_TYPE_COUNTS: dict[str, int] = {
    "code": 40,
    "pr": 60,
    "ticket": 50,
    "doc": 45,
    "message": 40,
    "adr": 14,
    "incident": 20,
    "ci_run": 30,
    "feedback": 15,
}

# Conflict groups: topic_key, title, affected, status, docs (doc_type, title, stance, age_days)
CONFLICT_SPECS: list[dict[str, Any]] = [
    {
        "topic_key": "payments-retry-policy",
        "title": "Retry policy for payment charges is contradicted",
        "repo": "payments-api",
        "service": "payments-api",
        "status": "resolved",
        "docs": [
            (
                "adr",
                "ADR-0042: Exponential backoff with jitter for payment retries",
                "exponential_backoff",
                60,
                "Decision: payment charge retries use exponential backoff with full jitter, base "
                "200ms, cap 30s, max 6 attempts. Fixed-interval retries caused synchronized load "
                "spikes on the payments table during INC-2107.",
            ),
            (
                "doc",
                "Payments runbook: retry handling (legacy)",
                "fixed_3_retries",
                330,
                "When a charge fails, retry exactly 3 times with a fixed 5 second delay before "
                "marking the payment_attempts row failed. This keeps behavior predictable for "
                "support engineers reading the payments table.",
            ),
        ],
    },
    {
        "topic_key": "auth-token-ttl",
        "title": "Access token TTL guidance diverges",
        "repo": "auth-service",
        "service": "auth-service",
        "status": "open",
        "docs": [
            (
                "adr",
                "ADR-0031: Access token TTL is 15 minutes",
                "ttl_15m",
                120,
                "Decision: access tokens issued by POST /v1/auth/token expire after 15 minutes and "
                "must be refreshed via POST /v1/auth/refresh. Long-lived tokens are banned after "
                "the sessions table audit.",
            ),
            (
                "message",
                "we bumped token TTL to 24h for the beta",
                "ttl_24h",
                45,
                "heads up: to unblock the mobile beta we bumped access token TTL to 24 hours in "
                "auth-service config. remember to revert before GA — sessions table growth is "
                "already noticeable.",
            ),
        ],
    },
    {
        "topic_key": "db-migration-strategy",
        "title": "Two documented database migration strategies",
        "repo": "payments-api",
        "service": "payments-api",
        "status": "open",
        "docs": [
            (
                "adr",
                "ADR-0027: Expand-contract schema migrations",
                "expand_contract",
                200,
                "Decision: all schema changes to production tables (payments, invoices, users) "
                "follow expand-contract: add nullable columns, dual-write, backfill, then drop. "
                "Destructive in-place migrations are banned.",
            ),
            (
                "doc",
                "Blue-green database migration guide",
                "blue_green",
                380,
                "Recommended approach: run a blue-green pair of databases and cut traffic over "
                "after replication catches up. This guide predates the expand-contract ADR and is "
                "kept for reference.",
            ),
        ],
    },
    {
        "topic_key": "notifications-provider",
        "title": "Transactional email provider is ambiguous",
        "repo": "notifications",
        "service": "notifications",
        "status": "resolved",
        "docs": [
            (
                "adr",
                "ADR-0038: Use SES for transactional email",
                "ses",
                90,
                "Decision: notifications sends transactional email through AWS SES with dedicated "
                "IP warmup. The notification_jobs worker retries via SQS with dead-lettering after "
                "5 attempts.",
            ),
            (
                "doc",
                "Twilio SendGrid setup for notifications",
                "sendgrid",
                400,
                "Setup guide for sending transactional email via SendGrid API keys stored in the "
                "notifications service. Includes template ids and webhook signature validation "
                "steps.",
            ),
        ],
    },
    {
        "topic_key": "search-ranking-weights",
        "title": "Search ranking weight guidance conflicts",
        "repo": "search-svc",
        "service": "search-svc",
        "status": "open",
        "docs": [
            (
                "doc",
                "Search ranking weights v2",
                "weights_v2",
                30,
                "The GET /v1/search ranker uses vector 0.45, fts 0.25, freshness 0.15, authority "
                "0.15 after the rerank experiment. The search_rerank flag must stay enabled for "
                "these weights to apply.",
            ),
            (
                "message",
                "revert rerank weights to v1?",
                "weights_v1",
                20,
                "seeing relevance complaints from growth — proposing we revert search-svc rerank "
                "weights to the v1 profile (vector 0.7, fts 0.3) until the offline eval finishes.",
            ),
        ],
    },
    {
        "topic_key": "mobile-release-cadence",
        "title": "Mobile release cadence is disputed",
        "repo": "mobile-bff",
        "service": "mobile-bff",
        "status": "open",
        "docs": [
            (
                "adr",
                "ADR-0044: Weekly mobile release trains",
                "weekly",
                75,
                "Decision: mobile ships on a weekly release train cut every Monday. Hotfixes ride "
                "the next train unless sev1. The mobile-bff API must stay backward compatible for "
                "two trains.",
            ),
            (
                "ticket",
                "Move mobile releases to biweekly",
                "biweekly",
                25,
                "App review overhead is crushing the team; proposal to move to biweekly releases "
                "and batch store submissions. Needs sign-off from Mobile and Growth leads before "
                "changing the train schedule.",
            ),
        ],
    },
]

RISKS_POOL = [
    "Retry semantics differ between documented sources; double charges possible if wrong doc used.",
    "Schema change touches a hot table; requires expand-contract rollout.",
    "Feature flag interactions are undocumented for this path.",
    "Stale runbook may describe removed configuration keys.",
    "Open conflict on this topic lowers confidence in the selected guidance.",
    "PII redaction patterns may not cover the new log fields.",
    "Canary metrics window may be too short to catch slow regressions.",
]

TESTS_POOL = [
    "Add an integration test covering 429 retry behavior with jittered backoff.",
    "Contract test pinning the response schema for downstream consumers.",
    "Migration test: apply expand phase, dual-write, verify backfill counts.",
    "Idempotency test: replay the same request id twice, assert single side effect.",
    "Load test the connection pool under retry storms.",
    "Regression test for pagination beyond 100k rows.",
    "E2E test for webhook signature validation failures.",
]

TASKS_BY_INTENT: dict[str, list[str]] = {
    "bugfix": [
        "Fix duplicate charge when webhook retries overlap on {service}",
        "Resolve p95 latency regression in {service} list endpoint",
        "Stop {service} from exhausting its DB connection pool under retry storms",
    ],
    "feature": [
        "Add cursor pagination to {service} search results",
        "Introduce outbox-based event publishing for {service}",
        "Ship idempotency keys for {service} mutation endpoints",
    ],
    "refactor": [
        "Extract retry helper in {repo} and align with the retry ADR",
        "Split the {service} webhook handler into verify/enqueue stages",
    ],
    "incident_response": [
        "Mitigate elevated 5xx on {service} and draft the postmortem",
        "Investigate stale cache served by {service} after deploy",
    ],
    "question": [
        "What is the current retry policy for {service}?",
        "Which team owns {repo} and what is the deploy process?",
        "What TTL should access tokens use for {service} clients?",
    ],
}

AGENT_NAMES = ["claude-code", "aider", "cursor-agent", "devin"]

APP_SETTINGS: dict[str, Any] = {
    # FTS leads: the default offline embeddings are deterministic-hash (no semantic
    # signal), useful only as a stable tie-breaker until a real provider is plugged in.
    "retrieval_weights": {"vector": 0.15, "fts": 0.50, "freshness": 0.20, "authority": 0.15},
    "freshness_window_days": 90,
    "authority_rules": {
        "source_type_ranks": {
            "adr": 95,
            "incident": 85,
            "confluence": 80,
            "github": 75,
            "jira": 60,
            "ci": 50,
            "feedback": 40,
            "slack": 35,
        }
    },
    "eval_thresholds": {"min_score": 0.5, "regression_delta": 0.05},
    "retention": {"audit_days": 180, "packet_days": 365},
    "pii_redaction": {
        "enabled": True,
        "patterns": [r"\b\d{16}\b", r"\b[\w.+-]+@[\w-]+\.[\w.]+\b", r"\b\d{3}-\d{2}-\d{4}\b"],
    },
    "feature_flags": {"graph_v2": True, "heatmap_export": False, "packet_diff": True},
    "token_budget": {"max_packet_tokens": 8000},
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _hash_key(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _uid(rng: random.Random) -> uuid.UUID:
    return uuid.UUID(int=rng.getrandbits(128), version=4)


def _chunk_text(content: str, size: int = CHUNK_SIZE_CHARS) -> list[str]:
    chunks: list[str] = []
    remaining = content.strip()
    while remaining:
        if len(remaining) <= size:
            chunks.append(remaining)
            break
        cut = remaining.rfind(" ", int(size * 0.6), size)
        cut = cut if cut > 0 else size
        chunks.append(remaining[:cut].strip())
        remaining = remaining[cut:].strip()
    return chunks or [content]


def _freshness(age_days: float, window: int = 90) -> float:
    return max(0.0, min(1.0, math.exp(-age_days / window)))


def _base_now() -> datetime:
    return datetime.now(UTC).replace(hour=12, minute=0, second=0, microsecond=0)


def _make_chunks(doc: m.Document, rng: random.Random) -> list[m.Chunk]:
    chunks = []
    for i, piece in enumerate(_chunk_text(doc.content)):
        chunks.append(
            m.Chunk(
                id=_uid(rng),
                document_id=doc.id,
                ord=i,
                content=piece,
                token_count=estimate_tokens(piece),
                embedding=embed_text(piece),
            )
        )
    return chunks


def _paragraphs(rng: random.Random, repo: str, service: str, team: str, n: int) -> str:
    out = []
    for tmpl in rng.sample(PARAGRAPHS, k=min(n, len(PARAGRAPHS))):
        out.append(
            tmpl.format(
                endpoint=rng.choice(ENDPOINTS),
                endpoint_short=rng.choice(ENDPOINTS).split(" ")[-1],
                table=rng.choice(TABLES),
                table2=rng.choice(TABLES),
                flag=rng.choice(FLAGS),
                incident=f"INC-{rng.randint(2100, 2199)}",
                ms=rng.choice([180, 240, 320, 450, 800, 1200]),
                pct=rng.choice([1, 2, 3, 5, 8]),
                repo=repo,
                service=service,
                service2=rng.choice(SERVICES),
                team=team,
            )
        )
    return "\n\n".join(out)


class _SeedContext:
    """Holds cross-references while building the demo org."""

    def __init__(self, rng: random.Random) -> None:
        self.rng = rng
        self.now = _base_now()
        self.teams: dict[str, m.Team] = {}
        self.users: dict[str, m.User] = {}
        self.sources: dict[str, m.Source] = {}
        self.documents: list[m.Document] = []
        self.chunks: list[m.Chunk] = []
        self.conflicts: list[m.Conflict] = []
        self.packets: list[m.ContextPacket] = []
        self.runs: list[m.AgentRun] = []
        self.entities: dict[tuple[str, str], m.Entity] = {}
        self.edges: dict[tuple[uuid.UUID, uuid.UUID, str], m.Edge] = {}


def _build_teams_users_keys(ctx: _SeedContext) -> tuple[list[Any], ...]:
    rng = ctx.rng
    teams = []
    for name, desc in TEAMS:
        team = m.Team(id=_uid(rng), name=name, description=desc)
        ctx.teams[name] = team
        teams.append(team)

    users = []
    for i, (name, email, role, team_name) in enumerate(USERS):
        user = m.User(
            id=_uid(rng),
            email=email,
            name=name,
            role=m.UserRole(role),
            team_id=ctx.teams[team_name].id,
            is_active=True,
            avatar_color=AVATAR_COLORS[i % len(AVATAR_COLORS)],
        )
        ctx.users[email] = user
        users.append(user)

    keys = []
    for raw, (email, kind) in DEMO_KEY_OWNERS.items():
        keys.append(
            m.ApiKey(
                id=_uid(rng),
                key_hash=_hash_key(raw),
                label=raw.replace("demo-", "").replace("-key", "").replace("-token", " (mcp)"),
                kind=m.ApiKeyKind(kind),
                user_id=ctx.users[email].id,
                is_active=True,
            )
        )
    return teams, users, keys


def _build_sources(ctx: _SeedContext) -> list[m.Source]:
    rng = ctx.rng
    sources = []
    for stype, name, rank in SOURCES:
        source = m.Source(
            id=_uid(rng),
            type=m.SourceType(stype),
            name=name,
            enabled=True,
            config={"org": "demo-org"} if stype == "github" else {},
            sync_status=m.SyncStatus.ok,
            last_synced_at=ctx.now - timedelta(hours=rng.randint(1, 48)),
            document_count=0,
            acl_sync_status=m.AclSyncStatus.ok,
            authority_rank=rank,
            freshness_window_days=90,
        )
        ctx.sources[stype] = source
        sources.append(source)
    return sources


def _make_document(
    ctx: _SeedContext,
    *,
    doc_type: str,
    title: str,
    content: str,
    repo: str | None,
    service: str | None,
    team_name: str | None,
    age_days: float,
    status: str = "active",
    topic_key: str | None = None,
    stance: str | None = None,
    external_id: str | None = None,
    acl: tuple[bool, list[str], list[str]] | None = None,
) -> m.Document:
    rng = ctx.rng
    source = ctx.sources[DOC_TYPE_SOURCE[doc_type]]
    team = ctx.teams.get(team_name) if team_name else None
    author = rng.choice([u for u in ctx.users.values() if u.role != m.UserRole.viewer])
    last_activity = ctx.now - timedelta(days=age_days, hours=rng.randint(0, 12))

    if acl is None:
        r = rng.random()
        if doc_type == "incident" and team_name == "Payments":
            acl = (False, [str(team.id)] if team else [], [])
        elif r < 0.70:
            acl = (True, [], [])
        elif r < 0.90 and team is not None:
            acl = (False, [str(team.id)], [])
        else:
            admin = ctx.users["admin@demo.dev"]
            allowed = [str(admin.id)]
            if team is not None:
                teammates = [u for u in ctx.users.values() if u.team_id == team.id]
                allowed += [str(u.id) for u in rng.sample(teammates, k=min(2, len(teammates)))]
            acl = (False, [], sorted(set(allowed)))

    doc = m.Document(
        id=_uid(rng),
        source_id=source.id,
        external_id=external_id or f"{doc_type}-{len(ctx.documents) + 1:04d}",
        doc_type=m.DocType(doc_type),
        title=title,
        content=content,
        url=f"https://demo.dev/{DOC_TYPE_SOURCE[doc_type]}/{doc_type}-{len(ctx.documents) + 1}",
        author_id=author.id,
        repo=repo,
        service=service,
        team_id=team.id if team else None,
        status=m.DocStatus(status),
        topic_key=topic_key,
        authority_score=source.authority_rank / 100.0,
        freshness_score=_freshness(age_days),
        acl_public=acl[0],
        acl_team_ids=acl[1],
        acl_user_ids=acl[2],
        last_activity_at=last_activity,
        doc_metadata={"stance": stance} if stance else {},
        usage_count=0,
        rejection_count=0,
        created_at=last_activity,
        updated_at=last_activity,
    )
    source.document_count += 1
    ctx.documents.append(doc)
    ctx.chunks.extend(_make_chunks(doc, rng))
    return doc


def _build_documents(ctx: _SeedContext) -> None:
    rng = ctx.rng
    stale_left, deprecated_left = 40, 12
    adr_n, build_n = 100, 4200
    for doc_type, count in DOC_TYPE_COUNTS.items():
        for _ in range(count):
            repo = rng.choice(REPOS)
            service = REPO_SERVICE[repo]
            team_name = REPO_TEAM[repo]
            age = rng.uniform(1, 400)
            status = "active"
            if age > 200 and stale_left > 0 and rng.random() < 0.45:
                status, stale_left = "stale", stale_left - 1
            elif age > 300 and deprecated_left > 0 and rng.random() < 0.35:
                status, deprecated_left = "deprecated", deprecated_left - 1
            title_tmpl = rng.choice(TITLES[doc_type])
            adr_n += 1
            build_n += rng.randint(1, 9)
            title = title_tmpl.format(
                repo=repo,
                service=service,
                team=team_name,
                table=rng.choice(TABLES),
                flag=rng.choice(FLAGS),
                endpoint_short=rng.choice(ENDPOINTS).split(" ")[-1],
                incident=f"INC-{rng.randint(2100, 2199)}",
                n=adr_n if doc_type == "adr" else build_n,
            )
            content = f"# {title}\n\n" + _paragraphs(
                ctx.rng, repo, service, team_name, rng.randint(2, 6)
            )
            _make_document(
                ctx,
                doc_type=doc_type,
                title=title,
                content=content,
                repo=repo,
                service=service,
                team_name=team_name,
                age_days=age,
                status=status,
            )


def _build_conflicts(ctx: _SeedContext) -> None:
    rng = ctx.rng
    resolver = ctx.users["priya@demo.dev"]
    for spec in CONFLICT_SPECS:
        doc_ids: list[str] = []
        adr_url = None
        recommended: uuid.UUID | None = None
        for doc_type, title, stance, age, content in spec["docs"]:
            doc = _make_document(
                ctx,
                doc_type=doc_type,
                title=title,
                content=f"# {title}\n\n{content}\n\n"
                + _paragraphs(rng, spec["repo"], spec["service"], REPO_TEAM[spec["repo"]], 2),
                repo=spec["repo"],
                service=spec["service"],
                team_name=REPO_TEAM[spec["repo"]],
                age_days=age,
                status="stale" if age > 300 else "active",
                topic_key=spec["topic_key"],
                stance=stance,
                acl=(True, [], []),
            )
            doc_ids.append(str(doc.id))
            if doc_type == "adr":
                recommended = doc.id
                adr_url = doc.url
        resolved = spec["status"] == "resolved"
        conflict = m.Conflict(
            id=_uid(rng),
            topic_key=spec["topic_key"],
            title=spec["title"],
            document_ids=doc_ids,
            status=m.ConflictStatus(spec["status"]),
            recommended_document_id=recommended if resolved else None,
            affected={"repos": [spec["repo"]], "services": [spec["service"]]},
            resolution_note=(
                f"Resolved in favor of the ADR; legacy guidance for {spec['topic_key']} marked "
                "stale and linked from the runbook."
                if resolved
                else None
            ),
            resolved_by=resolver.id if resolved else None,
            resolved_at=ctx.now - timedelta(days=rng.randint(3, 30)) if resolved else None,
            linked_adr_url=adr_url if resolved else None,
        )
        ctx.conflicts.append(conflict)


def _entity(
    ctx: _SeedContext, etype: str, name: str, ref: str | None = None, **meta: Any
) -> m.Entity:
    key = (etype, name)
    if key not in ctx.entities:
        ctx.entities[key] = m.Entity(
            id=_uid(ctx.rng),
            type=m.EntityType(etype),
            name=name,
            external_ref=ref,
            entity_metadata=meta,
        )
    return ctx.entities[key]


def _edge(ctx: _SeedContext, src: m.Entity, dst: m.Entity, etype: str, weight: float = 1.0) -> None:
    key = (src.id, dst.id, etype)
    if key not in ctx.edges and src.id != dst.id:
        ctx.edges[key] = m.Edge(
            id=_uid(ctx.rng),
            source_entity_id=src.id,
            target_entity_id=dst.id,
            type=m.EdgeType(etype),
            weight=weight,
            edge_metadata={},
        )


def _build_graph(ctx: _SeedContext) -> None:
    rng = ctx.rng
    team_entities = {name: _entity(ctx, "team", name, str(t.id)) for name, t in ctx.teams.items()}
    user_entities = {u.email: _entity(ctx, "user", u.name, str(u.id)) for u in ctx.users.values()}
    repo_entities = {r: _entity(ctx, "repo", r) for r in REPOS}
    service_entities = {s: _entity(ctx, "service", s) for s in SERVICES}

    for repo, team in REPO_TEAM.items():
        _edge(ctx, team_entities[team], repo_entities[repo], "owns")
    for service in SERVICES:
        _edge(ctx, team_entities[REPO_TEAM[service]], service_entities[service], "owns")
    for u in ctx.users.values():
        team_name = next(n for n, t in ctx.teams.items() if t.id == u.team_id)
        _edge(ctx, user_entities[u.email], team_entities[team_name], "member_of")

    by_type: dict[str, list[m.Document]] = {}
    for d in ctx.documents:
        by_type.setdefault(d.doc_type.value, []).append(d)

    def author_of(doc: m.Document) -> m.Entity | None:
        user = next((u for u in ctx.users.values() if u.id == doc.author_id), None)
        return user_entities.get(user.email) if user else None

    ticket_entities = []
    for i, d in enumerate(by_type.get("ticket", [])[:30]):
        ent = _entity(ctx, "ticket", f"ENG-{1400 + i}", str(d.id), title=d.title)
        ticket_entities.append(ent)
        author = author_of(d)
        if author:
            _edge(ctx, author, ent, "authored")

    incident_entities = []
    for i, d in enumerate(by_type.get("incident", [])[:18]):
        ent = _entity(ctx, "incident", f"INC-{2100 + i}", str(d.id), title=d.title)
        incident_entities.append(ent)
        if d.service in service_entities:
            _edge(ctx, ent, service_entities[d.service], "caused_by")

    pr_entities = []
    for i, d in enumerate(by_type.get("pr", [])[:45]):
        ent = _entity(ctx, "pr", f"PR #{800 + i}", str(d.id), title=d.title)
        pr_entities.append(ent)
        author = author_of(d)
        if author:
            _edge(ctx, author, ent, "authored")
        if d.repo in repo_entities:
            _edge(ctx, ent, repo_entities[d.repo], "modifies")
        if ticket_entities and rng.random() < 0.85:
            _edge(ctx, ent, rng.choice(ticket_entities), "references")
        if incident_entities and rng.random() < 0.35:
            _edge(ctx, ent, rng.choice(incident_entities), "resolves")

    for d in by_type.get("adr", [])[:16]:
        ent = _entity(ctx, "adr", d.title.split(":")[0], str(d.id), title=d.title)
        author = author_of(d)
        if author:
            _edge(ctx, author, ent, "authored")
        if d.service in service_entities:
            _edge(ctx, ent, service_entities[d.service], "documents")

    doc_entities = []
    for d in by_type.get("doc", [])[:15]:
        ent = _entity(ctx, "doc", d.title[:120], str(d.id))
        doc_entities.append(ent)
        author = author_of(d)
        if author:
            _edge(ctx, author, ent, "authored")

    for ep in ENDPOINTS[:8]:
        ent = _entity(ctx, "api", ep)
        for service in rng.sample(SERVICES, k=2):
            _edge(ctx, ent, service_entities[service], "used_by")

    for table in TABLES:
        ent = _entity(ctx, "db_table", table)
        for service in rng.sample(SERVICES, k=2):
            _edge(ctx, ent, service_entities[service], "depends_on")

    for src, dst in [
        ("mobile-bff", "payments-api"),
        ("mobile-bff", "auth-service"),
        ("web-app", "payments-api"),
        ("web-app", "search-svc"),
        ("payments-api", "billing-worker"),
        ("payments-api", "notifications"),
        ("web-app", "auth-service"),
        ("search-svc", "data-pipeline"),
        ("billing-worker", "notifications"),
        ("data-pipeline", "auth-service"),
    ]:
        _edge(ctx, service_entities[src], service_entities[dst], "depends_on")

    citable = pr_entities + doc_entities + ticket_entities
    for i, packet in enumerate(ctx.packets[:10]):
        ent = _entity(ctx, "context_packet", f"packet-{i + 1}", str(packet.id), task=packet.task)
        for target in rng.sample(citable, k=min(3, len(citable))):
            _edge(ctx, ent, target, "cites")
    for i, run in enumerate(ctx.runs[:10]):
        ent = _entity(ctx, "agent_run", f"run-{i + 1}", str(run.id), agent=run.agent_name)
        if run.context_packet_id is not None:
            packet_idx = next(
                (j for j, p in enumerate(ctx.packets[:10]) if p.id == run.context_packet_id), None
            )
            if packet_idx is not None:
                _edge(
                    ctx,
                    ent,
                    ctx.entities[("context_packet", f"packet-{packet_idx + 1}")],
                    "references",
                )
        if run.repo in {e.name for e in ctx.entities.values() if e.type == m.EntityType.repo}:
            _edge(ctx, ent, ctx.entities[("repo", run.repo)], "references")


def _build_packets(ctx: _SeedContext) -> None:
    rng = ctx.rng
    outcomes = (
        [m.AgentOutcome.succeeded] * 20
        + [m.AgentOutcome.failed] * 8
        + [m.AgentOutcome.pending] * 8
        + [m.AgentOutcome.abandoned] * 4
    )
    rng.shuffle(outcomes)
    requesters = [u for u in ctx.users.values() if u.role != m.UserRole.viewer]
    public_docs = [d for d in ctx.documents if d.acl_public]

    for i in range(40):
        intent = rng.choice(list(TASKS_BY_INTENT.keys()))
        repo = rng.choice(REPOS)
        service = REPO_SERVICE[repo]
        task = rng.choice(TASKS_BY_INTENT[intent]).format(service=service, repo=repo)
        pool = [d for d in public_docs if d.repo == repo] or public_docs
        selected_docs = rng.sample(pool, k=min(rng.randint(3, 6), len(pool)))
        rejected_pool = [d for d in public_docs if d not in selected_docs]
        rejected_docs = rng.sample(rejected_pool, k=rng.randint(1, 3))

        selected = []
        citations = []
        compiled_parts = [f"# Context: {task}", ""]
        for j, d in enumerate(selected_docs):
            score = round(rng.uniform(0.55, 0.97), 3)
            marker = f"S{j + 1}"
            reasons = rng.sample(
                [
                    "high vector similarity",
                    "matches repo",
                    "authoritative source",
                    "recent activity",
                    "fts keyword match",
                    "cited by prior packets",
                ],
                k=2,
            )
            selected.append(
                {
                    "document_id": str(d.id),
                    "title": d.title,
                    "doc_type": d.doc_type.value,
                    "score": score,
                    "reasons": reasons,
                }
            )
            quote = d.content.split("\n\n")[1][:180] if "\n\n" in d.content else d.content[:180]
            citations.append(
                {
                    "marker": marker,
                    "document_id": str(d.id),
                    "title": d.title,
                    "url": d.url,
                    "quote": quote,
                }
            )
            compiled_parts.append(f"## [{marker}] {d.title}\n{quote}…")
            d.usage_count += 1
        rejected = []
        for d in rejected_docs:
            rejected.append(
                {
                    "document_id": str(d.id),
                    "title": d.title,
                    "doc_type": d.doc_type.value,
                    "score": round(rng.uniform(0.1, 0.5), 3),
                    "reason": rng.choice(
                        [
                            "below score threshold",
                            "stale content",
                            "duplicate of selected source",
                            "different service",
                            "token budget exceeded",
                        ]
                    ),
                }
            )
            d.rejection_count += 1

        conflict_notes = []
        for c in ctx.conflicts:
            if repo in c.affected.get("repos", []) and rng.random() < 0.8:
                chosen = c.recommended_document_id or uuid.UUID(c.document_ids[0])
                conflict_notes.append(
                    {
                        "conflict_id": str(c.id),
                        "topic_key": c.topic_key,
                        "chosen_document_id": str(chosen),
                        "note": f"Preferred the higher-authority source for '{c.topic_key}'"
                        + ("" if c.status == m.ConflictStatus.resolved else " (conflict open)"),
                    }
                )
        blocked = rng.choice([0, 0, 0, 1, 1, 2, 3, 4])
        freshness = round(sum(d.freshness_score for d in selected_docs) / len(selected_docs), 3)
        authority = round(sum(d.authority_score for d in selected_docs) / len(selected_docs), 3)
        created = ctx.now - timedelta(days=rng.uniform(0, 60))
        packet = m.ContextPacket(
            id=_uid(rng),
            task=task,
            intent=m.Intent(intent),
            repo=repo,
            service=service,
            requested_by=rng.choice(requesters).id,
            compiled_context="\n\n".join(compiled_parts),
            selected_sources=selected,
            rejected_sources=rejected,
            citations=citations,
            conflict_notes=conflict_notes,
            acl_notes={
                "blocked_count": blocked,
                "note": (
                    f"{blocked} matching document(s) were hidden by ACL"
                    if blocked
                    else "No documents were blocked by ACL"
                ),
            },
            token_estimate=rng.randint(800, 6000),
            confidence_score=round(rng.uniform(0.4, 0.95), 3),
            freshness_score=freshness,
            authority_score=authority,
            risks=rng.sample(RISKS_POOL, k=rng.randint(1, 3)),
            recommended_tests=rng.sample(TESTS_POOL, k=rng.randint(1, 3)),
            agent_outcome=outcomes[i],
            feedback_score=round(rng.uniform(0.3, 1.0), 2) if rng.random() < 0.6 else None,
            created_at=created,
            updated_at=created,
        )
        ctx.packets.append(packet)


def _build_agent_runs(ctx: _SeedContext) -> None:
    rng = ctx.rng
    statuses = (
        [m.AgentRunStatus.succeeded] * 32
        + [m.AgentRunStatus.failed] * 9
        + [m.AgentRunStatus.running] * 5
    )
    rng.shuffle(statuses)
    engineers = [u for u in ctx.users.values() if u.role != m.UserRole.viewer]
    for i in range(46):
        packet = ctx.packets[i] if i < 30 else None
        repo = packet.repo if packet else rng.choice(REPOS)
        service = packet.service if packet else (REPO_SERVICE[repo] if repo else None)
        status = statuses[i]
        started = ctx.now - timedelta(days=rng.uniform(0, 30), hours=rng.uniform(0, 10))
        finished = (
            None
            if status == m.AgentRunStatus.running
            else started + timedelta(minutes=rng.randint(4, 95))
        )
        task = packet.task if packet else f"Ad-hoc maintenance task on {repo}"
        changed = [
            f"src/{(repo or 'app').replace('-', '_')}/{name}"
            for name in rng.sample(
                [
                    "handlers.py",
                    "retry.py",
                    "models.py",
                    "config.py",
                    "webhooks.py",
                    "pagination.py",
                    "tests/test_flow.py",
                ],
                k=rng.randint(1, 5),
            )
        ]
        if status == m.AgentRunStatus.failed:
            test_output = (
                "FAILED tests/test_flow.py::test_retry_backoff - AssertionError: expected "
                "jittered delays, got fixed 5s\n=== 38 passed, 1 failed in 42.1s ==="
            )
        elif status == m.AgentRunStatus.running:
            test_output = None
        else:
            test_output = f"=== {rng.randint(24, 120)} passed, {rng.randint(0, 3)} skipped ==="
        run = m.AgentRun(
            id=_uid(rng),
            agent_name=rng.choice(AGENT_NAMES),
            task=task,
            repo=repo,
            service=service,
            user_id=rng.choice(engineers).id,
            status=status,
            context_packet_id=packet.id if packet else None,
            plan=(
                f"1. Read the compiled context for {service or repo}\n"
                "2. Reproduce the issue with a failing test\n"
                "3. Implement the fix following the cited ADR\n"
                "4. Run the suite and open a PR"
            ),
            changed_files=changed,
            test_output=test_output,
            pr_url=(
                f"https://github.com/demo-org/{repo}/pull/{rng.randint(801, 999)}"
                if status == m.AgentRunStatus.succeeded
                else None
            ),
            reviewer_comments=(
                [
                    {
                        "author": rng.choice(engineers).name,
                        "comment": rng.choice(
                            [
                                "LGTM, nice use of the retry ADR.",
                                "Please add a contract test before merging.",
                                "Backoff cap should come from settings, not a constant.",
                            ]
                        ),
                    }
                ]
                if status != m.AgentRunStatus.running and rng.random() < 0.6
                else []
            ),
            langfuse_trace_id=uuid.UUID(int=rng.getrandbits(128)).hex
            if rng.random() < 0.35
            else None,
            started_at=started,
            finished_at=finished,
            created_at=started,
            updated_at=finished or started,
        )
        ctx.runs.append(run)


def _build_evals(ctx: _SeedContext) -> tuple[list[m.EvalTask], list[m.EvalRun], list[m.EvalResult]]:
    rng = ctx.rng
    tasks: list[m.EvalTask] = []
    specs = [
        (
            "payments-retry-policy",
            "payments-api",
            "What retry policy should payment charges use?",
            ["exponential", "backoff", "jitter"],
        ),
        (
            "auth-token-ttl",
            "auth-service",
            "What TTL should access tokens have?",
            ["ttl", "15 minutes", "refresh"],
        ),
        (
            "idempotency-keys",
            "payments-api",
            "How do we enforce idempotency on charge requests?",
            ["idempotency", "header", "duplicate"],
        ),
        (
            "pagination-standard",
            "search-svc",
            "Which pagination style is standard for list APIs?",
            ["cursor", "pagination", "next_cursor"],
        ),
        (
            "outbox-events",
            "notifications",
            "How should services publish domain events?",
            ["outbox", "at-least-once", "event_id"],
        ),
        (
            "canary-deploys",
            "web-app",
            "What is the canary rollout procedure?",
            ["canary", "rollback", "5xx"],
        ),
        (
            "pool-exhaustion",
            "payments-api",
            "How was the connection pool incident mitigated?",
            ["connection pool", "backoff", "alert"],
        ),
        (
            "pii-logging",
            "auth-service",
            "What are the PII logging requirements?",
            ["pii", "redaction", "audit"],
        ),
        (
            "schema-migrations",
            "billing-worker",
            "What is the schema migration policy?",
            ["expand", "contract", "backfill"],
        ),
        (
            "mobile-cadence",
            "mobile-bff",
            "How often do mobile releases ship?",
            ["release train", "weekly", "hotfix"],
        ),
    ]
    for name, service, question, keywords in specs:
        candidates = [d for d in ctx.documents if d.service == service and d.acl_public]
        # Golden expectations must be docs retrieval can plausibly surface for the
        # question: prefer candidates that actually mention the expected keywords.
        relevant = [
            d
            for d in candidates
            if any(k.lower() in f"{d.title}\n{d.content}".lower() for k in keywords)
        ]
        pool = relevant or candidates
        expected = [str(d.id) for d in rng.sample(pool, k=min(3, len(pool)))]
        tasks.append(
            m.EvalTask(
                id=_uid(rng),
                name=name,
                task=question,
                repo=next((r for r, s in REPO_SERVICE.items() if s == service), None),
                service=service,
                expected_document_ids=expected,
                expected_keywords=keywords,
                is_active=True,
            )
        )

    runs: list[m.EvalRun] = []
    results: list[m.EvalResult] = []
    # Kept in the range the real harness produces with offline deterministic
    # embeddings, so a fresh `ctx eval run` doesn't spuriously flag a regression.
    # Week 2 dips >delta below week 1 to demo the regression alert.
    engine_avgs = [0.38, 0.44, 0.36, 0.45, 0.48, 0.50]
    baseline_avgs = [0.15, 0.17, 0.16, 0.17, 0.18, 0.18]
    admin = ctx.users["admin@demo.dev"]
    for week, (eng_avg, base_avg) in enumerate(zip(engine_avgs, baseline_avgs, strict=True)):
        started = ctx.now - timedelta(weeks=len(engine_avgs) - week, hours=3)
        regression = week == 2
        run = m.EvalRun(
            id=_uid(rng),
            mode=m.EvalMode.comparison,
            status=m.EvalRunStatus.completed,
            triggered_by=admin.id,
            started_at=started,
            finished_at=started + timedelta(minutes=rng.randint(6, 18)),
            summary={},
            created_at=started,
            updated_at=started,
        )
        run_results: list[m.EvalResult] = []
        for task in tasks:
            for mode, avg in (("baseline", base_avg), ("context_engine", eng_avg)):
                score = round(min(1.0, max(0.0, rng.gauss(avg, 0.08))), 3)
                run_results.append(
                    m.EvalResult(
                        id=_uid(rng),
                        eval_run_id=run.id,
                        eval_task_id=task.id,
                        mode=m.EvalResultMode(mode),
                        score=score,
                        passed=score >= 0.6,
                        explanation=(
                            f"{mode}: retrieved context "
                            + ("hit" if score >= 0.6 else "missed")
                            + f" the expected documents for '{task.name}'"
                        ),
                        tokens_used=(
                            rng.randint(5500, 9500)
                            if mode == "baseline"
                            else rng.randint(1500, 4200)
                        ),
                        details={
                            "precision": round(min(1.0, score + rng.uniform(-0.05, 0.1)), 3),
                            "recall": round(min(1.0, score + rng.uniform(-0.1, 0.05)), 3),
                            "keyword_hits": rng.randint(1, len(task.expected_keywords)),
                            "citations_ok": score >= 0.5,
                        },
                        created_at=started,
                        updated_at=started,
                    )
                )
        eng_scores = [r.score for r in run_results if r.mode == m.EvalResultMode.context_engine]
        base_scores = [r.score for r in run_results if r.mode == m.EvalResultMode.baseline]
        regressed = sorted(t.name for t in rng.sample(tasks, k=2)) if regression else []
        run.summary = {
            "avg_score": round(sum(eng_scores) / len(eng_scores), 3),
            "pass_rate": round(sum(1 for s in eng_scores if s >= 0.6) / len(eng_scores), 3),
            "total_tokens": sum(
                r.tokens_used for r in run_results if r.mode == m.EvalResultMode.context_engine
            ),
            "baseline_avg_score": round(sum(base_scores) / len(base_scores), 3),
            "baseline_total_tokens": sum(
                r.tokens_used for r in run_results if r.mode == m.EvalResultMode.baseline
            ),
            "regression": regression,
            "regressed_task_names": regressed,
        }
        runs.append(run)
        results.extend(run_results)
    return tasks, runs, results


def _build_feedback(ctx: _SeedContext) -> list[m.Feedback]:
    rng = ctx.rng
    types = (
        [m.FeedbackType.useful] * 25
        + [m.FeedbackType.irrelevant] * 8
        + [m.FeedbackType.missing_context] * 7
        + [m.FeedbackType.stale_context] * 6
        + [m.FeedbackType.permission_issue] * 4
        + [m.FeedbackType.suggest_source] * 4
        + [m.FeedbackType.promote_authoritative] * 3
        + [m.FeedbackType.mark_deprecated] * 3
    )
    rng.shuffle(types)
    comments = {
        m.FeedbackType.useful: "Packet had exactly the ADR I needed.",
        m.FeedbackType.irrelevant: "Half the sources were about a different service.",
        m.FeedbackType.missing_context: "The incident postmortem was not included.",
        m.FeedbackType.stale_context: "Cited runbook describes config that no longer exists.",
        m.FeedbackType.permission_issue: "A needed doc was ACL-blocked; requesting access.",
        m.FeedbackType.suggest_source: "Please connect the on-call handbook as a source.",
        m.FeedbackType.promote_authoritative: "This ADR should always win for retry questions.",
        m.FeedbackType.mark_deprecated: "This guide predates the SES decision; deprecate it.",
    }
    rows: list[m.Feedback] = []
    users = list(ctx.users.values())
    for i, ftype in enumerate(types):
        on_packet = i < 40
        packet = rng.choice(ctx.packets) if on_packet else None
        document = None if on_packet else rng.choice(ctx.documents)
        if document is not None:
            if ftype == m.FeedbackType.mark_deprecated:
                document.status = m.DocStatus.deprecated
            elif ftype == m.FeedbackType.stale_context:
                document.status = m.DocStatus.stale
            elif ftype == m.FeedbackType.promote_authoritative:
                document.authority_score = 1.0
            elif ftype == m.FeedbackType.irrelevant:
                document.rejection_count += 1
            elif ftype == m.FeedbackType.useful:
                document.usage_count += 1
        rows.append(
            m.Feedback(
                id=_uid(rng),
                user_id=rng.choice(users).id,
                context_packet_id=packet.id if packet else None,
                document_id=document.id if document else None,
                type=ftype,
                comment=comments[ftype],
                created_at=ctx.now - timedelta(days=rng.uniform(0, 45)),
            )
        )
    return rows


def _build_activity(ctx: _SeedContext) -> list[m.ActivityEvent]:
    rng = ctx.rng
    rows: list[m.ActivityEvent] = []
    today = ctx.now.date()
    team_repos: dict[uuid.UUID, list[str]] = {}
    for repo, team_name in REPO_TEAM.items():
        team_repos.setdefault(ctx.teams[team_name].id, []).append(repo)
    role_events = {
        m.UserRole.admin: ["review", "doc_edit", "packet_use"],
        m.UserRole.lead: ["review", "pr", "ticket", "doc_edit", "packet_use"],
        m.UserRole.engineer: ["commit", "pr", "review", "ticket", "packet_use", "incident"],
        m.UserRole.viewer: ["doc_edit", "ticket"],
    }
    for user in ctx.users.values():
        repos = team_repos.get(user.team_id or uuid.UUID(int=0), REPOS[:2])
        base_p = {"admin": 0.5, "lead": 0.6, "engineer": 0.7, "viewer": 0.2}[user.role.value]
        for offset in range(90):
            day = today - timedelta(days=offset)
            p = base_p if day.weekday() < 5 else base_p * 0.15
            if rng.random() > p:
                continue
            for etype in rng.sample(role_events[user.role], k=rng.randint(1, 2)):
                repo = rng.choice(repos)
                rows.append(
                    m.ActivityEvent(
                        id=_uid(rng),
                        user_id=user.id,
                        team_id=user.team_id,
                        repo=repo,
                        service=REPO_SERVICE[repo],
                        event_type=m.ActivityEventType(etype),
                        day=day,
                        count=rng.randint(1, 6),
                    )
                )
    return rows


def _build_audit(ctx: _SeedContext) -> list[m.AuditLog]:
    rng = ctx.rng
    admin = ctx.users["admin@demo.dev"]
    leads = [u for u in ctx.users.values() if u.role == m.UserRole.lead]
    actions = [
        ("source.sync", "source"),
        ("settings.update", "settings"),
        ("conflict.resolve", "conflict"),
        ("acl.blocked", "document"),
        ("source.create", "source"),
        ("feedback.create", "feedback"),
        ("eval.run", "eval_run"),
        ("packet.compile", "context_packet"),
    ]
    rows: list[m.AuditLog] = []
    for i in range(80):
        action, rtype = actions[i % len(actions)]
        actor = (
            admin if action in {"settings.update", "source.create"} else rng.choice([admin, *leads])
        )
        if rtype == "source":
            resource_id = str(rng.choice(list(ctx.sources.values())).id)
        elif rtype == "conflict":
            resource_id = str(rng.choice(ctx.conflicts).id)
        elif rtype == "context_packet":
            resource_id = str(rng.choice(ctx.packets).id)
        elif rtype == "document":
            resource_id = str(rng.choice(ctx.documents).id)
        else:
            resource_id = None
        rows.append(
            m.AuditLog(
                id=_uid(rng),
                actor_id=actor.id,
                action=action,
                resource_type=rtype,
                resource_id=resource_id,
                detail={"note": f"{action} via demo seed", "n": i},
                created_at=ctx.now - timedelta(days=rng.uniform(0, 60)),
            )
        )
    return rows


def _build_sync_runs(ctx: _SeedContext) -> list[m.SyncRun]:
    """~2 sync runs per source (one realistic error) spread over the past 14 days."""
    rng = ctx.rng
    rows: list[m.SyncRun] = []
    error_messages = [
        "upstream returned 502 for 3/40 items; recorded and continued",
        "rate limited by GitHub API (secondary limit)",
        "connection reset while fetching page 2",
    ]
    for source in ctx.sources.values():
        for i in range(2):
            started = ctx.now - timedelta(days=rng.uniform(0, 14), hours=rng.uniform(0, 6))
            duration = timedelta(seconds=rng.randint(4, 90))
            errored = i == 1 and rng.random() < 0.5
            upserted = 0 if errored else rng.randint(3, source.document_count or 12)
            skipped = 0 if errored else rng.randint(0, 8)
            pruned = 0 if errored else rng.choice([0, 0, 0, 1, 2])
            rows.append(
                m.SyncRun(
                    id=_uid(rng),
                    source_id=source.id,
                    trigger=m.SyncTrigger.scheduled if i == 0 else m.SyncTrigger.manual,
                    status=m.SyncRunStatus.error if errored else m.SyncRunStatus.ok,
                    started_at=started,
                    finished_at=started + duration,
                    docs_upserted=upserted,
                    docs_skipped=skipped,
                    docs_pruned=pruned,
                    chunks_indexed=upserted * rng.randint(1, 3),
                    errors=(
                        [
                            {
                                "external_id": f"item-{rng.randint(1, 99)}",
                                "error": rng.choice(error_messages),
                            }
                        ]
                        if errored
                        else []
                    ),
                    created_at=started,
                    updated_at=started + duration,
                )
            )
    return rows


def _build_search_events(ctx: _SeedContext) -> list[m.SearchEvent]:
    """~30 search events over the past 14 days, incl. repeated zero-result queries."""
    rng = ctx.rng
    rows: list[m.SearchEvent] = []
    zero_result_queries = [
        "kafka partition rebalance runbook",
        "grpc deadline budget",
        "terraform drift detection policy",
    ]
    hit_queries = [
        "payment retry policy",
        "idempotency keys charge endpoint",
        "cursor pagination standard",
        "auth token ttl",
        "outbox event publishing",
        "canary rollback procedure",
        "connection pool exhaustion incident",
        "pii redaction logging",
    ]
    users = list(ctx.users.values())
    public_docs = [d for d in ctx.documents if d.acl_public]

    # Repeated zero-result queries (multiple hits each -> surfaces in context debt).
    for query in zero_result_queries:
        for _ in range(rng.randint(3, 5)):
            created = ctx.now - timedelta(days=rng.uniform(0, 14), hours=rng.uniform(0, 12))
            rows.append(
                m.SearchEvent(
                    id=_uid(rng),
                    user_id=rng.choice(users).id,
                    query=query,
                    result_count=0,
                    acl_blocked_count=rng.choice([0, 0, 1]),
                    took_ms=round(rng.uniform(8.0, 60.0), 2),
                    cache_hit=False,
                    top_document_ids=[],
                    created_at=created,
                )
            )

    # Successful queries with a handful of top document ids.
    for query in hit_queries:
        for _ in range(rng.randint(1, 3)):
            created = ctx.now - timedelta(days=rng.uniform(0, 14), hours=rng.uniform(0, 12))
            k = min(rng.randint(2, 6), len(public_docs))
            top = [str(d.id) for d in rng.sample(public_docs, k=k)]
            rows.append(
                m.SearchEvent(
                    id=_uid(rng),
                    user_id=rng.choice(users).id,
                    query=query,
                    result_count=len(top),
                    acl_blocked_count=rng.choice([0, 0, 0, 1, 2]),
                    took_ms=round(rng.uniform(5.0, 45.0), 2),
                    cache_hit=rng.random() < 0.3,
                    top_document_ids=top,
                    created_at=created,
                )
            )
    return rows


def _build_settings(ctx: _SeedContext) -> list[m.AppSetting]:
    return [m.AppSetting(key=k, value=v) for k, v in APP_SETTINGS.items()]


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------


async def _truncate_all(session: AsyncSession) -> None:
    from context_engine.storage.models import Base

    tables = ", ".join(t.name for t in reversed(Base.metadata.sorted_tables))
    await session.execute(text(f"TRUNCATE {tables} CASCADE"))


async def _is_empty(session: AsyncSession) -> bool:
    count = (await session.execute(select(func.count()).select_from(m.Team))).scalar_one()
    return int(count) == 0


def _build_all(ctx: _SeedContext) -> dict[str, list[Any]]:
    teams, users, keys = _build_teams_users_keys(ctx)
    sources = _build_sources(ctx)
    _build_documents(ctx)
    _build_conflicts(ctx)
    _build_packets(ctx)
    _build_agent_runs(ctx)
    _build_graph(ctx)
    eval_tasks, eval_runs, eval_results = _build_evals(ctx)
    feedback = _build_feedback(ctx)
    activity = _build_activity(ctx)
    audit = _build_audit(ctx)
    sync_runs = _build_sync_runs(ctx)
    search_events = _build_search_events(ctx)
    settings_rows = _build_settings(ctx)
    return {
        "teams": teams,
        "users": users,
        "api_keys": keys,
        "sources": sources,
        "documents": ctx.documents,
        "chunks": ctx.chunks,
        "entities": list(ctx.entities.values()),
        "edges": list(ctx.edges.values()),
        "conflicts": ctx.conflicts,
        "context_packets": ctx.packets,
        "agent_runs": ctx.runs,
        "eval_tasks": eval_tasks,
        "eval_runs": eval_runs,
        "eval_results": eval_results,
        "feedback": feedback,
        "activity_events": activity,
        "audit_logs": audit,
        "sync_runs": sync_runs,
        "search_events": search_events,
        "app_settings": settings_rows,
    }


_INSERT_ORDER = [
    "teams",
    "users",
    "api_keys",
    "sources",
    "documents",
    "chunks",
    "entities",
    "edges",
    "conflicts",
    "context_packets",
    "agent_runs",
    "eval_tasks",
    "eval_runs",
    "eval_results",
    "feedback",
    "activity_events",
    "audit_logs",
    "sync_runs",
    "search_events",
    "app_settings",
]


async def seed_demo(reset: bool = False, if_empty: bool = False) -> dict[str, int]:
    """Seed the full demo organization. Returns per-table row counts."""
    async with session_scope() as session:
        if reset:
            await _truncate_all(session)
        elif if_empty and not await _is_empty(session):
            logger.info("seed_skipped", reason="database not empty")
            return {}
        elif not await _is_empty(session):
            raise RuntimeError("Database is not empty; pass reset=True or if_empty=True.")

        ctx = _SeedContext(random.Random(SEED))
        data = _build_all(ctx)
        for key in _INSERT_ORDER:
            session.add_all(data[key])
            await session.flush()
        counts = {key: len(data[key]) for key in _INSERT_ORDER}
    logger.info("seed_complete", **counts)
    return counts


async def seed_minimal(session: AsyncSession) -> dict[str, int]:
    """Fast, small seed for tests. Uses the caller's session/transaction (no commit)."""
    rng = random.Random(SEED)
    now = _base_now()

    payments = m.Team(id=_uid(rng), name="Payments", description="Payments team")
    growth = m.Team(id=_uid(rng), name="Growth", description="Growth team")
    session.add_all([payments, growth])

    def make_user(name: str, email: str, role: str, team: m.Team) -> m.User:
        return m.User(
            id=_uid(rng),
            email=email,
            name=name,
            role=m.UserRole(role),
            team_id=team.id,
            is_active=True,
            avatar_color="#3b82f6",
        )

    admin = make_user("Ava Admin", "admin@demo.dev", "admin", payments)
    lead = make_user("Priya Sharma", "priya@demo.dev", "lead", payments)
    engineer = make_user("Jade Nguyen", "jade@demo.dev", "engineer", growth)
    viewer = make_user("Maya Levi", "maya@demo.dev", "viewer", growth)
    session.add_all([admin, lead, engineer, viewer])

    key_owner = {
        DEMO_API_KEYS["admin"]: (admin, "api"),
        DEMO_API_KEYS["lead"]: (lead, "api"),
        DEMO_API_KEYS["engineer"]: (engineer, "api"),
        DEMO_API_KEYS["viewer"]: (viewer, "api"),
        DEMO_API_KEYS["mcp"]: (admin, "mcp"),
    }
    keys = [
        m.ApiKey(
            id=_uid(rng),
            key_hash=_hash_key(raw),
            label=raw,
            kind=m.ApiKeyKind(kind),
            user_id=user.id,
            is_active=True,
        )
        for raw, (user, kind) in key_owner.items()
    ]
    session.add_all(keys)

    adr_source = m.Source(
        id=_uid(rng),
        type=m.SourceType.adr,
        name="ADR Repository",
        enabled=True,
        config={},
        sync_status=m.SyncStatus.ok,
        authority_rank=95,
        freshness_window_days=90,
        document_count=0,
    )
    wiki_source = m.Source(
        id=_uid(rng),
        type=m.SourceType.confluence,
        name="Confluence Wiki",
        enabled=True,
        config={},
        sync_status=m.SyncStatus.ok,
        authority_rank=80,
        freshness_window_days=90,
        document_count=0,
    )
    session.add_all([adr_source, wiki_source])

    docs: list[m.Document] = []
    chunks: list[m.Chunk] = []

    def make_doc(
        title: str,
        content: str,
        source: m.Source,
        doc_type: str,
        *,
        repo: str = "payments-api",
        service: str = "payments-api",
        team: m.Team | None = None,
        public: bool = True,
        team_ids: list[str] | None = None,
        user_ids: list[str] | None = None,
        topic_key: str | None = None,
        stance: str | None = None,
        age: int = 10,
        status: str = "active",
    ) -> m.Document:
        doc = m.Document(
            id=_uid(rng),
            source_id=source.id,
            external_id=f"min-{len(docs) + 1}",
            doc_type=m.DocType(doc_type),
            title=title,
            content=content,
            url=f"https://demo.dev/docs/min-{len(docs) + 1}",
            author_id=lead.id,
            repo=repo,
            service=service,
            team_id=(team or payments).id,
            status=m.DocStatus(status),
            topic_key=topic_key,
            authority_score=source.authority_rank / 100.0,
            freshness_score=_freshness(age),
            acl_public=public,
            acl_team_ids=team_ids or [],
            acl_user_ids=user_ids or [],
            last_activity_at=now - timedelta(days=age),
            doc_metadata={"stance": stance} if stance else {},
        )
        docs.append(doc)
        source.document_count += 1
        for i, piece in enumerate(_chunk_text(content)):
            chunks.append(
                m.Chunk(
                    id=_uid(rng),
                    document_id=doc.id,
                    ord=i,
                    content=piece,
                    token_count=estimate_tokens(piece),
                    embedding=embed_text(piece),
                )
            )
        return doc

    adr_doc = make_doc(
        "ADR-0042: Exponential backoff with jitter for payment retries",
        "Decision: payment charge retries use exponential backoff with full jitter, base 200ms, "
        "cap 30s, max 6 attempts. Fixed-interval retries caused synchronized load spikes on the "
        "payments table during INC-2107.",
        adr_source,
        "adr",
        topic_key="payments-retry-policy",
        stance="exponential_backoff",
        age=30,
    )
    legacy_doc = make_doc(
        "Payments runbook: retry handling (legacy)",
        "When a charge fails, retry exactly 3 times with a fixed 5 second delay before marking "
        "the payment_attempts row failed. Support engineers read the payments table directly.",
        wiki_source,
        "doc",
        topic_key="payments-retry-policy",
        stance="fixed_3_retries",
        age=320,
        status="stale",
    )
    make_doc(  # team-restricted: hidden from the engineer demo user
        "Payments postmortem: INC-2107 duplicate charges",
        "Team-restricted postmortem: duplicate charges occurred because webhook retries were not "
        "idempotent. Only the Payments team may read the raw customer impact numbers.",
        wiki_source,
        "doc",
        public=False,
        team_ids=[str(payments.id)],
        team=payments,
        age=40,
    )
    make_doc(  # user-restricted: admin only
        "Secret infra credentials rotation plan",
        "User-restricted: rotation schedule for the payment provider API keys and the vault "
        "paths that hold them. Access limited to named individuals.",
        wiki_source,
        "doc",
        public=False,
        user_ids=[str(admin.id)],
        age=15,
    )
    for i in range(6):
        make_doc(
            f"Payments guide {i + 1}: idempotency and webhooks",
            f"Guide {i + 1}: the POST /v1/payments/charge endpoint validates idempotency keys "
            "before writing to the payments table. Webhook retries must deduplicate on event_id. "
            "Cursor pagination is standard for list endpoints.",
            wiki_source,
            "doc",
            age=5 + i * 20,
        )
    session.add_all(docs)
    session.add_all(chunks)

    conflict = m.Conflict(
        id=_uid(rng),
        topic_key="payments-retry-policy",
        title="Retry policy for payment charges is contradicted",
        document_ids=[str(adr_doc.id), str(legacy_doc.id)],
        status=m.ConflictStatus.open,
        affected={"repos": ["payments-api"], "services": ["payments-api"]},
    )
    session.add(conflict)

    packets = []
    for i, requester in enumerate([admin, engineer]):
        packets.append(
            m.ContextPacket(
                id=_uid(rng),
                task=f"What is the retry policy for payments? (case {i + 1})",
                intent=m.Intent.question,
                repo="payments-api",
                service="payments-api",
                requested_by=requester.id,
                compiled_context=f"# Context\n\n## [S1] {adr_doc.title}\nUse exponential backoff…",
                selected_sources=[
                    {
                        "document_id": str(adr_doc.id),
                        "title": adr_doc.title,
                        "doc_type": "adr",
                        "score": 0.91,
                        "reasons": ["authoritative source"],
                    }
                ],
                rejected_sources=[
                    {
                        "document_id": str(legacy_doc.id),
                        "title": legacy_doc.title,
                        "doc_type": "doc",
                        "score": 0.42,
                        "reason": "stale content",
                    }
                ],
                citations=[
                    {
                        "marker": "S1",
                        "document_id": str(adr_doc.id),
                        "title": adr_doc.title,
                        "url": adr_doc.url,
                        "quote": adr_doc.content[:120],
                    }
                ],
                conflict_notes=[
                    {
                        "conflict_id": str(conflict.id),
                        "topic_key": conflict.topic_key,
                        "chosen_document_id": str(adr_doc.id),
                        "note": "ADR outranks legacy runbook",
                    }
                ],
                acl_notes={"blocked_count": i, "note": "ACL check applied"},
                token_estimate=1200 + i * 300,
                confidence_score=0.82,
                freshness_score=0.8,
                authority_score=0.95,
                risks=[RISKS_POOL[0]],
                recommended_tests=[TESTS_POOL[0]],
                agent_outcome=m.AgentOutcome.succeeded if i == 0 else m.AgentOutcome.pending,
            )
        )
    session.add_all(packets)

    runs = [
        m.AgentRun(
            id=_uid(rng),
            agent_name="claude-code",
            task=packets[0].task,
            repo="payments-api",
            service="payments-api",
            user_id=engineer.id,
            status=m.AgentRunStatus.succeeded,
            context_packet_id=packets[0].id,
            plan="1. Read context\n2. Fix\n3. Test",
            changed_files=["src/payments_api/retry.py"],
            test_output="=== 42 passed ===",
            pr_url="https://github.com/demo-org/payments-api/pull/812",
            reviewer_comments=[{"author": lead.name, "comment": "LGTM"}],
            started_at=now - timedelta(days=2),
            finished_at=now - timedelta(days=2) + timedelta(minutes=18),
        ),
        m.AgentRun(
            id=_uid(rng),
            agent_name="aider",
            task="Ad-hoc fix on payments-api",
            repo="payments-api",
            service="payments-api",
            user_id=lead.id,
            status=m.AgentRunStatus.failed,
            context_packet_id=None,
            plan="1. Patch\n2. Test",
            changed_files=["src/payments_api/webhooks.py"],
            test_output="FAILED tests/test_webhooks.py::test_dedupe - AssertionError",
            started_at=now - timedelta(days=1),
            finished_at=now - timedelta(days=1) + timedelta(minutes=9),
        ),
    ]
    session.add_all(runs)

    golden = m.EvalTask(
        id=_uid(rng),
        name="payments-retry-policy",
        task="What retry policy should payment charges use?",
        repo="payments-api",
        service="payments-api",
        expected_document_ids=[str(adr_doc.id)],
        expected_keywords=["exponential", "backoff", "jitter"],
        is_active=True,
    )
    session.add(golden)

    eval_run = m.EvalRun(
        id=_uid(rng),
        mode=m.EvalMode.comparison,
        status=m.EvalRunStatus.completed,
        triggered_by=admin.id,
        started_at=now - timedelta(days=3),
        finished_at=now - timedelta(days=3) + timedelta(minutes=7),
        summary={
            "avg_score": 0.8,
            "pass_rate": 1.0,
            "total_tokens": 2100,
            "baseline_avg_score": 0.45,
            "baseline_total_tokens": 7800,
            "regression": False,
            "regressed_task_names": [],
        },
    )
    session.add(eval_run)
    session.add_all(
        [
            m.EvalResult(
                id=_uid(rng),
                eval_run_id=eval_run.id,
                eval_task_id=golden.id,
                mode=m.EvalResultMode.baseline,
                score=0.45,
                passed=False,
                explanation="baseline missed the retry ADR",
                tokens_used=7800,
                details={"precision": 0.4, "recall": 0.5, "keyword_hits": 1, "citations_ok": False},
            ),
            m.EvalResult(
                id=_uid(rng),
                eval_run_id=eval_run.id,
                eval_task_id=golden.id,
                mode=m.EvalResultMode.context_engine,
                score=0.8,
                passed=True,
                explanation="engine retrieved ADR-0042 with citations",
                tokens_used=2100,
                details={"precision": 0.9, "recall": 0.75, "keyword_hits": 3, "citations_ok": True},
            ),
        ]
    )

    feedback_rows = [
        m.Feedback(
            id=_uid(rng),
            user_id=engineer.id,
            context_packet_id=packets[0].id,
            document_id=None,
            type=m.FeedbackType.useful,
            comment="Exactly the ADR I needed.",
        ),
        m.Feedback(
            id=_uid(rng),
            user_id=lead.id,
            context_packet_id=None,
            document_id=legacy_doc.id,
            type=m.FeedbackType.stale_context,
            comment="Legacy runbook is outdated.",
        ),
    ]
    session.add_all(feedback_rows)

    activity = []
    for user in (admin, lead, engineer, viewer):
        for offset in range(0, 7, 2):
            activity.append(
                m.ActivityEvent(
                    id=_uid(rng),
                    user_id=user.id,
                    team_id=user.team_id,
                    repo="payments-api",
                    service="payments-api",
                    event_type=m.ActivityEventType.commit,
                    day=now.date() - timedelta(days=offset),
                    count=rng.randint(1, 4),
                )
            )
    session.add_all(activity)

    session.add_all([m.AppSetting(key=k, value=v) for k, v in APP_SETTINGS.items()])
    audit = m.AuditLog(
        id=_uid(rng),
        actor_id=admin.id,
        action="source.sync",
        resource_type="source",
        resource_id=str(adr_source.id),
        detail={"note": "seed_minimal"},
    )
    session.add(audit)

    sync_runs = [
        m.SyncRun(
            id=_uid(rng),
            source_id=adr_source.id,
            trigger=m.SyncTrigger.scheduled,
            status=m.SyncRunStatus.ok,
            started_at=now - timedelta(days=1),
            finished_at=now - timedelta(days=1) + timedelta(seconds=12),
            docs_upserted=8,
            docs_skipped=0,
            docs_pruned=0,
            chunks_indexed=8,
            errors=[],
        ),
        m.SyncRun(
            id=_uid(rng),
            source_id=wiki_source.id,
            trigger=m.SyncTrigger.manual,
            status=m.SyncRunStatus.error,
            started_at=now - timedelta(days=2),
            finished_at=now - timedelta(days=2) + timedelta(seconds=5),
            docs_upserted=0,
            docs_skipped=0,
            docs_pruned=0,
            chunks_indexed=0,
            errors=[{"external_id": "min-3", "error": "upstream returned 502"}],
        ),
    ]
    session.add_all(sync_runs)

    search_events = []
    for query, count in [
        ("kafka partition rebalance runbook", 0),
        ("kafka partition rebalance runbook", 0),
        ("grpc deadline budget", 0),
        ("payment retry policy", 3),
        ("idempotency keys", 2),
    ]:
        created = now - timedelta(days=rng.uniform(0, 14))
        search_events.append(
            m.SearchEvent(
                id=_uid(rng),
                user_id=engineer.id,
                query=query,
                result_count=count,
                acl_blocked_count=0,
                took_ms=round(rng.uniform(5.0, 40.0), 2),
                cache_hit=False,
                top_document_ids=[str(adr_doc.id)] if count else [],
                created_at=created,
            )
        )
    session.add_all(search_events)

    await session.flush()
    return {
        "teams": 2,
        "users": 4,
        "api_keys": 5,
        "sources": 2,
        "documents": len(docs),
        "chunks": len(chunks),
        "conflicts": 1,
        "context_packets": 2,
        "agent_runs": 2,
        "eval_tasks": 1,
        "eval_runs": 1,
        "eval_results": 2,
        "feedback": 2,
        "activity_events": len(activity),
        "app_settings": len(APP_SETTINGS),
        "audit_logs": 1,
        "sync_runs": len(sync_runs),
        "search_events": len(search_events),
    }


def main() -> None:
    """CLI entrypoint: python -m seeds.demo_data [--reset|--if-empty]."""
    parser = argparse.ArgumentParser(description="Seed the demo organization")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--reset", action="store_true", help="truncate all tables first")
    group.add_argument(
        "--if-empty", action="store_true", help="only seed when the database is empty"
    )
    args = parser.parse_args()
    counts = asyncio.run(seed_demo(reset=args.reset, if_empty=args.if_empty))
    logger.info("seed_done", **counts)


if __name__ == "__main__":
    main()

# Architecture — Org Context Engineering Platform

A context engine (not naive RAG) that ingests engineering knowledge (code, PRs, tickets, docs,
Slack-like messages, ADRs, incidents, CI metadata, feedback) and serves **decision-grade,
source-backed, ACL-enforced context packets** to coding agents via REST, MCP, CLI, and a web UI.

## Monorepo layout

```
backend/            Python 3.12, uv, FastAPI, SQLAlchemy 2 (async), Postgres+pgvector, Redis, Dramatiq
  src/context_engine/
    config/           Pydantic Settings (env-driven), constants
    storage/          SQLAlchemy models, async session, repositories
    connectors/       Source connectors (github, jira, slack, confluence, adr, incident, ci, feedback)
    ingestion/        Normalization pipeline: connector payload -> Document + entities + edges
    indexing/         Chunking, embeddings (pluggable, default deterministic hash — no API key), FTS
    retrieval/        Hybrid retrieval: vector + FTS + freshness + authority; ACL pre-filter; rerank
    reasoning/        Intent classification, conflict detection, scoring (freshness/authority/confidence)
    context_compiler/ Builds ContextPacket: select/reject sources, resolve conflicts, ACL notes,
                      token budgeting, citations, risks, recommended tests
    api/              FastAPI app factory + /v1 routers (see API_CONTRACT.md)
    mcp_server/       MCP server (FastMCP, stdio + streamable-http) exposing context tools
    cli/              Typer CLI `ctx`
    evals/            Golden tasks, baseline-vs-engine harness, scoring, regression detection
    observability/    structlog setup, Langfuse shim (no-op without keys), audit log, request middleware
  alembic/            Migrations
  seeds/              Deterministic realistic demo-org data
  tests/              unit/, integration/, api/
frontend/           React 18 + TS + Vite + Tailwind v4 + TanStack Query v5 + Zustand + React Flow
                    (@xyflow/react) + Recharts + TanStack Table v8 + local shadcn-style ui kit
docs/               This documentation
docker-compose.yml  db (pgvector), redis, api, worker, ui
Makefile            All required targets
Jenkinsfile         CI: lint, typecheck, backend tests, frontend tests, coverage gate ≥85%, e2e
```

## Key decisions

- **Embeddings**: `EmbeddingProvider` protocol. Default `DeterministicEmbeddingProvider`
  (hash-based, dim=384, stable, offline). Pluggable for real models later. pgvector cosine.
- **Hybrid retrieval**: score = w_vec·cosine + w_fts·ts_rank + w_fresh·freshness + w_auth·authority
  (weights live in `settings` table, editable in Admin UI). ACL filter applied **in SQL** before
  scoring; blocked docs are counted and reported as `acl_blocked_count` (never leaked).
- **Conflict detection**: documents sharing a `topic_key` with divergent `stance` metadata, plus
  heuristic contradiction detection at compile time. Conflicts persisted, surfaced in UI.
- **Context packet**: immutable record with selected + rejected sources (with reasons), citations,
  conflict-resolution notes, ACL notes, token estimate, confidence/freshness/authority scores,
  risks, recommended tests. Agents get the packet; UI inspects it.
- **Queue**: Dramatiq + Redis. Actors: `sync_source`, `run_eval`. API enqueues; worker executes.
  In tests/dev, actors also run inline (StubBroker).
- **AuthN/Z**: `Authorization: Bearer <api-key>` -> user. Roles: admin, lead, engineer, viewer.
  Document ACL: `{public, allowed_team_ids, allowed_user_ids}`. Admin sees all; others need
  public OR team OR direct grant. Enforced in retrieval SQL and per-document endpoints (404 on
  denied reads to avoid existence leaks; UI shows permission-denied state on 403 for actions).
- **Observability**: structlog JSON logs, request-id middleware, audit_logs table for mutations,
  Langfuse shim (activates only when LANGFUSE_* env present), per-request timing.
- **No OpenSearch**: Postgres FTS (tsvector, GIN) + pgvector cover search.
- **Search everywhere is ACL-filtered.** No endpoint returns content the caller cannot read.

## Data flow

connector.fetch() -> ingestion.normalize() -> Document(+ACL, +entities, +edges)
 -> indexing.chunk+embed+tsv -> storage
query -> reasoning.classify_intent -> retrieval.hybrid (ACL SQL filter) -> reasoning.conflicts
 -> context_compiler.compile -> ContextPacket (persisted) -> REST/MCP/CLI/UI

## Ports

- API: 8000  ·  UI dev: 5173  ·  UI docker: 8080  ·  Postgres host: 5433  ·  Redis host: 6380

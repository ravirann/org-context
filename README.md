# Org Context — Context Engineering Platform

A production-grade context engine for an organization's coding agents. Ingests engineering
knowledge (code, PRs, tickets, docs, Slack-like messages, ADRs, incidents, CI metadata,
feedback), and serves **decision-grade, source-backed, ACL-enforced context packets** over
REST, MCP, and CLI — with a full web UI for inspecting, debugging, and improving context
quality.

> Docs: [Architecture](docs/ARCHITECTURE.md) · [Data model](docs/DATA_MODEL.md) ·
> [API contract](docs/API_CONTRACT.md) · [MCP guide](docs/MCP.md) · [CLI](docs/CLI.md) ·
> [Eval harness](docs/EVALS.md) · [Conventions](docs/CONVENTIONS.md) ·
> [Interfaces](docs/INTERFACES.md)

## Quick start

```bash
make setup          # install backend (uv) + frontend (pnpm) deps
make run            # full stack via docker compose  →  UI http://localhost:8080, API :8000
# or, for local dev:
make ingest-demo    # start db+redis, migrate, seed a realistic demo org
make run-api        # FastAPI with reload on :8000
make run-ui         # Vite dev server on :5173
```

If host port 8000 is taken: `CE_API_PORT=8010 make run` (the UI image is built against the
matching URL automatically).

**Auth modes** — `CE_AUTH_MODE=demo` (default): API keys, switch roles in the UI top bar
(`demo-admin-key`, `demo-lead-key`, `demo-engineer-key`, `demo-viewer-key`; MCP:
`demo-mcp-token`). `CE_AUTH_MODE=oidc`: real SSO — `docker compose up -d keycloak`, set
`CE_OIDC_*` per [docs/IAM.md](docs/IAM.md), and the UI shows a login page
(`admin@demo.dev` / `demo1234` maps to the seeded admin). API keys keep working for
agents/CLI/MCP in both modes, and are minted/revoked in Admin → API keys.

**Data sources** — every connector runs in `demo` mode by default (offline fixtures); flip a
source to `live` with real credentials (GitHub PAT, Jira/Confluence API token, Slack bot
token) via Sources → Configure or `PATCH /v1/sources/{id}` — incremental cursors, retries,
and credential masking included ([docs/CONNECTORS.md](docs/CONNECTORS.md)). The seeded demo org has
6 teams, 24 users, 8 sources, 326 documents (public/team/user-restricted ACL mix), a
209-node knowledge graph, 6 conflicts, 40+ context packets, 46 agent runs, 90 days of
activity heatmap data, and a 6-week eval history.

## What makes it a context *engine* (not naive RAG)

- **Hybrid retrieval**: pgvector + Postgres FTS + freshness + source authority, weights
  tunable live in Admin → Retrieval.
- **Reasoning**: intent classification, conflict detection across sources (topic-key +
  stance), authority/freshness scoring.
- **Context compiler**: packs a token-budgeted packet with *selected and rejected* sources
  (with reasons), `[S1]`-style citations, conflict-resolution notes, risks, and recommended
  tests — every packet persisted and inspectable in the UI.
- **ACL before anything**: enforced in SQL for search/compile, 404-on-hidden for documents,
  blocked counts surfaced (never the content), RBAC on admin/mutating routes, audit log.
- **Feedback loop**: useful/irrelevant/missing/stale signals adjust authority and status and
  feed the Context Debt dashboard.
- **Evals**: baseline-vs-engine harness over golden tasks with regression alerts
  (engine 0.599 avg / 80% pass vs baseline 0.179 / 0% on the demo org — see
  [docs/EVALS.md](docs/EVALS.md)).

## Commands

`make setup · run · run-api · run-ui · run-worker · ingest-demo · test · test-api · test-ui ·
test-e2e · coverage · lint · typecheck · eval`

## Testing & CI

Backend: pytest — unit, integration, API, ACL, retrieval, conflict, and eval tests (**353
tests, 93.9% coverage, hard 85% gate**). Frontend: Vitest + Testing Library — component,
page, chart/graph/heatmap rendering, and accessibility smoke tests (**266 tests, 97.3% line
coverage, 85% thresholds**), plus a 10-scenario Playwright E2E suite against the composed
stack. The [Jenkinsfile](Jenkinsfile) fails the build below 85% coverage on either side.

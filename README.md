# Org Context — Context Engineering Platform

A production-grade context engine for an organization's coding agents. Ingests engineering
knowledge (code, PRs, tickets, docs, Slack-like messages, ADRs, incidents, CI metadata,
feedback), and serves **decision-grade, source-backed, ACL-enforced context packets** over
REST, MCP, CLI — with a full web UI for inspecting, debugging, and improving context quality.

> Docs: [Architecture](docs/ARCHITECTURE.md) · [Data model](docs/DATA_MODEL.md) ·
> [API contract](docs/API_CONTRACT.md) · [Conventions](docs/CONVENTIONS.md)

## Quick start

```bash
make setup          # install backend (uv) + frontend (pnpm) deps
make run            # full stack via docker compose  →  UI http://localhost:8080, API :8000
# or, for local dev:
make ingest-demo    # start db+redis, migrate, seed a realistic demo org
make run-api        # FastAPI with reload on :8000
make run-ui         # Vite dev server on :5173
```

Demo API keys (select in the UI top bar): `demo-admin-key`, `demo-lead-key`,
`demo-engineer-key`, `demo-viewer-key`. MCP token: `demo-mcp-token`.

## Commands

`make setup · run · run-api · run-ui · ingest-demo · test · test-api · test-ui · test-e2e ·
coverage · lint · typecheck · eval`

## Testing & CI

Backend: pytest (unit + integration + API + ACL + retrieval + conflict + eval tests) with a
**hard 85% coverage gate**. Frontend: Vitest + Testing Library with **85% coverage thresholds**,
plus Playwright E2E. The [Jenkinsfile](Jenkinsfile) fails the build below 85% on either side.

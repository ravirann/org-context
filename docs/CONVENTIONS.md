# Conventions & Agent File Ownership

## Backend
- Python 3.12 (uv-managed, `.python-version` = 3.12). Package `context_engine` under
  `backend/src/`. Absolute imports (`from context_engine.storage import ...`).
- SQLAlchemy 2.0 async (asyncpg). One `Base` in `storage/models.py`. Sessions via
  `storage/db.py: get_session()` (FastAPI dependency) and `session_scope()` (scripts/workers).
- Settings: `config/settings.py` `Settings(BaseSettings)` env-prefix `CE_`, cached
  `get_settings()`. DATABASE_URL default `postgresql+asyncpg://ce:ce@localhost:5433/context_engine`.
- Ruff (line-length 100, rules: E,F,I,UP,B) + mypy (strict-ish: disallow_untyped_defs, but
  pragmatic ignores allowed for third-party). All public functions typed.
- Tests: pytest + pytest-asyncio (asyncio_mode=auto) + httpx AsyncClient (ASGITransport).
  Integration/API tests hit real Postgres (compose service on :5433, db `context_engine_test`)
  — fixtures in `backend/tests/conftest.py` create/drop schema per session, truncate per test.
  Dramatiq StubBroker in tests; eval/sync actors executed inline.
- Coverage: `pytest --cov=context_engine --cov-fail-under=85` (configured in pyproject).
- IMPORTANT: mypy/ruff must pass with zero errors. No `print` (use structlog logger).

## Frontend
- React 18 + TS strict + Vite 6 + Tailwind v4 (`@tailwindcss/vite`) + react-router-dom v7
  (declarative `<Routes>`), TanStack Query v5, Zustand, @xyflow/react, Recharts, TanStack Table v8.
- Local shadcn-style kit in `src/components/ui/` (Button, Card, Badge, Input, Select, Dialog,
  Tabs, Table, Tooltip, Toast, Skeleton, EmptyState, ErrorState, PermissionDenied, Spinner) —
  hand-written, CVA + tailwind-merge, Radix primitives allowed.
- Theme: CSS variables (`--background`, `--foreground`, `--card`, `--primary`, `--muted`,
  `--accent`, `--destructive`, `--border`, `--ring`, chart palette `--chart-1..6`) with `.dark`
  class on `<html>`; Zustand `useThemeStore` persists to localStorage.
- API: `src/lib/api.ts` typed fetch wrapper reading key from `useAuthStore` (localStorage,
  default `demo-admin-key`, switchable in UI). Types in `src/lib/types.ts` mirror API_CONTRACT.
  Base URL: `import.meta.env.VITE_API_URL ?? "http://localhost:8000"`.
- Every page handles: loading (skeletons), error (ErrorState w/ retry), empty (EmptyState),
  permission-denied (403 → PermissionDenied component).
- Tests: Vitest + @testing-library/react + jsdom; global fetch mocked per test (msw not required;
  a `mockApi` helper in `tests/utils.tsx` wraps QueryClientProvider + MemoryRouter).
  Coverage v8 thresholds 85 (lines, statements, functions, branches 75) in vite config.
- Playwright e2e in `frontend/e2e/` runs against docker compose stack (API :8000 seeded + UI).

## Commit/branch
- Branch `feature/context-engineering-platform`; commits per wave, imperative subject.

## Agent file-ownership map (DO NOT touch files owned by another agent)
- BF (backend-foundation): backend/pyproject.toml, backend/src/context_engine/{config,storage,
  observability}/, alembic/, seeds/, backend/tests/conftest.py, docker/entrypoint bits
- BI (ingestion): connectors/, ingestion/, indexing/
- BR (retrieval): retrieval/, reasoning/, context_compiler/
- BA (api): api/
- BM (mcp+cli): mcp_server/, cli/
- BE (evals): evals/
- FF (frontend-foundation): frontend config files, src/components/ui, src/components/layout,
  src/lib, src/stores, src/App.tsx, src/main.tsx, src/index.css
- F1/F2/F3 (page groups): only their own files under src/pages/** and src/components/<domain>/**
- Tests waves own only their test files.
Root files (Makefile, docker-compose.yml, Jenkinsfile, README) owned by the orchestrator.

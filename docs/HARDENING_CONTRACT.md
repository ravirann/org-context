# Production Hardening Contract — IAM, User Management, Live Connectors

PINNED decisions for the hardening wave. All agents read this FIRST. Existing suites
(353 backend / 266 frontend / 14 e2e) MUST stay green: `CE_AUTH_MODE=demo` (default)
preserves current behavior exactly.

## 1. Auth model (dual, mode-gated)

- `Settings.auth_mode: Literal["demo","oidc"] = "demo"` (env `CE_AUTH_MODE`), plus
  `secret_key` (env `CE_SECRET_KEY`, default "dev-secret-change-me"), `oidc_issuer`,
  `oidc_client_id`, `oidc_client_secret`, `oidc_redirect_url`
  (default http://localhost:8000/v1/auth/callback), `session_ttl_hours=12`,
  `allowed_email_domains: list[str] = []` (empty = allow any).
- `get_current_user` accepts EITHER (checked in this order):
  1. `Authorization: Bearer <api-key>` — unchanged (agents, CLI, MCP, demo UI).
  2. `ce_session` httpOnly cookie — HS256 JWT `{sub: user_id, email, exp, iat}` signed with
     `secret_key`. Invalid/expired cookie → fall through → 401.
  In `oidc` mode both still work (API keys are for programmatic access), but the UI drives
  cookie sessions.
- OIDC: **Authorization Code flow via backend** (confidential client), issuer discovery from
  `{issuer}/.well-known/openid-configuration` fetched lazily and cached. PKCE not required
  (confidential client) — `state` param signed+verified (JWT, 10min exp) to prevent CSRF.
- JIT provisioning on first login: match `users.email`; if absent and email domain allowed →
  create user (role=viewer, team=None, external_subject=`sub`, is_active=true, audit
  "auth.jit_provision"). Inactive users are rejected with 403 at login and at every request.

### New endpoints (module `api/routes/auth.py`)
- `GET /v1/auth/login` (no auth) → 200 `{authorization_url}` in oidc mode (the SPA redirects
  itself); 409 `{detail:"auth_mode is demo"}` in demo mode.
- `GET /v1/auth/callback?code=&state=` (no auth) → exchanges code, validates ID token
  (signature via issuer JWKS, aud, exp), JIT-provisions, sets `ce_session` cookie
  (httpOnly, SameSite=Lax, path=/), then 302 redirect to the UI origin (first CORS origin).
- `POST /v1/auth/logout` → clears cookie → 204.
- `GET /v1/auth/session` (no auth) → `{auth_mode, authenticated: bool, user: MeOut|null}` —
  the SPA bootstraps from this.
- `GET /v1/me` unchanged.
- CORS: `allow_credentials=True` (already same-site-friendly origins).

## 2. User & access management (module `api/routes/admin.py` — extend)

All [admin], all audited (`user.create`, `user.update`, `user.deactivate`, `team.create`,
`team.update`, `team.delete`, `api_key.create`, `api_key.revoke`):
- `POST /v1/admin/users` `{email, name, role, team_id?}` → 201 AdminUser (409 on duplicate email)
- `PATCH /v1/admin/users/{id}` `{name?, role?, team_id?, is_active?}` → AdminUser
  (admin cannot deactivate or demote THEMSELVES → 400)
- `POST /v1/admin/teams` `{name, description?}` → 201; `PATCH /v1/admin/teams/{id}`;
  `DELETE /v1/admin/teams/{id}` → 204 (members' team_id set NULL; docs' team ACLs untouched)
- `POST /v1/admin/api-keys` `{label, kind: api|mcp, user_id, role_hint?}` → 201
  `{id, label, kind, user_name, raw_key}` — **raw key returned exactly once**; store sha256.
  Raw format: `ce_<kind>_<32 hex>`.
- `POST /v1/admin/api-keys/{id}/revoke` → key `is_active=false` → ApiKeyOut.
- Pydantic models for these live IN `admin.py`/`auth.py` (do NOT edit `api/schemas.py` —
  parallel-agent conflict avoidance; import shared ones from schemas, add new ones locally).

## 3. Live connectors (owner: connectors agent)

- `sources.sync_state JSONB NOT NULL DEFAULT '{}'` — incremental cursors
  (e.g. `{"pr_cursor": "2026-07-01T00:00:00Z", "issues_cursor": ...}`). Updated after each
  successful sync; demo connectors ignore it.
- `source.config` gains `{"mode": "demo"|"live", ...credentials & scope}`; **mode defaults to
  demo** everywhere (seeds unchanged). Live configs per type:
  - github: `{mode, token, org, repos: [..] , api_url?="https://api.github.com"}` — syncs PRs
    (+bodies+review comments as doc_type pr), repo docs (README/*.md via contents API,
    doc_type code), issues (doc_type ticket). ACL: private repo → team-restricted (config
    `team_name`), public → acl_public.
  - jira: `{mode, base_url, email, api_token, jql?}` — issues updated since cursor → ticket.
  - slack: `{mode, token, channels: [..]}` — conversations.history since cursor → message.
  - confluence: `{mode, base_url, email, api_token, space_keys: [..]}` — CQL lastModified →
    doc.
- Framework: `connectors/live/` package (`http.py` shared httpx.AsyncClient helper with:
  bearer/basic auth, 3x retry w/ exponential backoff on 429/5xx honoring Retry-After,
  30s timeout, structlog request logging). Each live connector implements the SAME
  `Connector` protocol (`fetch(source) -> list[RawItem]`) reading+writing cursors via
  `source.sync_state` (fetch may mutate `source.sync_state`; pipeline persists it).
  `get_connector(source_type, config)` routes demo|live by `config["mode"]`.
- GET /v1/sources must MASK credentials: config values whose keys are in
  {token, api_token, client_secret, password} → `"•••" + last4`. PATCH accepts full config;
  masked sentinel values ("•••…") are ignored (keep stored secret).
- NO real network in tests: httpx.MockTransport fixtures with realistic GitHub/Jira/Slack/
  Confluence payloads; cursor advance + idempotent re-sync + 429-retry + auth-failure
  (→ sync_status=error, last_error) all covered.

## 4. Migrations (dictated — do not deviate)
- IAM agent: `backend/alembic/versions/0002_auth.py` — revision="0002_auth",
  down_revision="730e5b7a2104": users.external_subject (str nullable, unique),
  users.last_login_at (ts nullable).
- Connectors agent: `backend/alembic/versions/0003_connector_state.py` —
  revision="0003_connector_state", down_revision="0002_auth": sources.sync_state JSONB
  NOT NULL server_default '{}'.
- Both also add the columns to `storage/models.py`?? NO — models.py edited ONLY by the IAM
  agent (adds all three columns in one pass to avoid conflicts; connectors agent relies on it).

## 5. Frontend (single agent owns all frontend changes)
- `lib/api.ts`: `credentials: "include"`; Authorization header only when an apiKey is set.
- Boot: query `GET /v1/auth/session`. demo mode → current behavior (key switcher).
  oidc mode → if unauthenticated, full-screen **/login page** ("Sign in with SSO" button →
  fetch authorization_url → window.location). Logout button in user menu (POST logout).
- Admin page upgrades: Users tab → create-user dialog, inline role select (PATCH),
  activate/deactivate toggle, team assign; Teams tab → create/rename/delete; API keys tab →
  create-key dialog (kind, label, user) showing raw key ONCE with copy button + revoke action.
- Sources page: config editor dialog (JSON-ish form: mode toggle demo/live + per-type
  credential fields, masked secrets left untouched unless replaced), sync_state cursor display.
- New types colocated or added to `lib/types.ts` (FE agent owns it this wave).

## 6. Local IAM (IAM agent owns)
- docker-compose.yml: add `keycloak` service (quay.io/keycloak/keycloak:26.0, `start-dev
  --import-realm`, port 8081:8080, admin/admin) + volume mount `./backend/keycloak/realm-org-context.json`.
- `backend/keycloak/realm-org-context.json`: realm `org-context`, confidential client
  `org-context-api` (secret `dev-client-secret`, redirect http://localhost:8000/v1/auth/callback
  + http://localhost:8010/v1/auth/callback), demo users ava@demo.dev etc. password `demo1234`.
- docs/IAM.md: how to run oidc mode locally (compose up keycloak; CE_AUTH_MODE=oidc,
  CE_OIDC_ISSUER=http://localhost:8081/realms/org-context, client id/secret; UI login flow;
  production notes: Okta/Auth0/Google config table, secret storage, cookie Secure flag).

## 7. File ownership (hard rule)
- **IAM-BE agent**: config/settings.py, api/deps.py, api/routes/auth.py, api/routes/__init__.py,
  api/app.py (CORS credentials + auth router), storage/models.py (3 new columns),
  alembic 0002, backend/keycloak/, docker-compose.yml, docs/IAM.md, observability nothing,
  tests: tests/api/test_auth_oidc.py, tests/unit/test_session_jwt.py.
- **UserMgmt-BE agent**: api/routes/admin.py, storage/repositories.py (add helpers only —
  append, don't reorder), tests/api/test_user_management.py.
- **Connectors agent**: connectors/live/**, connectors/base.py (mode routing), ingestion/pipeline.py
  (persist sync_state), api/routes/sources.py (masking), alembic 0003, seeds NOT touched,
  tests/unit/test_live_connectors.py, tests/integration/test_live_sync.py, docs/CONNECTORS.md.
- **Frontend agent**: frontend/src/** (pages/login.tsx, admin, sources, lib, stores, layout user
  menu), frontend/tests/** new files + may extend fixtures-admin.ts, e2e NOT touched.
- Makefile/README/final docs: orchestrator.
Every agent: ruff+mypy / tsc+eslint clean, full existing suite still green (backend agents run
`uv run pytest -q --no-cov` at minimum; coverage gate run by orchestrator at the end).

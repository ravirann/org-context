# Cross-module interfaces (PINNED — implement/consume EXACTLY these)

All async functions take an `AsyncSession` first. ORM types from `context_engine.storage.models`.

## retrieval (owner: BR)
```python
# context_engine/retrieval/service.py
@dataclass
class SearchFilters:
    doc_types: list[str] | None = None
    source_ids: list[str] | None = None      # UUID strings
    repo: str | None = None
    service: str | None = None
    status: str | None = None
    page: int = 1
    page_size: int = 20

@dataclass
class SearchHit:
    document_id: str; chunk_id: str; title: str; doc_type: str; source_name: str
    snippet: str; score: float; url: str; repo: str | None; service: str | None
    status: str; freshness_score: float; authority_score: float
    last_activity_at: datetime

@dataclass
class SearchPage:
    items: list[SearchHit]; total: int; acl_blocked_count: int

async def search_chunks(session, user: User, query: str, filters: SearchFilters) -> SearchPage
```
ACL is enforced inside `search_chunks` via `repositories.acl_filter_clause(user)`;
`acl_blocked_count` = matching docs hidden from this user. Hybrid scoring per ARCHITECTURE.md
using weights from app_settings `retrieval_weights`.

## reasoning (owner: BR)
```python
# context_engine/reasoning/intent.py
def classify_intent(task: str) -> IntentType          # storage.models IntentType enum

# context_engine/reasoning/scoring.py
def freshness_score(last_activity_at: datetime, window_days: int) -> float
def packet_confidence(selected: list[SearchHit], open_conflicts: int) -> float

# context_engine/reasoning/conflicts.py
async def conflicts_for_documents(session, document_ids: list[str]) -> list[Conflict]
async def detect_and_persist_conflicts(session) -> int   # scans topic_keys, upserts Conflict rows
```

## context_compiler (owner: BR)
```python
# context_engine/context_compiler/compiler.py
async def compile_context(
    session, user: User, task: str,
    repo: str | None = None, service: str | None = None,
    max_tokens: int | None = None,
) -> ContextPacket        # persisted + flushed ORM row, all JSONB fields populated
```

## ingestion (owner: BI)
```python
# context_engine/ingestion/pipeline.py
async def sync_source(session, source: Source) -> int    # returns upserted doc count; updates
                                                          # source.sync_status/last_synced_at/
                                                          # document_count; (re)indexes chunks
# context_engine/ingestion/actors.py
@dramatiq.actor(max_retries=3)
def sync_source_actor(source_id: str) -> None             # opens own session via session_scope
```
Connectors: `context_engine/connectors/base.py` defines
`class Connector(Protocol): source_type: ClassVar[str]; async def fetch(self, source: Source) -> list[RawItem]`
with `RawItem` dataclass (external_id, doc_type, title, content, url, author_email, repo,
service, team_name, acl (public/team_names/user_emails), topic_key, metadata, last_activity_at).
Registry: `get_connector(source_type) -> Connector`. Demo connectors return deterministic
fixture data (offline, no network).

## evals (owner: BE)
```python
# context_engine/evals/harness.py
async def run_eval(session, mode: EvalMode, triggered_by: uuid.UUID | None = None) -> EvalRun
# creates EvalRun(running) -> executes golden tasks (baseline = naive keyword retrieval w/o
# reranking/authority/conflict handling; context_engine = compile_context path) -> EvalResults
# -> summary (incl. regression vs previous completed run using eval_thresholds) -> completed.

# context_engine/evals/actors.py
@dramatiq.actor(max_retries=0)
def run_eval_actor(eval_run_id: str, mode: str) -> None   # own session; picks up pre-created
                                                          # EvalRun row and executes it
async def execute_eval_run(session, eval_run: EvalRun) -> EvalRun   # in harness.py, used by both
```

## api (owner: BA)
- `context_engine/api/app.py`: `def create_app() -> FastAPI` (factory; wires middleware,
  routers, /healthz). `app = create_app` NOT called at import (uvicorn --factory).
- `context_engine/api/deps.py`: `get_current_user` (Bearer key -> repositories.get_user_by_api_key,
  401 otherwise), `require_roles(*roles)` dependency factory (403).
- `context_engine/api/schemas.py`: every request/response model from API_CONTRACT.md.
- Enqueue rule: POST /v1/sources/{id}/sync → `sync_source_actor.send(str(id))`;
  POST /v1/evals/run → create EvalRun(status=running) then `run_eval_actor.send(str(run.id), mode)`.
  With StubBroker (CE_ENV=test) actors must ALSO be executed inline by the API layer? NO —
  in tests the StubBroker + worker execution is triggered by test helpers; API only `.send()`s.

## mcp_server / cli (owner: BM)
- `context_engine/mcp_server/server.py`: FastMCP("org-context") with tools
  `compile_context(task, repo?, service?, max_tokens?)`, `search_context(query, repo?, service?)`,
  `get_document(document_id)`, `report_feedback(type, context_packet_id?, document_id?, comment?)`.
  Auth: env CE_MCP_TOKEN (raw key, kind=mcp) resolved to a user once at tool-call time; ACL
  enforced by reusing retrieval/compiler. Entrypoints: `ctx serve-mcp` (stdio) and
  `ctx serve-mcp --http` (streamable-http on :8765).
- `context_engine/cli/main.py`: Typer app `app`; `def app_entry() -> None` wraps app() (pyproject
  script `ctx`). Commands: `seed [--reset|--if-empty]`, `sync <source-name|--all>`,
  `search <query> [--repo --service --json]`, `compile <task> [--repo --service --max-tokens --json]`,
  `eval run [--mode]` + `eval report [run-id]`, `serve-api`, `serve-mcp [--http]`.
  CLI acts as the admin user (looks up demo-admin-key user; explicit --api-key override).
```

## Shared utilities (already exist — REUSE, do not duplicate)
- `context_engine.indexing.embeddings.embed_text(text) -> list[float]` (384-dim deterministic)
- `context_engine.indexing.tokens.estimate_tokens(text) -> int`
- `context_engine.storage.repositories`: acl_filter_clause, get/set_setting, write_audit,
  get_user_by_api_key
- `context_engine.observability.logging.get_logger`, `.langfuse_client`, `.worker` (broker)

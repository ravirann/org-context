# Phase 3 Contract — Production-grade Ingestion & Retrieval

PINNED decisions. All agents read this first. Existing gates must stay green
(424 backend / 293 frontend / 14 e2e; coverage ≥85 both sides). Agents may update an
existing test ONLY when its asserted behavior intentionally changed here — never weaken
ACL tests. Evals `baseline.py` stays naive on purpose (it's the comparison baseline).

## A. Embeddings (owner: EMB agent)

`indexing/embeddings.py` becomes a provider registry. Column stays `Vector(384)` — every
provider MUST emit 384 dims.

```python
class EmbeddingProvider(Protocol):
    name: str          # "deterministic" | "openai" | "fastembed"
    model: str
    dim: int           # always 384
    async def embed_texts(self, texts: list[str]) -> list[list[float]]: ...

def get_embedding_provider() -> EmbeddingProvider   # from settings, cached; reset_provider_cache()
async def embed_texts(texts: list[str]) -> list[list[float]]   # via configured provider, batches of 64
async def embed_query(text: str) -> list[float]                # single-text convenience
def embed_text(text: str) -> list[float]   # KEEP: sync deterministic impl (seeds/tests/back-compat)
```

- Providers: **deterministic** (default; wraps existing hash impl), **openai**
  (`text-embedding-3-small`, request `dimensions: 384`, httpx w/ retry/backoff on 429/5xx,
  API key required; batched ≤64), **fastembed** (`BAAI/bge-small-en-v1.5`, 384-dim, LAZY
  import behind optional dependency extra `local-embeddings`; clear RuntimeError if extra
  not installed). L2-normalize all outputs.
- Settings (EMB agent owns config/settings.py additions): `embedding_provider: str =
  "deterministic"` (env CE_EMBEDDING_PROVIDER), `openai_api_key: str = ""`,
  `openai_base_url: str = "https://api.openai.com/v1"`, `embedding_batch_size: int = 64`.
- pyproject: `[project.optional-dependencies] local-embeddings = ["fastembed>=0.4"]`.
- **Reindex path**: `indexing/reindex.py` `async def reindex_all(session, batch=200) -> int`
  (re-chunk+re-embed all active docs, set chunks.embedding_version) + dramatiq actor
  `reindex_actor()` (indexing/actors.py, registered for worker lazy-import like others) +
  CLI `ctx reindex` (EMB agent may edit cli/main.py — sole owner this wave).
- `embedding_version` string = f"{provider.name}/{provider.model}" written on chunks
  (column added by ING agent — build against it).
- **API**: new `api/routes/system.py` — `GET /v1/system/info` [admin] →
  `{embedding: {provider, model, dim}, auth_mode, queue_depth: int|null (redis LLEN
  dramatiq:default, null on error), version: "0.3.0"}`. EMB agent registers it in
  routes/__init__.py (sole owner of that file this wave).
- Tests: tests/unit/test_embedding_providers.py (deterministic unchanged/normalized;
  openai via httpx.MockTransport incl. batching, retry, dim check; fastembed skipped via
  importorskip), tests/integration/test_reindex.py (reindex swaps embedding_version,
  chunk counts stable), tests/api/test_system_info.py.

## B. Ingestion robustness (owner: ING agent)

- **models.py (ING agent is sole owner)** — add:
  - `SyncRun`: id UUID, source_id FK (cascade), trigger enum(manual|scheduled),
    status enum(running|ok|error), started_at, finished_at nullable, docs_upserted int,
    docs_skipped int, docs_pruned int, chunks_indexed int, errors JSONB list
    [{external_id, error}] (cap 50), created_at/updated_at.
  - `SearchEvent`: id UUID, user_id FK nullable, query str, result_count int,
    acl_blocked_count int, took_ms float, cache_hit bool, top_document_ids JSONB,
    created_at. Index on (query), (created_at).
  - `Document.content_hash: str | None` (sha256 hex of title+"\n"+content).
  - `Chunk.embedding_version: str` default "deterministic/sha256-v1", server_default same.
- **Migration `0004_ops`** (revision="0004_ops", down_revision="0003_connector_state"):
  all of the above.
- **pipeline.py**:
  - Create SyncRun(running) at start; per-item try/except (record error, continue);
    >50% item failures → source.sync_status=error; finalize SyncRun (ok|error, counts).
  - Unchanged-content skip: compute content_hash before upsert; if matches stored AND
    chunks exist → update freshness/acl/last_activity only, docs_skipped++ (no re-embed).
  - Pruning: Connector protocol gains OPTIONAL
    `async def list_active_external_ids(self, source) -> list[str] | None` (default None
    via base). Demo connectors + live github implement. When non-None: docs of that source
    absent from the list → status=deprecated, docs_pruned++, audit "source.prune".
  - Concurrency lock: redis `SET ce:sync-lock:{source_id} 1 NX EX 600` (redis.asyncio from
    settings.redis_url); if locked, log+return without a SyncRun. Release in finally.
    Redis unavailable → proceed without lock (log warning).
  - On successful sync: `INCR ce:search:gen` (retrieval cache invalidation; ignore redis
    errors).
  - index_document (chunking.py): use `await embed_texts([...])` batch API + write
    embedding_version from EMB module constant `current_embedding_version()` (EMB exposes).
- **Scheduler**: `ingestion/scheduler.py` — `async def run_scheduler(poll_seconds=60)`:
  every tick, enabled sources where last_synced_at is NULL or older than
  config.get("sync_interval_minutes", app_settings ingestion default 30) →
  `sync_source_actor.send(str(id))` (trigger recorded as scheduled via actor kwarg
  `trigger="scheduled"`). Entrypoint `python -m context_engine.ingestion.scheduler`,
  scripts/start-scheduler.sh, compose service `scheduler` (same image/env as worker) —
  ING agent owns the compose edit this wave.
- **API (sources.py)**: `GET /v1/sources/{id}/sync-runs` → `{items: [SyncRunOut ...]}` 20
  newest; SourceDetail gains `last_sync_run: SyncRunOut | null`. Response models colocated.
- **Seeds**: append sync_runs demo rows (~2 per source, one error w/ realistic message) and
  ~30 search_events (incl. repeated zero-result queries like "kafka partition rebalance
  runbook", "grpc deadline budget") — deterministic.
- Tests: extend/add tests/integration/test_sync_runs.py (per-item isolation, skip-unchanged,
  pruning, lock skip via fakeredis-style monkeypatch or real redis :6380, sync_run rows,
  trigger field), tests/unit/test_scheduler.py (due-source selection logic as pure fn).

## C. Retrieval quality (owner: RET agent) — retrieval/**, api/routes/context_debt.py

- **FTS recall**: `websearch_to_tsquery('english', q)`; when it yields < page_size matches
  and q has >1 lexeme, UNION with an OR-of-lexemes to_tsquery (sanitize lexemes via
  plainto per-word). Snippets unchanged.
- **Score normalization**: min–max normalize the vector and fts legs across the candidate
  set (guard zero-range) BEFORE applying weights — stabilizes weight semantics.
- **Phrase/title boost**: +0.08 (post-normalization, cap score at 1.0) when title ILIKE
  %q% or chunk contains the exact phrase (case-insensitive), q len ≥ 2 words.
- **MMR diversification**: after dedupe-to-best-chunk-per-doc, reorder top candidates with
  MMR (relevance vs max cosine to already-picked, pure-python dot on stored embeddings),
  lambda = get_setting("retrieval_extras").get("mmr_lambda", 0.7). Applied before
  pagination.
- **Redis cache**: retrieval/cache.py — key = sha256(f"{gen}|{user.id}|{user.role}|
  {user.team_id}|{query}|{sorted filters}") where gen = GET ce:search:gen (default 0);
  value = JSON SearchPage; TTL get_setting("retrieval_extras").get("cache_ttl_seconds",60).
  Graceful bypass on redis errors. BYPASS entirely when settings.env == "test" unless test
  opts in (keeps existing tests deterministic).
- **Telemetry**: after each search, INSERT SearchEvent (query, user_id, result_count,
  acl_blocked_count, took_ms, cache_hit, top_document_ids ≤10). Flush, don't commit.
- **context_debt.py**: repeated_misses now = zero-result SearchEvents grouped by query
  (count desc, top 10), replacing the feedback proxy.
- Tests: extend tests/integration/test_retrieval.py (multi-term recall via OR fallback,
  normalization ordering, phrase boost, MMR reduces same-topic adjacency), new
  tests/integration/test_search_cache.py (opt-in cache: hit/miss, gen bump invalidates,
  ACL isolation — engineer's cache never served to viewer), test_search_events assertions,
  context_debt updated test. May adjust existing retrieval/compiler/eval tests minimally
  where ordering legitimately changed.

## D. Frontend + docs (owner: FE agent) — frontend/**, may touch lib/types.ts additively
- Sources page: per-source expandable **Sync history** (GET /v1/sources/{id}/sync-runs):
  status dot, trigger badge, started timeAgo, duration, upserted/skipped/pruned/chunks
  counts, expandable errors list; SourceDetail.last_sync_run summary inline in the row.
- Admin → System tab: card from GET /v1/system/info (embedding provider/model/dim badge,
  auth mode, queue depth, version) with PermissionDenied handling.
- Context Debt: no shape change (repeated_misses same shape, now real).
- Types for SyncRun/SystemInfo; tests for the new UI (sync history expand, error list,
  system card, 403) keeping thresholds ≥85/85/85/75.

## Sequencing / shared-file owners this wave
models.py+migration+compose+seeds+sources.py+pipeline+chunking → ING ·
embeddings/reindex/system/settings.py/pyproject/cli/main.py/routes/__init__.py → EMB ·
retrieval+cache+context_debt → RET · frontend → FE.
EMB's `embed_texts`/`current_embedding_version()` and ING's models land early; RET/ING
build against the pinned signatures above regardless of landing order.
All: ruff+mypy clean; full backend suite `--no-cov` green before finishing (orchestrator
runs the coverage gate + e2e at the end).

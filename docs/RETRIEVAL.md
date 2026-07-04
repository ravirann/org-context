# Retrieval

Hybrid, ACL-enforced search over document chunks. Combines dense vector similarity,
full-text search (FTS), freshness, and authority into a single relevance score, then
diversifies and paginates. Everything lives in `context_engine/retrieval/`:

| Module        | Responsibility                                                    |
| ------------- | ----------------------------------------------------------------- |
| `service.py`  | Orchestration: candidates → SQL pre-cut → Python scoring → MMR → page. Cache + telemetry. |
| `mmr.py`      | Pure Maximal-Marginal-Relevance reranker (no I/O, unit-tested).    |
| `cache.py`    | Best-effort, per-user Redis result cache with ACL-safe keys.       |

The public entry point is stable:

```python
async def search_chunks(session, user, query, filters) -> SearchPage
```

All normalization, diversification, caching, and telemetry are internal — callers
(`api/routes/search.py`, `context_compiler/compiler.py`) are unaffected.

## Scoring pipeline

```
                          query, filters, user
                                   │
              ┌────────────────────┴─────────────────────┐
              │ 0. Cache lookup (per-user key)            │  hit → record cache_hit
              │    key = sha256(gen│user│role│team│q│flt) │        SearchEvent, return
              └────────────────────┬─────────────────────┘
                                   │ miss
              ┌────────────────────┴─────────────────────┐
              │ 1. Candidate selection (SQL)              │
              │    websearch_to_tsquery('english', q)     │
              │      OR  vector top-N (cosine distance)   │
              │    OR-fallback: if websearch matches      │
              │      < page_size docs and q has ≥2        │
              │      lexemes, UNION to_tsquery(l1|l2|…)    │
              └────────────────────┬─────────────────────┘
                                   │
              ┌────────────────────┴─────────────────────┐
              │ 2. SQL pre-cut                            │
              │    raw weighted score orders rows;        │
              │    take top MAX_SCAN_ROWS (1000).         │
              │    Fetch: chunk, doc, source, raw legs,   │
              │           stored embedding.               │
              └────────────────────┬─────────────────────┘
                                   │
              ┌────────────────────┴─────────────────────┐
              │ 3. Python re-scoring                      │
              │    a. min–max normalize vec + fts legs    │
              │       across the candidate set            │
              │    b. weighted sum with freshness +       │
              │       authority (unnormalized, already    │
              │       in [0,1])                            │
              │    c. phrase/title boost (+0.08, cap 1.0) │
              └────────────────────┬─────────────────────┘
                                   │
              ┌────────────────────┴─────────────────────┐
              │ 4. Dedupe → best chunk per document       │
              │    (total = #distinct documents)          │
              └────────────────────┬─────────────────────┘
                                   │
              ┌────────────────────┴─────────────────────┐
              │ 5. MMR reorder over top 3·page_size       │
              │    window (relevance vs. diversity)       │
              └────────────────────┬─────────────────────┘
                                   │
              ┌────────────────────┴─────────────────────┐
              │ 6. Paginate + build snippets              │
              └────────────────────┬─────────────────────┘
                                   │
                   cache set  +  SearchEvent telemetry
```

### 1. Candidates & FTS recall

The candidate set is `chunks matching the FTS query OR ranking in the vector top-N`
(`VECTOR_CANDIDATE_LIMIT = 200` by cosine distance). The FTS query is
`websearch_to_tsquery('english', q)` — it honors quotes, `-negation`, and `or`, and is
stricter than the old `plainto_tsquery`.

**OR fallback.** `websearch_to_tsquery` ANDs bare terms, so a multi-word query can
match nothing even when each word matches something. When the primary websearch query
matches fewer than `page_size` documents *and* the query has ≥2 lexemes, we UNION an
OR-of-lexemes `to_tsquery('english', 'l1 | l2 | …')`. Lexemes are the distinct
alphanumeric tokens (>1 char, lowercased) of the query. The `ts_rank` leg is then
computed against the combined `websearch || or_query` tsquery so recalled rows get a
real (non-zero) FTS score. Snippets are unchanged.

The empty/whitespace query short-circuits the FTS/vector legs entirely (`match = TRUE`,
`vec = fts = 0`); recent + authoritative documents win.

### 2. SQL pre-cut

To stay sane on large tables, SQL still orders rows by the **raw** weighted score
(`w_vec·vec + w_fts·fts + w_fresh·freshness + w_auth·authority`) and takes the top
`MAX_SCAN_ROWS = 1000`. This is only a pre-cut — final scoring happens in Python. The
row also carries the raw `vec` and `fts` legs and the stored chunk `embedding` (needed
for MMR).

### 3. Score normalization

Final scoring moves to Python so weight semantics are stable across queries:

- The **vector** and **fts** legs are **min–max normalized** across the candidate set
  to `[0, 1]` (zero-range is guarded → all zeros). Freshness and authority are already
  document-level `[0, 1]` scores and are used as-is.
- Normalized legs are combined with the configured weights.
- **Phrase/title boost:** `+0.08` (capped at `1.0`) when the query is ≥2 words and the
  exact phrase appears in the document title or the chunk content (case-insensitive).

Weights come from the `retrieval_weights` app setting; defaults:

| Leg       | Default weight |
| --------- | -------------- |
| vector    | 0.45           |
| fts       | 0.25           |
| freshness | 0.15           |
| authority | 0.15           |

Missing/partial settings fall back per-key to these defaults.

### 4. Dedupe

Rows are sorted by `(score, last_activity_at, chunk_id)` descending and reduced to the
**best-scored chunk per document**. `SearchPage.total` counts distinct documents.

### 5. MMR diversification

After dedupe, the top `3 · page_size` candidates are reordered with **Maximal Marginal
Relevance** (`mmr.py`, pure & unit-tested):

```
pick = argmax_i [ λ · relevance_i − (1 − λ) · max_{j∈picked} cos(emb_i, emb_j) ]
```

- `λ = 1.0` → pure relevance ordering (no diversification).
- `λ = 0.0` → pure novelty.
- `λ` comes from `retrieval_extras.mmr_lambda` (default `0.7`).

Cosine similarity is a plain-Python dot product over the stored chunk embeddings
(defensively normalized). Rows with a missing embedding contribute zero similarity
(treated as maximally diverse). MMR runs **before** pagination, so page 1 is the
diversified head. Because MMR trades relevance for diversity, the emitted `score`
values are no longer guaranteed strictly monotonic across a page — the *ordering* is
the MMR ordering, and `score` remains the item's relevance.

### 6. Pagination & snippets

The reordered, deduped list is sliced by `(page, page_size)` and each hit gets a
~240-char snippet centered on the first query-term hit (`build_snippet`).

## ACL isolation

ACL is enforced **in SQL** via `repositories.acl_filter_clause(user)` on every leg —
admins see everything; everyone else needs `acl_public` OR a team grant OR a direct
user grant (JSONB containment). Hidden-but-matching documents never appear in results.

`acl_blocked_count` is computed exactly as before: the same match predicate is counted
once with and once without the ACL clause; the difference is the blocked count. When
`> 0`, an `acl.blocked` audit row is written (`resource_type="search"`, detail carries
the raw query + blocked count) and logged. Admin searches never write an ACL audit.

The **cache key embeds the user's id, role, and team**, so a document one user can see
can never be served from another user's cache entry — ACL isolation holds by
construction, not by cache-content inspection. An engineer and a viewer issuing the
identical query produce different keys and each run a fresh DB query.

## Cache semantics (`cache.py`)

- **Key:** `sha256(f"{gen}|{user.id}|{user.role}|{user.team_id}|{query}|{filters}")`,
  prefixed `ce:search:`. `gen = GET ce:search:gen` (default `0`). Filters are
  canonicalized to sorted-key JSON with sorted list values so equivalent filter sets
  collide intentionally.
- **Value:** the JSON-serialized `SearchPage`. `SearchHit.last_activity_at` round-trips
  as ISO-8601.
- **TTL:** `retrieval_extras.cache_ttl_seconds` (default `60`).
- **Invalidation:** a successful sync `INCR ce:search:gen` (owned by the ingestion
  pipeline). Bumping the generation changes every key at once, so a reindex or fresh
  sync transparently invalidates all cached results.
- **Best-effort:** every Redis op is wrapped; any connectivity error or a corrupted
  (non-JSON) entry results in a silent **cache bypass / graceful miss**, never a failed
  search.
- **Test hermeticity:** disabled when `settings.env == "test"` (`enabled(settings)`
  returns `env != "test"`). The dedicated cache tests opt in by monkeypatching
  `cache.enabled → True` against the real Redis at `settings.redis_url` (:6380).

## Telemetry (`SearchEvent`)

Every search — **including cache hits** — records a `SearchEvent` row (flushed, not
committed):

| Field               | Meaning                                              |
| ------------------- | ---------------------------------------------------- |
| `query`             | Raw query string.                                    |
| `user_id`           | Requesting user (nullable).                           |
| `result_count`      | `SearchPage.total` (distinct documents).             |
| `acl_blocked_count` | Documents hidden by ACL for this query.              |
| `took_ms`           | Wall time via `time.perf_counter()`.                 |
| `cache_hit`         | `True` when served from the Redis cache.             |
| `top_document_ids`  | Up to 10 returned document ids (page order).         |

On a cache hit the results come from Redis but a fresh, short DB write still records
the event with `cache_hit=True` — so telemetry is complete regardless of caching.

**Context-debt `repeated_misses`** is derived from this table: zero-result searches
(`result_count == 0`) grouped by `lower(query)`, ordered by count descending, top 10,
shaped `{query, count}`. This replaces the old `missing_context` feedback proxy.

## Tuning knobs

| Setting / constant                          | Location                      | Default   |
| ------------------------------------------- | ----------------------------- | --------- |
| `retrieval_weights` (vector/fts/…)          | `app_settings`                | see table |
| `retrieval_extras.mmr_lambda`               | `app_settings`                | `0.7`     |
| `retrieval_extras.cache_ttl_seconds`        | `app_settings`                | `60`      |
| `VECTOR_CANDIDATE_LIMIT`                     | `service.py`                  | `200`     |
| `MAX_SCAN_ROWS`                              | `service.py`                  | `1000`    |
| `PHRASE_TITLE_BOOST`                         | `service.py`                  | `0.08`    |
| `MMR_WINDOW_MULTIPLIER` (× page_size)        | `service.py`                  | `3`       |
| `TOP_DOCUMENT_IDS_CAP`                       | `service.py`                  | `10`      |
| `ce:search:gen`                              | Redis (bumped by sync)        | `0`       |
```

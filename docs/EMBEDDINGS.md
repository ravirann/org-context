# Embeddings

The context engine embeds chunks and queries through a **provider registry**
(`context_engine.indexing.embeddings`). Every provider emits **384-dimensional,
L2-normalized** vectors so the `chunks.embedding` `Vector(384)` column stays valid
regardless of which provider is active. The active provider is chosen from settings
and cached process-wide.

## Providers

| Provider        | `name`          | Model                       | Needs           | Notes |
|-----------------|-----------------|-----------------------------|-----------------|-------|
| Deterministic   | `deterministic` | `sha256-v1`                 | nothing         | Default. Offline, stable hash-based vectors. Backs seeds and tests. |
| OpenAI          | `openai`        | `text-embedding-3-small`    | `CE_OPENAI_API_KEY` | Requests `dimensions: 384`; batches ≤ `CE_EMBEDDING_BATCH_SIZE`; retries 429/5xx with exponential backoff. |
| fastembed       | `fastembed`     | `BAAI/bge-small-en-v1.5`    | `local-embeddings` extra | Local CPU model, 384-dim. Lazy-imported; sync model run in a thread. |

The **embedding version** string written on every chunk is
`f"{provider.name}/{provider.model}"` — e.g. `deterministic/sha256-v1`,
`openai/text-embedding-3-small`, `fastembed/BAAI/bge-small-en-v1.5`. It is exposed
via `current_embedding_version()` and stored in `chunks.embedding_version`.

## Configuration

All settings use the `CE_` env prefix (see `config/settings.py`):

| Setting | Env | Default |
|---------|-----|---------|
| `embedding_provider` | `CE_EMBEDDING_PROVIDER` | `deterministic` |
| `openai_api_key`     | `CE_OPENAI_API_KEY`     | `""` |
| `openai_base_url`    | `CE_OPENAI_BASE_URL`    | `https://api.openai.com/v1` |
| `embedding_batch_size` | `CE_EMBEDDING_BATCH_SIZE` | `64` |

## Switching providers

1. Install extras if needed: `uv sync --extra local-embeddings` (fastembed only).
2. Set `CE_EMBEDDING_PROVIDER` (and `CE_OPENAI_API_KEY` for OpenAI).
3. Restart the API/worker so the cached provider is rebuilt (or call
   `reset_provider_cache()` in-process).
4. **Re-index** so existing chunks are re-embedded and stamped with the new version
   (vectors from different providers are not comparable).

Verify the active provider any time via `GET /v1/system/info` (admin) — it reports
`embedding.{provider, model, dim}`.

## Re-index procedure

Switching providers leaves old vectors stale. Re-embed everything:

```bash
# Confirmation prompt (use --yes in automation)
uv run ctx reindex

# Or asynchronously on the worker
python -c "from context_engine.indexing.actors import reindex_actor; reindex_actor.send()"
```

`reindex_all(session, batch=200)` re-chunks and re-embeds all **active** documents in
id-ordered batches, replaces each document's chunks in place, and stamps them with the
current `embedding_version`. It returns the document count and logs progress per batch.
The `reindex_actor` dramatiq actor (`max_retries=0`) wraps it with its own worker
session.

## Cost notes

- **deterministic / fastembed**: free — no API calls. fastembed runs locally on CPU.
- **openai**: billed per token by OpenAI. `text-embedding-3-small` is the cheapest
  small model; batching (≤64 inputs/request) minimizes request overhead. A full
  re-index embeds every chunk of every active document, so estimate cost against total
  chunk-token volume before switching a large corpus.

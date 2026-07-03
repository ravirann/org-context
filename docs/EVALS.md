# Evaluation Harness

The eval harness answers one question continuously: **does the context engine beat naive
retrieval, and is it getting better or worse?**

## Design

- **Golden tasks** (`eval_tasks`): realistic engineering questions ("What is the retry policy
  for payment webhooks?") with `expected_document_ids` (docs a competent teammate would cite)
  and `expected_keywords` (facts the compiled context must contain).
- **Baseline leg**: deliberately naive retrieval — pure Postgres FTS rank, no authority, no
  freshness, no conflict handling, no diversity, top chunks concatenated. (ACL is still
  enforced; we never leak, even in evals.)
- **Engine leg**: the full `compile_context` path — hybrid retrieval, intent-aware rerank,
  conflict resolution, token budgeting, citations.

## Scoring (per task, 0–1)

```
score = 0.40·F1(expected vs retrieved docs)
      + 0.35·keyword coverage of the compiled context
      + 0.15·citations valid (unique markers, all within selected sources)
      + 0.10·token efficiency (1 − tokens/6000)
```

`passed = score ≥ eval_thresholds.min_score` (settings, default 0.5). A run **regresses** when
its average drops more than `regression_delta` (default 0.05) below the previous completed run
of the same mode; per-task drops populate `regressed_task_names`.

## Running

```bash
make eval                      # comparison mode + printed report
cd backend && uv run ctx eval run --mode comparison
uv run ctx eval report         # re-print latest
# or POST /v1/evals/run — executed by the Dramatiq worker; watch it in the Eval Dashboard
```

## Current results on the demo org (deterministic offline embeddings)

| Metric | Baseline | Context engine |
|---|---|---|
| Average score | 0.179 | **0.599** |
| Pass rate | 0 / 10 | **8 / 10** |
| Tokens | 1,898 | 4,582 |

Per-task delta ranges **+0.15 to +0.72**. The two failing tasks (`canary-deploys`,
`pagination-standard`) fail on retrieval recall — their expected docs live in sparsely
connected sources — and are kept failing on purpose so the Eval Dashboard's failure
explanations and the Context Debt views have real material.

Embeddings are deterministic-hash by default (offline, reproducible; no semantic signal —
retrieval weights are FTS-led). Plugging a real embedding provider into
`indexing/embeddings.EmbeddingProvider` is the single highest-leverage quality upgrade.

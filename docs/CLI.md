# `ctx` CLI

Installed by `uv sync` inside `backend/` (entry point `ctx`). All commands act as the demo
admin by default; pass `--api-key <raw-key>` to act as another identity (ACL applies).

```bash
cd backend

uv run ctx seed --reset            # (re)seed the full demo organization
uv run ctx seed --if-empty         # seed only when the database is empty (used by docker)

uv run ctx sync --all              # sync every enabled source through the ingestion pipeline
uv run ctx sync "GitHub"           # sync one source by name

uv run ctx search "webhook retries" --repo payments-api          # ranked hits
uv run ctx search "webhook retries" --json                       # machine-readable

uv run ctx compile "Fix duplicate charge on webhook retry" --service payments-api
uv run ctx compile "..." --json    # full packet JSON (id, citations, scores, risks)

uv run ctx eval run --mode comparison   # baseline vs context engine over golden tasks
uv run ctx eval report                  # report for the latest completed run

uv run ctx serve-api --port 8000   # uvicorn with the app factory
uv run ctx serve-mcp [--http]      # MCP server (stdio, or streamable-http on :8765)
```

JSON output goes to stdout; structured logs go to stderr, so `ctx ... --json | jq` is safe.

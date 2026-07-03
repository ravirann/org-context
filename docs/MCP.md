# MCP Server — agent integration guide

The platform exposes its context engine to coding agents over the
[Model Context Protocol](https://modelcontextprotocol.io). The server reuses the exact same
retrieval, compiler, and ACL code paths as the REST API — an agent can never see documents its
MCP identity is not allowed to read.

## Running

```bash
# stdio (for Claude Code / Claude Desktop and most MCP clients)
cd backend && CE_MCP_TOKEN=demo-mcp-token uv run ctx serve-mcp

# streamable HTTP on :8765
CE_MCP_TOKEN=demo-mcp-token uv run ctx serve-mcp --http
# equivalently: python -m context_engine.mcp_server [--http]
```

Claude Code registration example:

```bash
claude mcp add org-context -e CE_MCP_TOKEN=demo-mcp-token -- \
  uv --directory /path/to/org-context/backend run ctx serve-mcp
```

## Authentication

`CE_MCP_TOKEN` must hold a raw MCP token (an `api_keys` row with `kind=mcp`). The demo seed
provides `demo-mcp-token`, bound to a platform user whose team/role determines document
visibility. Invalid or missing tokens fail every tool call with a ToolError.

## Tools

| Tool | Arguments | Returns |
|---|---|---|
| `compile_context` | `task`, `repo?`, `service?`, `max_tokens?` | JSON context packet: `compiled_context` (markdown with `[S1]`-style citation markers), `selected_sources` + `rejected_sources` (with reasons), `citations`, `conflict_notes`, `acl_notes`, `token_estimate`, `confidence_score`, `risks`, `recommended_tests` |
| `search_context` | `query`, `repo?`, `service?` | JSON hits (`document_id`, `title`, `doc_type`, `snippet`, `score`, `url`) + `acl_blocked_count` |
| `get_document` | `document_id` | JSON document (title, content, type, url, status, freshness/authority scores); ACL-hidden documents return `{"error": ...}` |
| `report_feedback` | `type`, `context_packet_id?`, `document_id?`, `comment?` | `{"status": "recorded", "id": ...}` |

Recommended agent flow: `compile_context` for the work item → act on the packet →
`report_feedback` (`useful` / `irrelevant` / `missing_context` / `stale_context`) so retrieval
quality improves over time. Every compile is persisted and inspectable in the web UI under
**Context Packets**.

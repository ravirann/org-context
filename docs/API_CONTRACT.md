# API Contract — /v1 (FastAPI)

Auth: `Authorization: Bearer <api-key>` on every endpoint (401 without). RBAC: admin-only
endpoints marked [admin]. ACL enforced on all document/search/packet content. Denied single-doc
reads → 404. Role-forbidden actions → 403 `{detail}`.

Pagination convention: `?page=1&page_size=20` → `{"items": [...], "total": int, "page": int,
"page_size": int}`. Common filters are query params. Dates ISO-8601. IDs are UUID strings.
Pydantic response schemas live in `backend/src/context_engine/api/schemas.py` (single module,
shared by routers; mirrored in `frontend/src/lib/types.ts`).

## Dashboard
- `GET /v1/dashboard/summary` →
  `{total_documents, connected_sources, active_repos, active_services, active_users,
    context_packets, agent_runs, failed_agent_runs, stale_documents, conflicting_documents,
    acl_violations_blocked, latest_eval_score}` (all int, latest_eval_score float|null)
- `GET /v1/dashboard/trends?days=30` →
  `{eval_scores: [{date, value}], source_freshness: [{date, value}],
    review_rework: [{date, value}], packets_per_day: [{date, value}]}`

## Context
- `POST /v1/context/compile` body `{task: str, repo?: str, service?: str, max_tokens?: int}`
  → 201 full **ContextPacket** (see DATA_MODEL context_packets; response schema
  `ContextPacketOut` includes all fields + `created_at`, `requested_by_name`)
- `GET /v1/context-packets?repo=&service=&intent=&page=` → paginated `ContextPacketSummary`
  `{id, task, intent, repo, service, token_estimate, confidence_score, agent_outcome,
    requested_by_name, created_at, source_count}`
- `GET /v1/context-packets/{id}` → `ContextPacketOut` + `feedback: list[FeedbackOut]`
  + `agent_run: AgentRunSummary|null`

## Search & documents
- `POST /v1/search` body `{query: str, doc_types?: list, source_ids?: list, repo?: str,
  service?: str, status?: str, page?, page_size?}` → paginated
  `{document_id, chunk_id, title, doc_type, source_name, snippet (highlighted chunk excerpt),
    score, url, repo, service, status, freshness_score, authority_score, last_activity_at}`
  ACL-filtered; also returns top-level `acl_blocked_count: int`.
- `GET /v1/documents/{id}` → `{id, title, content, doc_type, url, status, repo, service,
    source: {id, name, type}, author_name, team_name, topic_key, authority_score,
    freshness_score, last_activity_at, acl: {public, team_names: list[str], user_count: int},
    chunks: [{id, ord, content, token_count}], citations_of: int (usage_count),
    related: [{id, title, doc_type, relation}] (via entity edges),
    conflicts: [{id, topic_key, title, status}],
    packet_usage: [{packet_id, task, created_at, was_selected: bool}]}`

## Relationships
- `GET /v1/relationships/graph?node_types=repo,service&edge_types=owns&q=&limit=300` →
  `{nodes: [{id, type, label, ref, stale: bool, conflicted: bool, degree: int}],
    edges: [{id, source, target, type, weight}]}`
- `GET /v1/relationships/path?from_id=&to_id=` →
  `{path: [{node: {...}, edge: {...}|null}], found: bool}` (BFS shortest path)

## Heatmaps
- `GET /v1/heatmaps/users?from=&to=&team_id=&repo=&service=&metric=commit|pr|review|doc_edit|
  ticket|incident|packet_use|all` →
  `{rows: [{user_id, user_name, team_name, cells: [{day, value}] , total}], days: [str]}`
- `GET /v1/heatmaps/ownership` →
  `{rows: [{key (repo or service), owner_team, doc_count, owner_user_names: list[str],
    coverage_score float, last_activity_at}]}`
- `GET /v1/heatmaps/context-debt` →
  `{rows: [{key, repo, service, team_name, stale_count, missing_owner: bool,
    conflict_count, rejected_count, failed_runs, debt_score float}]}`

## Agent runs
- `GET /v1/agent-runs?agent=&repo=&service=&user_id=&status=&from=&to=&page=` → paginated
  `AgentRunSummary {id, agent_name, task, repo, service, user_name, status, started_at,
    finished_at, context_packet_id}`
- `GET /v1/agent-runs/{id}` → full run: summary fields + `{plan, changed_files, test_output,
    pr_url, reviewer_comments, langfuse_trace_url: str|null, context_packet: ContextPacketOut|null}`

## Evals
- `GET /v1/evals?page=` → paginated eval runs `{id, mode, status, started_at, finished_at, summary}`
- `GET /v1/evals/{id}` → run + `results: [{task_name, mode, score, passed, explanation,
    tokens_used, details}]` + `golden_tasks_total`
- `POST /v1/evals/run` body `{mode: "comparison"|"baseline"|"context_engine"}` → 202
  `{eval_run_id, status}` (enqueued; inline-executed in tests/dev via stub broker)
- `GET /v1/evals/golden-tasks` → `{items: [{id, name, task, repo, service, is_active,
    expected_keywords}] , total}`

## Sources
- `GET /v1/sources` → `{items: [SourceOut {id, type, name, enabled, sync_status, last_synced_at,
    last_error, document_count, acl_sync_status, authority_rank, freshness_window_days}]}`
- `POST /v1/sources` [admin] body `{type, name, config?}` → 201 SourceOut
- `DELETE /v1/sources/{id}` [admin] → 204
- `POST /v1/sources/{id}/sync` [admin|lead] → 202 `{status: "queued"}` (audit-logged)
- `PATCH /v1/sources/{id}` [admin] body any of `{enabled, name, authority_rank,
    freshness_window_days, config}` → SourceOut

## Conflicts
- `GET /v1/conflicts?status=open|resolved&page=` → paginated `{id, topic_key, title, status,
    document_count, affected, created_at}`
- `GET /v1/conflicts/{id}` → `{id, topic_key, title, status, affected, resolution_note,
    resolved_by_name, resolved_at, linked_adr_url, recommended_document_id,
    documents: [{id, title, doc_type, source_name, freshness_score, authority_score,
    last_activity_at, excerpt}]}` (recommendation = highest authority·freshness)
- `POST /v1/conflicts/{id}/resolve` [admin|lead] body `{recommended_document_id?, note,
    linked_adr_url?}` → ConflictOut (marks losing docs stale? No — only audit + status)

## Context debt
- `GET /v1/context-debt` → `{stale_docs: [{repo, service, team_name, count}],
    missing_owners: [{key, doc_count}], undocumented_apis: [{name, service}],
    repeated_misses: [{query, count}], failed_agent_areas: [{repo, service, failed, total}],
    never_used_docs: [{id, title, doc_type, created_at}],
    frequently_rejected_docs: [{id, title, rejection_count}],
    conflicts_by_source_type: [{source_type, count}]}`

## Feedback
- `POST /v1/feedback` body `{type, context_packet_id?, document_id?, comment?}` → 201 FeedbackOut.
  Side effects: promote_authoritative → doc.authority_score=1.0; mark_deprecated →
  doc.status=deprecated; stale_context → doc.status=stale (all audit-logged).

## Admin & settings
- `GET /v1/admin/users` [admin] → `{items: [{id, email, name, role, team_name, is_active}]}`
- `GET /v1/admin/teams` [admin] → `{items: [{id, name, member_count}]}`
- `GET /v1/admin/api-keys` [admin] → `{items: [{id, label, kind, user_name, is_active,
    last_used_at}]}` (never returns key material)
- `GET /v1/admin/audit-logs?action=&page=` [admin] → paginated `{id, actor_name, action,
    resource_type, resource_id, detail, created_at}`
- `GET /v1/settings` [admin] → `{retrieval_weights, freshness_window_days, authority_rules,
    eval_thresholds, retention, pii_redaction, feature_flags, token_budget}`
- `PATCH /v1/settings` [admin] body: partial of the above → full settings (audit-logged)

## Misc
- `GET /v1/me` → `{id, email, name, role, team_name}` (drives UI RBAC states)
- `GET /healthz` (no auth) → `{status: "ok"}`

## Error shape
FastAPI default: `{"detail": str}`. 401 unauthenticated, 403 forbidden, 404 not-found/ACL-hidden,
422 validation.

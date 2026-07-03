# Data Model (Postgres + pgvector)

All models in `backend/src/context_engine/storage/models.py`. SQLAlchemy 2.0 typed ORM,
async engine. UUID PKs (`uuid4`, as `Uuid` type). `created_at`/`updated_at` timestamptz defaults.
JSON columns are `JSONB`. Enums are Python `str, enum.Enum` stored as strings (native_enum=False).

## Tables

### teams
- id UUID PK · name str unique · description str

### users
- id UUID PK · email str unique · name str · role enum(admin|lead|engineer|viewer)
- team_id FK teams · is_active bool default true · avatar_color str (hex, for UI)

### api_keys
- id UUID PK · key_hash str unique (sha256 of raw key) · label str · kind enum(api|mcp)
- user_id FK users · is_active bool · last_used_at ts nullable
- Raw demo keys are deterministic: `demo-admin-key`, `demo-lead-key`, `demo-engineer-key`,
  `demo-viewer-key`, `demo-mcp-token` (seeded; hash stored).

### sources
- id UUID PK · type enum(github|jira|slack|confluence|adr|incident|ci|feedback)
- name str · enabled bool · config JSONB
- sync_status enum(idle|syncing|ok|error) · last_synced_at ts nullable · last_error str nullable
- document_count int default 0 · acl_sync_status enum(ok|pending|error) default ok
- authority_rank int default 50 (0–100, admin-configurable) · freshness_window_days int default 90

### documents
- id UUID PK · source_id FK sources · external_id str · doc_type
  enum(code|pr|ticket|doc|message|adr|incident|ci_run|feedback)
- title str · content text · url str · author_id FK users nullable
- repo str nullable · service str nullable · team_id FK teams nullable
- status enum(active|stale|deprecated) · topic_key str nullable (conflict grouping)
- authority_score float 0–1 · freshness_score float 0–1 (recomputed from last_activity_at)
- acl_public bool · acl_team_ids JSONB (list[str uuid]) · acl_user_ids JSONB (list[str uuid])
- last_activity_at ts · doc_metadata JSONB (e.g. {stance, pr_number, severity, labels})
- usage_count int default 0 · rejection_count int default 0 (for context-debt)
- unique (source_id, external_id)

### chunks
- id UUID PK · document_id FK documents (cascade delete) · ord int · content text
- token_count int · embedding Vector(384) · tsv TSVECTOR (GIN index, generated in migration
  via trigger or computed column: to_tsvector('english', content))

### entities
- id UUID PK · type enum(repo|service|user|team|pr|ticket|doc|adr|incident|api|db_table|
  context_packet|agent_run) · name str · external_ref str nullable (document/packet/run UUID
  or natural key) · entity_metadata JSONB
- unique (type, name)

### edges
- id UUID PK · source_entity_id FK entities · target_entity_id FK entities
- type enum(owns|member_of|authored|references|modifies|resolves|caused_by|depends_on|
  documents|cites|deployed_in|used_by) · weight float default 1.0 · edge_metadata JSONB
- unique (source_entity_id, target_entity_id, type)

### context_packets
- id UUID PK · task text · intent enum(bugfix|feature|refactor|incident_response|question|unknown)
- repo str nullable · service str nullable · requested_by FK users
- compiled_context text (final markdown handed to agent)
- selected_sources JSONB  list[{document_id, title, doc_type, score, reasons: list[str]}]
- rejected_sources JSONB  list[{document_id, title, doc_type, score, reason}]
- citations JSONB         list[{marker: "S1", document_id, title, url, quote}]
- conflict_notes JSONB    list[{conflict_id, topic_key, chosen_document_id, note}]
- acl_notes JSONB         {blocked_count int, note str}
- token_estimate int · confidence_score float · freshness_score float · authority_score float
- risks JSONB list[str] · recommended_tests JSONB list[str]
- agent_outcome enum(pending|succeeded|failed|abandoned) default pending
- feedback_score float nullable (avg of feedback: useful=1, irrelevant=0)

### agent_runs
- id UUID PK · agent_name str · task text · repo str nullable · service str nullable
- user_id FK users · status enum(running|succeeded|failed)
- context_packet_id FK context_packets nullable
- plan text nullable · changed_files JSONB list[str] · test_output text nullable
- pr_url str nullable · reviewer_comments JSONB list[{author, comment}]
- langfuse_trace_id str nullable · started_at ts · finished_at ts nullable

### conflicts
- id UUID PK · topic_key str · title str · document_ids JSONB list[str]
- status enum(open|resolved) · recommended_document_id UUID nullable
- affected JSONB {repos: list[str], services: list[str]}
- resolution_note text nullable · resolved_by FK users nullable · resolved_at ts nullable
- linked_adr_url str nullable

### feedback
- id UUID PK · user_id FK users · context_packet_id FK nullable · document_id FK nullable
- type enum(useful|irrelevant|missing_context|stale_context|permission_issue|suggest_source|
  promote_authoritative|mark_deprecated)
- comment text nullable · created_at

### eval_tasks (golden tasks)
- id UUID PK · name str unique · task text · repo str nullable · service str nullable
- expected_document_ids JSONB list[str] · expected_keywords JSONB list[str] · is_active bool

### eval_runs
- id UUID PK · mode enum(baseline|context_engine|comparison) · status enum(running|completed|failed)
- triggered_by FK users nullable · started_at · finished_at nullable
- summary JSONB {avg_score, pass_rate, total_tokens, baseline_avg_score, baseline_total_tokens,
  regression: bool, regressed_task_names: list[str]}

### eval_results
- id UUID PK · eval_run_id FK (cascade) · eval_task_id FK
- mode enum(baseline|context_engine) · score float 0–1 · passed bool
- explanation text · tokens_used int · details JSONB {precision, recall, keyword_hits, citations_ok}

### audit_logs
- id UUID PK · actor_id FK users nullable · action str (e.g. "source.sync", "conflict.resolve",
  "settings.update", "acl.blocked") · resource_type str · resource_id str nullable
- detail JSONB · created_at

### app_settings
- key str PK · value JSONB · updated_at
- Seeded keys: retrieval_weights {vector,fts,freshness,authority}, freshness_window_days,
  authority_rules {source_type_ranks: {...}}, eval_thresholds {min_score, regression_delta},
  retention {audit_days, packet_days}, pii_redaction {enabled, patterns: list[str]},
  feature_flags {graph_v2, heatmap_export, ...}, token_budget {max_packet_tokens}

### activity_events (heatmap aggregates)
- id UUID PK · user_id FK · team_id FK · repo str nullable · service str nullable
- event_type enum(commit|pr|review|doc_edit|ticket|incident|packet_use)
- day date · count int
- unique (user_id, repo, service, event_type, day)

## Scoring conventions
- freshness_score = exp(-age_days / freshness_window_days), clamped [0,1]
- authority_score = source.authority_rank/100, doc-level overrides via doc_metadata.authority
- confidence_score (packet) = weighted mean of selected sources' (score · freshness · authority),
  penalized by open conflicts (−0.1 each, floor 0.05)
- Token estimate: `len(text) // 4` (chars/4), utility `estimate_tokens(text)` in
  `context_engine/indexing/tokens.py` — use everywhere.

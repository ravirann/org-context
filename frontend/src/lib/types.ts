/**
 * TypeScript mirrors of every request/response schema in docs/API_CONTRACT.md.
 * Field names are snake_case, exactly as the API returns them.
 */

/* ----------------------------------- shared ---------------------------------- */

export type Role = "admin" | "lead" | "engineer" | "viewer";

export interface Paginated<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface ItemsResponse<T> {
  items: T[];
}

/* ------------------------------------- me ------------------------------------ */

export interface Me {
  id: string;
  email: string;
  name: string;
  role: Role;
  team_name: string | null;
}

/* --------------------------------- dashboard --------------------------------- */

export interface DashboardSummary {
  total_documents: number;
  connected_sources: number;
  active_repos: number;
  active_services: number;
  active_users: number;
  context_packets: number;
  agent_runs: number;
  failed_agent_runs: number;
  stale_documents: number;
  conflicting_documents: number;
  acl_violations_blocked: number;
  latest_eval_score: number | null;
}

export interface TrendPoint {
  date: string;
  value: number;
}

export interface Trends {
  eval_scores: TrendPoint[];
  source_freshness: TrendPoint[];
  review_rework: TrendPoint[];
  packets_per_day: TrendPoint[];
}

/* ------------------------------- context packets ------------------------------ */

export type Intent =
  | "bugfix"
  | "feature"
  | "refactor"
  | "incident_response"
  | "question"
  | "unknown";

export type AgentOutcome = "pending" | "succeeded" | "failed" | "abandoned";

export interface SelectedSource {
  document_id: string;
  title: string;
  doc_type: string;
  score: number;
  reasons: string[];
}

export interface RejectedSource {
  document_id: string;
  title: string;
  doc_type: string;
  score: number;
  reason: string;
}

export interface Citation {
  marker: string;
  document_id: string;
  title: string;
  url: string | null;
  quote: string;
}

export interface ConflictNote {
  conflict_id: string;
  topic_key: string;
  chosen_document_id: string | null;
  note: string;
}

export interface AclNotes {
  blocked_count: number;
  note: string;
}

export interface CompileRequest {
  task: string;
  repo?: string;
  service?: string;
  max_tokens?: number;
}

export interface ContextPacket {
  id: string;
  task: string;
  intent: Intent;
  repo: string | null;
  service: string | null;
  compiled_context: string;
  selected_sources: SelectedSource[];
  rejected_sources: RejectedSource[];
  citations: Citation[];
  conflict_notes: ConflictNote[];
  acl_notes: AclNotes;
  token_estimate: number;
  confidence_score: number;
  freshness_score: number;
  authority_score: number;
  risks: string[];
  recommended_tests: string[];
  agent_outcome: AgentOutcome;
  feedback_score: number | null;
  requested_by_name: string;
  created_at: string;
}

export interface ContextPacketSummary {
  id: string;
  task: string;
  intent: Intent;
  repo: string | null;
  service: string | null;
  token_estimate: number;
  confidence_score: number;
  agent_outcome: AgentOutcome;
  requested_by_name: string;
  created_at: string;
  source_count: number;
}

export interface ContextPacketDetail extends ContextPacket {
  feedback: Feedback[];
  agent_run: AgentRunSummary | null;
}

/* ---------------------------------- search ----------------------------------- */

export interface SearchRequest {
  query: string;
  doc_types?: string[];
  source_ids?: string[];
  repo?: string;
  service?: string;
  status?: string;
  page?: number;
  page_size?: number;
}

export interface SearchResult {
  document_id: string;
  chunk_id: string;
  title: string;
  doc_type: string;
  source_name: string;
  snippet: string;
  score: number;
  url: string | null;
  repo: string | null;
  service: string | null;
  status: string;
  freshness_score: number;
  authority_score: number;
  last_activity_at: string;
}

export interface SearchResponse extends Paginated<SearchResult> {
  acl_blocked_count: number;
}

/* --------------------------------- documents --------------------------------- */

export interface DocumentSourceRef {
  id: string;
  name: string;
  type: string;
}

export interface DocumentAcl {
  public: boolean;
  team_names: string[];
  user_count: number;
}

export interface DocumentChunk {
  id: string;
  ord: number;
  content: string;
  token_count: number;
}

export interface RelatedDocument {
  id: string;
  title: string;
  doc_type: string;
  relation: string;
}

export interface DocumentConflictRef {
  id: string;
  topic_key: string;
  title: string;
  status: ConflictStatus;
}

export interface PacketUsage {
  packet_id: string;
  task: string;
  created_at: string;
  was_selected: boolean;
}

export interface DocumentDetail {
  id: string;
  title: string;
  content: string;
  doc_type: string;
  url: string | null;
  status: string;
  repo: string | null;
  service: string | null;
  source: DocumentSourceRef;
  author_name: string | null;
  team_name: string | null;
  topic_key: string | null;
  authority_score: number;
  freshness_score: number;
  last_activity_at: string;
  acl: DocumentAcl;
  chunks: DocumentChunk[];
  citations_of: number;
  related: RelatedDocument[];
  conflicts: DocumentConflictRef[];
  packet_usage: PacketUsage[];
}

/* ------------------------------- relationships -------------------------------- */

export interface GraphNode {
  id: string;
  type: string;
  label: string;
  ref: string | null;
  stale: boolean;
  conflicted: boolean;
  degree: number;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  type: string;
  weight: number;
}

export interface GraphResponse {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface PathStep {
  node: GraphNode;
  edge: GraphEdge | null;
}

export interface PathResponse {
  path: PathStep[];
  found: boolean;
}

/* ---------------------------------- heatmaps ---------------------------------- */

export type HeatmapMetric =
  | "commit"
  | "pr"
  | "review"
  | "doc_edit"
  | "ticket"
  | "incident"
  | "packet_use"
  | "all";

export interface HeatmapCell {
  day: string;
  value: number;
}

export interface HeatmapRow {
  user_id: string;
  user_name: string;
  team_name: string | null;
  cells: HeatmapCell[];
  total: number;
}

export interface HeatmapUsersResponse {
  rows: HeatmapRow[];
  days: string[];
}

export interface OwnershipRow {
  key: string;
  owner_team: string | null;
  doc_count: number;
  owner_user_names: string[];
  coverage_score: number;
  last_activity_at: string | null;
}

export interface OwnershipResponse {
  rows: OwnershipRow[];
}

export interface ContextDebtRow {
  key: string;
  repo: string | null;
  service: string | null;
  team_name: string | null;
  stale_count: number;
  missing_owner: boolean;
  conflict_count: number;
  rejected_count: number;
  failed_runs: number;
  debt_score: number;
}

export interface ContextDebtHeatmapResponse {
  rows: ContextDebtRow[];
}

/* --------------------------------- agent runs --------------------------------- */

export type AgentRunStatus = "running" | "succeeded" | "failed";

export interface AgentRunSummary {
  id: string;
  agent_name: string;
  task: string;
  repo: string | null;
  service: string | null;
  user_name: string;
  status: AgentRunStatus;
  started_at: string;
  finished_at: string | null;
  context_packet_id: string | null;
}

export interface ReviewerComment {
  author: string;
  comment: string;
}

export interface AgentRunDetail extends AgentRunSummary {
  plan: string | null;
  changed_files: string[];
  test_output: string | null;
  pr_url: string | null;
  reviewer_comments: ReviewerComment[];
  langfuse_trace_url: string | null;
  context_packet: ContextPacket | null;
}

/* ------------------------------------ evals ----------------------------------- */

export type EvalMode = "baseline" | "context_engine" | "comparison";
export type EvalRunStatus = "running" | "completed" | "failed";

export interface EvalSummary {
  avg_score: number;
  pass_rate: number;
  total_tokens: number;
  baseline_avg_score: number | null;
  baseline_total_tokens: number | null;
  regression: boolean;
  regressed_task_names: string[];
}

export interface EvalRun {
  id: string;
  mode: EvalMode;
  status: EvalRunStatus;
  started_at: string;
  finished_at: string | null;
  summary: EvalSummary | null;
}

export interface EvalResultDetails {
  precision: number;
  recall: number;
  keyword_hits: number;
  citations_ok: boolean;
}

export interface EvalResult {
  task_name: string;
  mode: "baseline" | "context_engine";
  score: number;
  passed: boolean;
  explanation: string;
  tokens_used: number;
  details: EvalResultDetails;
}

export interface EvalRunDetail extends EvalRun {
  results: EvalResult[];
  golden_tasks_total: number;
}

export interface EvalRunRequest {
  mode: EvalMode;
}

export interface EvalRunEnqueued {
  eval_run_id: string;
  status: string;
}

export interface GoldenTask {
  id: string;
  name: string;
  task: string;
  repo: string | null;
  service: string | null;
  is_active: boolean;
  expected_keywords: string[];
}

export interface GoldenTasksResponse {
  items: GoldenTask[];
  total: number;
}

/* ----------------------------------- sources ---------------------------------- */

export interface Source {
  id: string;
  type: string;
  name: string;
  enabled: boolean;
  sync_status: string;
  last_synced_at: string | null;
  last_error: string | null;
  document_count: number;
  acl_sync_status: string;
  authority_rank: number;
  freshness_window_days: number;
  config: Record<string, unknown>;
  sync_state: Record<string, unknown>;
  last_sync_run?: SyncRun | null;
}

export interface SourceCreate {
  type: string;
  name: string;
  config?: Record<string, unknown>;
}

export interface SourceUpdate {
  enabled?: boolean;
  name?: string;
  authority_rank?: number;
  freshness_window_days?: number;
  config?: Record<string, unknown>;
}

export interface SyncEnqueued {
  status: string;
}

export type SyncRunTrigger = "manual" | "scheduled";
export type SyncRunStatus = "running" | "ok" | "error";

export interface SyncRunError {
  external_id?: string | null;
  error: string;
}

export interface SyncRun {
  id: string;
  trigger: SyncRunTrigger;
  status: SyncRunStatus;
  started_at: string;
  finished_at: string | null;
  docs_upserted: number;
  docs_skipped: number;
  docs_pruned: number;
  chunks_indexed: number;
  errors: SyncRunError[];
}

/* ---------------------------------- system ------------------------------------ */

export interface SystemEmbeddingInfo {
  provider: string;
  model: string;
  dim: number;
}

export interface SystemInfo {
  embedding: SystemEmbeddingInfo;
  auth_mode: string;
  queue_depth: number | null;
  version: string;
}

/* ---------------------------------- conflicts --------------------------------- */

export type ConflictStatus = "open" | "resolved";

export interface ConflictAffected {
  repos: string[];
  services: string[];
}

export interface Conflict {
  id: string;
  topic_key: string;
  title: string;
  status: ConflictStatus;
  document_count: number;
  affected: ConflictAffected;
  created_at: string;
}

export interface ConflictDocument {
  id: string;
  title: string;
  doc_type: string;
  source_name: string;
  freshness_score: number;
  authority_score: number;
  last_activity_at: string;
  excerpt: string;
}

export interface ConflictDetail {
  id: string;
  topic_key: string;
  title: string;
  status: ConflictStatus;
  affected: ConflictAffected;
  resolution_note: string | null;
  resolved_by_name: string | null;
  resolved_at: string | null;
  linked_adr_url: string | null;
  recommended_document_id: string | null;
  documents: ConflictDocument[];
}

export interface ConflictResolveRequest {
  recommended_document_id?: string;
  note: string;
  linked_adr_url?: string;
}

/* --------------------------------- context debt ------------------------------- */

export interface StaleDocsRow {
  repo: string | null;
  service: string | null;
  team_name: string | null;
  count: number;
}

export interface MissingOwnerRow {
  key: string;
  doc_count: number;
}

export interface UndocumentedApiRow {
  name: string;
  service: string;
}

export interface RepeatedMissRow {
  query: string;
  count: number;
}

export interface FailedAgentAreaRow {
  repo: string | null;
  service: string | null;
  failed: number;
  total: number;
}

export interface NeverUsedDocRow {
  id: string;
  title: string;
  doc_type: string;
  created_at: string;
}

export interface FrequentlyRejectedDocRow {
  id: string;
  title: string;
  rejection_count: number;
}

export interface ConflictsBySourceTypeRow {
  source_type: string;
  count: number;
}

export interface ContextDebtReport {
  stale_docs: StaleDocsRow[];
  missing_owners: MissingOwnerRow[];
  undocumented_apis: UndocumentedApiRow[];
  repeated_misses: RepeatedMissRow[];
  failed_agent_areas: FailedAgentAreaRow[];
  never_used_docs: NeverUsedDocRow[];
  frequently_rejected_docs: FrequentlyRejectedDocRow[];
  conflicts_by_source_type: ConflictsBySourceTypeRow[];
}

/* ---------------------------------- feedback ---------------------------------- */

export type FeedbackType =
  | "useful"
  | "irrelevant"
  | "missing_context"
  | "stale_context"
  | "permission_issue"
  | "suggest_source"
  | "promote_authoritative"
  | "mark_deprecated";

export interface Feedback {
  id: string;
  type: FeedbackType;
  context_packet_id: string | null;
  document_id: string | null;
  comment: string | null;
  user_name: string;
  created_at: string;
}

export interface FeedbackCreate {
  type: FeedbackType;
  context_packet_id?: string;
  document_id?: string;
  comment?: string;
}

/* ---------------------------------- auth --------------------------------------- */

export type AuthMode = "demo" | "oidc";

export interface AuthSession {
  auth_mode: AuthMode;
  authenticated: boolean;
  user: Me | null;
}

export interface AuthLoginResponse {
  authorization_url: string;
}

/* ------------------------------- admin & settings ------------------------------ */

export interface AdminUser {
  id: string;
  email: string;
  name: string;
  role: Role;
  team_name: string | null;
  is_active: boolean;
}

export interface CreateUserRequest {
  email: string;
  name: string;
  role: Role;
  team_id?: string | null;
}

export interface UpdateUserRequest {
  name?: string;
  role?: Role;
  team_id?: string | null;
  is_active?: boolean;
}

export interface AdminTeam {
  id: string;
  name: string;
  member_count: number;
}

export interface CreateTeamRequest {
  name: string;
  description?: string;
}

export interface ApiKeyOut {
  id: string;
  label: string;
  kind: string;
  user_name: string;
  is_active: boolean;
  last_used_at: string | null;
}

export type ApiKeyKind = "api" | "mcp";

export interface CreateApiKeyRequest {
  label: string;
  kind: ApiKeyKind;
  user_id: string;
  role_hint?: Role;
}

export interface ApiKeyCreated {
  id: string;
  label: string;
  kind: string;
  user_name: string;
  raw_key: string;
}

export interface AuditLog {
  id: string;
  actor_name: string | null;
  action: string;
  resource_type: string;
  resource_id: string | null;
  detail: Record<string, unknown>;
  created_at: string;
}

export interface RetrievalWeights {
  vector: number;
  fts: number;
  freshness: number;
  authority: number;
}

export interface AuthorityRules {
  source_type_ranks: Record<string, number>;
}

export interface EvalThresholds {
  min_score: number;
  regression_delta: number;
}

export interface RetentionSettings {
  audit_days: number;
  packet_days: number;
}

export interface PiiRedactionSettings {
  enabled: boolean;
  patterns: string[];
}

export interface TokenBudgetSettings {
  max_packet_tokens: number;
}

export interface Settings {
  retrieval_weights: RetrievalWeights;
  freshness_window_days: number;
  authority_rules: AuthorityRules;
  eval_thresholds: EvalThresholds;
  retention: RetentionSettings;
  pii_redaction: PiiRedactionSettings;
  feature_flags: Record<string, boolean>;
  token_budget: TokenBudgetSettings;
}

export type SettingsUpdate = Partial<Settings>;

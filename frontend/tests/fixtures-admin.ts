/**
 * Realistic fixtures (per docs/API_CONTRACT.md) for the conflicts, context-debt,
 * feedback and admin page tests.
 */
import type {
  AdminTeam,
  AdminUser,
  ApiKeyOut,
  AuditLog,
  Conflict,
  ConflictDetail,
  ConflictDocument,
  ContextDebtReport,
  ItemsResponse,
  Me,
  Paginated,
  Settings,
} from "@/lib/types";

export function paginated<T>(
  items: T[],
  { page = 1, page_size = 20, total = items.length } = {},
): Paginated<T> {
  return { items, total, page, page_size };
}

/* ------------------------------------- me ------------------------------------ */

export const meAdmin: Me = {
  id: "6b1f0c1a-1111-4e1a-9b1a-000000000001",
  email: "ava@example.com",
  name: "Ava Admin",
  role: "admin",
  team_name: "Platform",
};

export const meLead: Me = {
  id: "6b1f0c1a-1111-4e1a-9b1a-000000000002",
  email: "lena@example.com",
  name: "Lena Lead",
  role: "lead",
  team_name: "Payments",
};

export const meViewer: Me = {
  id: "6b1f0c1a-1111-4e1a-9b1a-000000000003",
  email: "vik@example.com",
  name: "Vik Viewer",
  role: "viewer",
  team_name: null,
};

/* ---------------------------------- conflicts --------------------------------- */

export const conflictOpen: Conflict = {
  id: "c0000000-0000-4000-8000-000000000001",
  topic_key: "payments.webhook-retry-policy",
  title: "Webhook retry policy disagrees between runbook and ADR",
  status: "open",
  document_count: 2,
  affected: {
    repos: ["payments-api", "webhook-worker"],
    services: ["payments", "billing", "notifications"],
  },
  created_at: "2026-06-28T09:15:00Z",
};

export const conflictResolved: Conflict = {
  id: "c0000000-0000-4000-8000-000000000002",
  topic_key: "auth.session-ttl",
  title: "Session TTL documented as both 24h and 7d",
  status: "resolved",
  document_count: 3,
  affected: { repos: ["auth-service"], services: ["auth"] },
  created_at: "2026-06-20T14:00:00Z",
};

export const conflictsPage: Paginated<Conflict> = paginated([
  conflictOpen,
  conflictResolved,
]);

export const conflictDocA: ConflictDocument = {
  id: "d0000000-0000-4000-8000-00000000000a",
  title: "Payments webhook runbook",
  doc_type: "runbook",
  source_name: "Confluence",
  freshness_score: 0.35,
  authority_score: 0.9,
  last_activity_at: "2026-03-02T08:00:00Z",
  excerpt:
    "Webhook deliveries are retried 3 times with a fixed 30s delay. After the third " +
    "failure the event is parked in the DLQ and an on-call page fires. Operators " +
    "should replay parked events from the admin console once the downstream " +
    "consumer recovers, and never re-enqueue manually via the broker.",
};

export const conflictDocB: ConflictDocument = {
  id: "d0000000-0000-4000-8000-00000000000b",
  title: "ADR-118: exponential backoff for webhook retries",
  doc_type: "adr",
  source_name: "GitHub",
  freshness_score: 0.95,
  authority_score: 0.85,
  last_activity_at: "2026-06-25T16:30:00Z",
  excerpt:
    "We adopt exponential backoff with jitter (base 1m, cap 4h, max 10 attempts) " +
    "for webhook redelivery. The fixed 3×30s scheme is retired because it drops " +
    "events during longer consumer outages.",
};

export const conflictDetailOpen: ConflictDetail = {
  id: conflictOpen.id,
  topic_key: conflictOpen.topic_key,
  title: conflictOpen.title,
  status: "open",
  affected: conflictOpen.affected,
  resolution_note: null,
  resolved_by_name: null,
  resolved_at: null,
  linked_adr_url: null,
  recommended_document_id: conflictDocA.id,
  documents: [conflictDocA, conflictDocB],
};

/** No API recommendation → the client should pick doc B (0.95×0.85 > 0.35×0.9). */
export const conflictDetailNoRecommendation: ConflictDetail = {
  ...conflictDetailOpen,
  recommended_document_id: null,
};

export const conflictDetailResolved: ConflictDetail = {
  ...conflictDetailOpen,
  status: "resolved",
  resolution_note: "ADR-118 wins; the runbook predates the backoff decision.",
  resolved_by_name: "Lena Lead",
  resolved_at: "2026-07-01T11:20:00Z",
  linked_adr_url: "https://github.com/org/payments-api/blob/main/docs/adr/118.md",
  recommended_document_id: conflictDocB.id,
};

/* --------------------------------- context debt ------------------------------- */

export const debtReport: ContextDebtReport = {
  stale_docs: [
    { repo: "payments-api", service: null, team_name: "Payments", count: 12 },
    { repo: null, service: "auth", team_name: "Identity", count: 7 },
    { repo: "webhook-worker", service: null, team_name: null, count: 3 },
  ],
  missing_owners: [
    { key: "legacy-billing", doc_count: 9 },
    { key: "cron-scripts", doc_count: 2 },
  ],
  undocumented_apis: [
    { name: "POST /v2/refunds", service: "payments" },
    { name: "GET /internal/flags", service: "config" },
  ],
  repeated_misses: [
    { query: "refund idempotency key rules", count: 14 },
    { query: "sandbox webhook signature", count: 6 },
  ],
  failed_agent_areas: [
    { repo: "payments-api", service: null, failed: 8, total: 20 },
    { repo: null, service: "notifications", failed: 2, total: 16 },
  ],
  never_used_docs: [
    {
      id: "d0000000-0000-4000-8000-0000000000c1",
      title: "2019 on-call handbook",
      doc_type: "wiki",
      created_at: "2019-04-11T10:00:00Z",
    },
  ],
  frequently_rejected_docs: [
    {
      id: "d0000000-0000-4000-8000-0000000000c2",
      title: "Old deployment checklist",
      rejection_count: 21,
    },
  ],
  conflicts_by_source_type: [
    { source_type: "confluence", count: 5 },
    { source_type: "slack", count: 3 },
    { source_type: "github", count: 1 },
  ],
};

export const emptyDebtReport: ContextDebtReport = {
  stale_docs: [],
  missing_owners: [],
  undocumented_apis: [],
  repeated_misses: [],
  failed_agent_areas: [],
  never_used_docs: [],
  frequently_rejected_docs: [],
  conflicts_by_source_type: [],
};

/* ------------------------------- admin & settings ------------------------------ */

export const adminUsersFixture: ItemsResponse<AdminUser> = {
  items: [
    {
      id: meAdmin.id,
      email: meAdmin.email,
      name: meAdmin.name,
      role: "admin",
      team_name: "Platform",
      is_active: true,
    },
    {
      id: meLead.id,
      email: meLead.email,
      name: meLead.name,
      role: "lead",
      team_name: "Payments",
      is_active: true,
    },
    {
      id: "6b1f0c1a-1111-4e1a-9b1a-000000000004",
      email: "eli@example.com",
      name: "Eli Engineer",
      role: "engineer",
      team_name: "Payments",
      is_active: false,
    },
  ],
};

export const adminTeamsFixture: ItemsResponse<AdminTeam> = {
  items: [
    { id: "t0000000-0000-4000-8000-000000000001", name: "Platform", member_count: 6 },
    { id: "t0000000-0000-4000-8000-000000000002", name: "Payments", member_count: 11 },
  ],
};

export const adminApiKeysFixture: ItemsResponse<ApiKeyOut> = {
  items: [
    {
      id: "k0000000-0000-4000-8000-000000000001",
      label: "ava-cli",
      kind: "api",
      user_name: "Ava Admin",
      is_active: true,
      last_used_at: "2026-07-02T18:00:00Z",
    },
    {
      id: "k0000000-0000-4000-8000-000000000002",
      label: "claude-mcp",
      kind: "mcp",
      user_name: "Eli Engineer",
      is_active: false,
      last_used_at: null,
    },
  ],
};

export const auditLogsFixture: Paginated<AuditLog> = paginated([
  {
    id: "a0000000-0000-4000-8000-000000000001",
    actor_name: "Ava Admin",
    action: "settings.update",
    resource_type: "settings",
    resource_id: null,
    detail: { retrieval_weights: { vector: 0.5 } },
    created_at: "2026-07-02T09:00:00Z",
  },
  {
    id: "a0000000-0000-4000-8000-000000000002",
    actor_name: null,
    action: "source.sync",
    resource_type: "source",
    resource_id: "s0000000-0000-4000-8000-000000000001",
    detail: { status: "queued" },
    created_at: "2026-07-01T22:30:00Z",
  },
]);

export const settingsFixture: Settings = {
  retrieval_weights: { vector: 0.5, fts: 0.2, freshness: 0.15, authority: 0.15 },
  freshness_window_days: 90,
  authority_rules: { source_type_ranks: { adr: 100, confluence: 60, slack: 20 } },
  eval_thresholds: { min_score: 0.7, regression_delta: 0.05 },
  retention: { audit_days: 365, packet_days: 90 },
  pii_redaction: { enabled: true, patterns: ["\\b\\d{3}-\\d{2}-\\d{4}\\b"] },
  feature_flags: { conflict_auto_resolve: false, graph_v2: true },
  token_budget: { max_packet_tokens: 6000 },
};

/**
 * Shared, realistic API fixtures matching docs/API_CONTRACT.md exactly.
 * Used by the page tests in tests/pages/*.test.tsx.
 */
import type {
  ContextPacket,
  ContextPacketDetail,
  ContextPacketSummary,
  DashboardSummary,
  DocumentDetail,
  Feedback,
  Me,
  Paginated,
  SearchResponse,
  Trends,
} from "@/lib/types";

/* ------------------------------------ me ------------------------------------- */

export const meFixture: Me = {
  id: "u-1",
  email: "asha@acme.dev",
  name: "Asha Rao",
  role: "engineer",
  team_name: "Payments",
};

/* --------------------------------- dashboard ---------------------------------- */

export const dashboardSummaryFixture: DashboardSummary = {
  total_documents: 12842,
  connected_sources: 7,
  active_repos: 24,
  active_services: 18,
  active_users: 86,
  context_packets: 1439,
  agent_runs: 512,
  failed_agent_runs: 37,
  stale_documents: 214,
  conflicting_documents: 12,
  acl_violations_blocked: 93,
  latest_eval_score: 0.87,
};

export const dashboardTrendsFixture: Trends = {
  eval_scores: [
    { date: "2026-06-01", value: 0.81 },
    { date: "2026-06-15", value: 0.84 },
    { date: "2026-06-29", value: 0.87 },
  ],
  source_freshness: [
    { date: "2026-06-01", value: 0.72 },
    { date: "2026-06-15", value: 0.75 },
    { date: "2026-06-29", value: 0.79 },
  ],
  review_rework: [
    { date: "2026-06-01", value: 14 },
    { date: "2026-06-15", value: 11 },
    { date: "2026-06-29", value: 8 },
  ],
  packets_per_day: [
    { date: "2026-06-27", value: 42 },
    { date: "2026-06-28", value: 55 },
    { date: "2026-06-29", value: 47 },
  ],
};

export const emptyTrendsFixture: Trends = {
  eval_scores: [],
  source_freshness: [],
  review_rework: [],
  packets_per_day: [],
};

/* ----------------------------------- search ----------------------------------- */

export const searchResponseFixture: SearchResponse = {
  items: [
    {
      document_id: "doc-1",
      chunk_id: "chunk-1",
      title: "Payment webhook retry runbook",
      doc_type: "runbook",
      source_name: "Confluence",
      snippet: "When the payment webhook fails, retries use exponential backoff up to 5 attempts.",
      score: 0.92,
      url: "https://wiki.acme.dev/runbooks/payment-webhook",
      repo: "acme/payments",
      service: "payment-service",
      status: "active",
      freshness_score: 0.9,
      authority_score: 0.85,
      last_activity_at: "2026-06-30T09:00:00Z",
    },
    {
      document_id: "doc-2",
      chunk_id: "chunk-2",
      title: "ADR-042: Payment idempotency keys",
      doc_type: "adr",
      source_name: "GitHub",
      snippet: "Every payment mutation must carry an idempotency key derived from the order id.",
      score: 0.81,
      url: null,
      repo: "acme/payments",
      service: null,
      status: "stale",
      freshness_score: 0.42,
      authority_score: 0.95,
      last_activity_at: "2026-03-11T13:30:00Z",
    },
  ],
  total: 42,
  page: 1,
  page_size: 20,
  acl_blocked_count: 3,
};

export const emptySearchResponseFixture: SearchResponse = {
  items: [],
  total: 0,
  page: 1,
  page_size: 20,
  acl_blocked_count: 0,
};

/* ---------------------------------- documents ---------------------------------- */

export const documentDetailFixture: DocumentDetail = {
  id: "doc-1",
  title: "Payment webhook retry runbook",
  content:
    "# Payment webhook retries\n\nWhen the payment webhook fails, retries use exponential backoff.\n\n## Escalation\nPage the payments on-call after 5 failed attempts.",
  doc_type: "runbook",
  url: "https://wiki.acme.dev/runbooks/payment-webhook",
  status: "active",
  repo: "acme/payments",
  service: "payment-service",
  source: { id: "src-1", name: "Confluence", type: "confluence" },
  author_name: "Maya Chen",
  team_name: "Payments",
  topic_key: "payments.webhook.retry",
  authority_score: 0.85,
  freshness_score: 0.9,
  last_activity_at: "2026-06-30T09:00:00Z",
  acl: { public: false, team_names: ["Payments", "SRE"], user_count: 14 },
  chunks: [
    {
      id: "chunk-1",
      ord: 0,
      content: "When the payment webhook fails, retries use exponential backoff.",
      token_count: 120,
    },
    {
      id: "chunk-2",
      ord: 1,
      content:
        "Escalation policy: page the payments on-call after 5 failed attempts. " +
        "Include the last webhook payload and the delivery attempt ids in the page so the " +
        "on-call engineer can replay the event from the dashboard without digging through logs.",
      token_count: 180,
    },
  ],
  citations_of: 12,
  related: [
    { id: "doc-2", title: "ADR-042: Payment idempotency keys", doc_type: "adr", relation: "mentions" },
  ],
  conflicts: [
    {
      id: "conf-1",
      topic_key: "payments.webhook.retry",
      title: "Retry limits disagree between runbook and ADR",
      status: "open",
    },
  ],
  packet_usage: [
    {
      packet_id: "pkt-1",
      task: "Fix webhook retry storm",
      created_at: "2026-07-01T10:00:00Z",
      was_selected: true,
    },
    {
      packet_id: "pkt-2",
      task: "Add payment reconciliation job",
      created_at: "2026-06-20T08:00:00Z",
      was_selected: false,
    },
  ],
};

/* ------------------------------- context packets -------------------------------- */

export const packetSummariesFixture: Paginated<ContextPacketSummary> = {
  items: [
    {
      id: "pkt-1",
      task: "Fix webhook retry storm in payment-service",
      intent: "bugfix",
      repo: "acme/payments",
      service: "payment-service",
      token_estimate: 5120,
      confidence_score: 0.88,
      agent_outcome: "succeeded",
      requested_by_name: "Asha Rao",
      created_at: "2026-07-01T10:00:00Z",
      source_count: 6,
    },
    {
      id: "pkt-2",
      task: "Add payment reconciliation job",
      intent: "feature",
      repo: null,
      service: "billing-service",
      token_estimate: 15300,
      confidence_score: 0.61,
      agent_outcome: "pending",
      requested_by_name: "Maya Chen",
      created_at: "2026-06-20T08:00:00Z",
      source_count: 9,
    },
  ],
  total: 2,
  page: 1,
  page_size: 20,
};

export const compiledPacketFixture: ContextPacket = {
  id: "pkt-new",
  task: "Investigate flaky payment e2e test",
  intent: "bugfix",
  repo: "acme/payments",
  service: null,
  compiled_context: "# Context\n[S1] Retry runbook…",
  selected_sources: [
    {
      document_id: "doc-1",
      title: "Payment webhook retry runbook",
      doc_type: "runbook",
      score: 0.92,
      reasons: ["vector match"],
    },
  ],
  rejected_sources: [],
  citations: [],
  conflict_notes: [],
  acl_notes: { blocked_count: 0, note: "" },
  token_estimate: 2100,
  confidence_score: 0.8,
  freshness_score: 0.9,
  authority_score: 0.84,
  risks: [],
  recommended_tests: [],
  agent_outcome: "pending",
  feedback_score: null,
  requested_by_name: "Asha Rao",
  created_at: "2026-07-02T12:00:00Z",
};

export const feedbackFixture: Feedback = {
  id: "fb-1",
  type: "useful",
  context_packet_id: "pkt-1",
  document_id: null,
  comment: "Nailed the retry context.",
  user_name: "Maya Chen",
  created_at: "2026-07-01T12:00:00Z",
};

export const packetDetailFixture: ContextPacketDetail = {
  id: "pkt-1",
  task: "Fix webhook retry storm in payment-service",
  intent: "bugfix",
  repo: "acme/payments",
  service: "payment-service",
  compiled_context:
    "# Task context\n\nThe payment webhook retries with exponential backoff [S1].\nIdempotency keys are required on every mutation [S2].",
  selected_sources: [
    {
      document_id: "doc-1",
      title: "Payment webhook retry runbook",
      doc_type: "runbook",
      score: 0.92,
      reasons: ["vector match", "fresh"],
    },
    {
      document_id: "doc-2",
      title: "ADR-042: Payment idempotency keys",
      doc_type: "adr",
      score: 0.81,
      reasons: ["authoritative"],
    },
  ],
  rejected_sources: [
    {
      document_id: "doc-9",
      title: "Legacy payments FAQ",
      doc_type: "wiki",
      score: 0.34,
      reason: "superseded by newer runbook",
    },
    {
      document_id: "doc-10",
      title: "Old webhook design doc",
      doc_type: "design",
      score: 0.28,
      reason: "stale beyond freshness window",
    },
  ],
  citations: [
    {
      marker: "S1",
      document_id: "doc-1",
      title: "Payment webhook retry runbook",
      url: "https://wiki.acme.dev/runbooks/payment-webhook",
      quote: "retries use exponential backoff up to 5 attempts",
    },
    {
      marker: "S2",
      document_id: "doc-2",
      title: "ADR-042: Payment idempotency keys",
      url: null,
      quote: "Every payment mutation must carry an idempotency key",
    },
  ],
  conflict_notes: [
    {
      conflict_id: "conf-1",
      topic_key: "payments.webhook.retry",
      chosen_document_id: "doc-1",
      note: "Runbook chosen over ADR draft — higher freshness and authority.",
    },
  ],
  acl_notes: {
    blocked_count: 2,
    note: "Two finance documents were excluded by team ACLs.",
  },
  token_estimate: 5120,
  confidence_score: 0.88,
  freshness_score: 0.9,
  authority_score: 0.84,
  risks: ["Retry limit change may impact reconciliation jobs"],
  recommended_tests: ["Replay a failed webhook and assert 5 retries", "Idempotency key uniqueness test"],
  agent_outcome: "succeeded",
  feedback_score: 0.9,
  requested_by_name: "Asha Rao",
  created_at: "2026-07-01T10:00:00Z",
  feedback: [feedbackFixture],
  agent_run: {
    id: "run-1",
    agent_name: "claude-code",
    task: "Fix webhook retry storm in payment-service",
    repo: "acme/payments",
    service: "payment-service",
    user_name: "Asha Rao",
    status: "succeeded",
    started_at: "2026-07-01T10:05:00Z",
    finished_at: "2026-07-01T10:25:00Z",
    context_packet_id: "pkt-1",
  },
};

/* ---------------------------------- helpers ------------------------------------ */

/** Base routes most page tests need (auth'd user). */
export const baseRoutes = {
  "GET /v1/me": meFixture,
};

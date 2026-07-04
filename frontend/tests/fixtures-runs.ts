/**
 * Realistic fixtures for the agent-runs / evals / sources page tests,
 * shaped exactly like docs/API_CONTRACT.md responses.
 */
import type {
  AgentRunDetail,
  AgentRunSummary,
  ContextPacket,
  EvalRun,
  EvalRunDetail,
  GoldenTasksResponse,
  ItemsResponse,
  Me,
  Paginated,
  Source,
  SyncRun,
} from "@/lib/types";

/* ------------------------------------ me -------------------------------------- */

export const meAdmin: Me = {
  id: "u-admin",
  email: "ada@example.com",
  name: "Ada Admin",
  role: "admin",
  team_name: "Platform",
};

export const meEngineer: Me = {
  id: "u-eng",
  email: "eng@example.com",
  name: "Evan Engineer",
  role: "engineer",
  team_name: "Payments",
};

/* -------------------------------- agent runs ---------------------------------- */

export function paginate<T>(
  items: T[],
  overrides: Partial<Paginated<T>> = {},
): Paginated<T> {
  return { items, total: items.length, page: 1, page_size: 20, ...overrides };
}

export const agentRuns: AgentRunSummary[] = [
  {
    id: "run-1",
    agent_name: "claude-code",
    task: "Fix the flaky retry logic in the payments webhook handler so that duplicate events are ignored",
    repo: "org/payments",
    service: "payments-api",
    user_name: "Evan Engineer",
    status: "succeeded",
    started_at: "2026-07-01T10:00:00Z",
    finished_at: "2026-07-01T10:02:14Z",
    context_packet_id: "packet-1",
  },
  {
    id: "run-2",
    agent_name: "cursor",
    task: "Add dark-mode support to the settings page",
    repo: "org/webapp",
    service: null,
    user_name: "Ada Admin",
    status: "running",
    started_at: "2026-07-02T08:30:00Z",
    finished_at: null,
    context_packet_id: null,
  },
  {
    id: "run-3",
    agent_name: "claude-code",
    task: "Upgrade SQLAlchemy to 2.0 across the ingestion workers",
    repo: null,
    service: "ingestion-worker",
    user_name: "Priya Lead",
    status: "failed",
    started_at: "2026-06-30T16:45:00Z",
    finished_at: "2026-06-30T17:01:03Z",
    context_packet_id: "packet-3",
  },
];

export const agentRunsPage: Paginated<AgentRunSummary> = paginate(agentRuns, {
  total: 42,
});

export const contextPacket: ContextPacket = {
  id: "packet-1",
  task: "Fix the flaky retry logic in the payments webhook handler",
  intent: "bugfix",
  repo: "org/payments",
  service: "payments-api",
  compiled_context: "## Webhook retry semantics\n...",
  selected_sources: [
    {
      document_id: "doc-1",
      title: "ADR-014: Webhook idempotency keys",
      doc_type: "adr",
      score: 0.93,
      reasons: ["authority", "topic match"],
    },
    {
      document_id: "doc-2",
      title: "payments-api runbook",
      doc_type: "runbook",
      score: 0.81,
      reasons: ["freshness"],
    },
    {
      document_id: "doc-3",
      title: "Incident 2026-05-12: duplicate charges",
      doc_type: "incident",
      score: 0.77,
      reasons: ["incident linkage"],
    },
  ],
  rejected_sources: [
    {
      document_id: "doc-9",
      title: "Old webhook design doc",
      doc_type: "confluence",
      score: 0.31,
      reason: "stale",
    },
  ],
  citations: [
    {
      marker: "[1]",
      document_id: "doc-1",
      title: "ADR-014: Webhook idempotency keys",
      url: "https://example.com/adr-014",
      quote: "Every webhook must carry an idempotency key.",
    },
  ],
  conflict_notes: [],
  acl_notes: { blocked_count: 0, note: "" },
  token_estimate: 5482,
  confidence_score: 0.87,
  freshness_score: 0.9,
  authority_score: 0.95,
  risks: ["Retry storm if the queue backs up"],
  recommended_tests: ["test_webhook_duplicate_event_ignored"],
  agent_outcome: "succeeded",
  feedback_score: 0.8,
  requested_by_name: "Evan Engineer",
  created_at: "2026-07-01T09:58:00Z",
};

export const agentRunDetail: AgentRunDetail = {
  ...agentRuns[0],
  plan: "1. Reproduce the duplicate-event bug\n2. Add idempotency-key check\n3. Extend webhook tests",
  changed_files: [
    "src/payments/webhooks/handler.py",
    "src/payments/webhooks/dedupe.py",
    "tests/test_webhooks.py",
  ],
  test_output:
    "collected 24 items\n" +
    "tests/test_webhooks.py::test_single_event PASSED\n" +
    "tests/test_webhooks.py::test_duplicate_event FAILED\n" +
    "AssertionError: Error processing duplicate event\n" +
    "tests/test_webhooks.py::test_retry_backoff PASSED\n" +
    "23 passed, 1 failed",
  pr_url: "https://github.com/org/payments/pull/321",
  reviewer_comments: [
    { author: "Priya Lead", comment: "Please add a test for the 3x retry path." },
    { author: "Sam Reviewer", comment: "LGTM after the dedupe TTL tweak." },
  ],
  langfuse_trace_url: "https://langfuse.example.com/trace/abc123",
  context_packet: contextPacket,
};

/** Running run with no packet, no trace, no test output. */
export const agentRunDetailMinimal: AgentRunDetail = {
  ...agentRuns[1],
  plan: null,
  changed_files: [],
  test_output: null,
  pr_url: null,
  reviewer_comments: [],
  langfuse_trace_url: null,
  context_packet: null,
};

/* ----------------------------------- evals ------------------------------------ */

export const evalRuns: EvalRun[] = [
  {
    id: "eval-1",
    mode: "comparison",
    status: "completed",
    started_at: "2026-07-02T06:00:00Z",
    finished_at: "2026-07-02T06:12:00Z",
    summary: {
      avg_score: 0.86,
      pass_rate: 0.9,
      total_tokens: 48_200,
      baseline_avg_score: 0.71,
      baseline_total_tokens: 90_500,
      regression: true,
      regressed_task_names: ["golden-payments-refund"],
    },
  },
  {
    id: "eval-2",
    mode: "context_engine",
    status: "completed",
    started_at: "2026-06-25T06:00:00Z",
    finished_at: "2026-06-25T06:09:00Z",
    summary: {
      avg_score: 0.82,
      pass_rate: 0.8,
      total_tokens: 51_000,
      baseline_avg_score: null,
      baseline_total_tokens: null,
      regression: false,
      regressed_task_names: [],
    },
  },
  {
    id: "eval-3",
    mode: "baseline",
    status: "running",
    started_at: "2026-07-02T07:00:00Z",
    finished_at: null,
    summary: null,
  },
];

export const evalRunsPage: Paginated<EvalRun> = paginate(evalRuns);

export const evalRunDetail: EvalRunDetail = {
  ...evalRuns[0],
  golden_tasks_total: 2,
  results: [
    {
      task_name: "golden-webhook-dedupe",
      mode: "baseline",
      score: 0.62,
      passed: true,
      explanation: "Found the runbook but missed the ADR.",
      tokens_used: 41_000,
      details: { precision: 0.6, recall: 0.55, keyword_hits: 3, citations_ok: true },
    },
    {
      task_name: "golden-webhook-dedupe",
      mode: "context_engine",
      score: 0.91,
      passed: true,
      explanation: "Selected ADR-014 and the incident postmortem.",
      tokens_used: 22_000,
      details: { precision: 0.9, recall: 0.88, keyword_hits: 6, citations_ok: true },
    },
    {
      task_name: "golden-payments-refund",
      mode: "baseline",
      score: 0.74,
      passed: true,
      explanation: "Baseline retrieved the refund policy doc.",
      tokens_used: 49_500,
      details: { precision: 0.7, recall: 0.66, keyword_hits: 4, citations_ok: true },
    },
    {
      task_name: "golden-payments-refund",
      mode: "context_engine",
      score: 0.41,
      passed: false,
      explanation:
        "Missed the refund-ledger ADR entirely; cited a stale confluence page instead.",
      tokens_used: 26_200,
      details: { precision: 0.4, recall: 0.3, keyword_hits: 1, citations_ok: false },
    },
  ],
};

export const goldenTasks: GoldenTasksResponse = {
  items: [
    {
      id: "gt-1",
      name: "golden-webhook-dedupe",
      task: "Explain how duplicate webhook events are deduplicated in payments-api and cite the relevant ADR",
      repo: "org/payments",
      service: "payments-api",
      is_active: true,
      expected_keywords: ["idempotency", "ADR-014", "dedupe"],
    },
    {
      id: "gt-2",
      name: "golden-payments-refund",
      task: "Describe the refund ledger flow",
      repo: null,
      service: "payments-api",
      is_active: false,
      expected_keywords: ["refund", "ledger"],
    },
  ],
  total: 2,
};

/* ---------------------------------- sources ----------------------------------- */

export const sources: Source[] = [
  {
    id: "src-1",
    type: "github",
    name: "backend monorepo",
    enabled: true,
    sync_status: "ok",
    last_synced_at: "2026-07-02T05:00:00Z",
    last_error: null,
    document_count: 12_480,
    acl_sync_status: "ok",
    authority_rank: 90,
    freshness_window_days: 30,
    config: {
      mode: "live",
      token: "•••7a2c",
      org: "example-org",
      repos: ["backend", "shared-libs"],
      team_name: "Platform",
    },
    sync_state: { pr_cursor: "2026-07-01T00:00:00Z", issues_cursor: "2026-06-30T00:00:00Z" },
  },
  {
    id: "src-2",
    type: "jira",
    name: "payments board",
    enabled: true,
    sync_status: "error",
    last_synced_at: "2026-06-30T22:00:00Z",
    last_error: "401 Unauthorized: token expired for jira.example.com",
    document_count: 3_210,
    acl_sync_status: "pending",
    authority_rank: 60,
    freshness_window_days: 14,
    config: { mode: "demo" },
    sync_state: {},
  },
  {
    id: "src-3",
    type: "slack",
    name: "#incidents archive",
    enabled: false,
    sync_status: "idle",
    last_synced_at: null,
    last_error: null,
    document_count: 0,
    acl_sync_status: "pending",
    authority_rank: 30,
    freshness_window_days: 7,
    config: { mode: "demo" },
    sync_state: {},
  },
];

export const sourcesResponse: ItemsResponse<Source> = { items: sources };

/* --------------------------------- sync runs ------------------------------------ */

export const syncRunOk: SyncRun = {
  id: "run-a1",
  trigger: "scheduled",
  status: "ok",
  started_at: "2026-07-02T05:00:00Z",
  finished_at: "2026-07-02T05:03:12Z",
  docs_upserted: 42,
  docs_skipped: 118,
  docs_pruned: 2,
  chunks_indexed: 340,
  errors: [],
};

export const syncRunError: SyncRun = {
  id: "run-a2",
  trigger: "manual",
  status: "error",
  started_at: "2026-06-30T22:00:00Z",
  finished_at: "2026-06-30T22:01:45Z",
  docs_upserted: 5,
  docs_skipped: 3,
  docs_pruned: 0,
  chunks_indexed: 40,
  errors: [
    { external_id: "issue-441", error: "401 Unauthorized: token expired" },
    { external_id: null, error: "Timed out fetching page 3" },
  ],
};

export const syncRunRunning: SyncRun = {
  id: "run-a3",
  trigger: "manual",
  status: "running",
  started_at: "2026-07-03T09:00:00Z",
  finished_at: null,
  docs_upserted: 0,
  docs_skipped: 0,
  docs_pruned: 0,
  chunks_indexed: 0,
  errors: [],
};

export const syncRunsResponse: ItemsResponse<SyncRun> = {
  items: [syncRunError, syncRunOk],
};

/** Sources list where src-1 carries a last_sync_run summary. */
export const sourcesWithLastRun: Source[] = [
  { ...sources[0], last_sync_run: syncRunOk },
  { ...sources[1], last_sync_run: syncRunError },
  { ...sources[2], last_sync_run: null },
];

export const sourcesWithLastRunResponse: ItemsResponse<Source> = {
  items: sourcesWithLastRun,
};

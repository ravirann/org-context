/**
 * Realistic fixtures for the /graph and /heatmaps pages.
 */
import type {
  ContextDebtHeatmapResponse,
  GraphResponse,
  HeatmapUsersResponse,
  Me,
  OwnershipResponse,
  PathResponse,
} from "@/lib/types";

export const meFixture: Me = {
  id: "u-admin",
  email: "admin@example.com",
  name: "Ada Admin",
  role: "admin",
  team_name: "Platform",
};

/* ---------------------------------- graph ------------------------------------ */

export const graphFixture: GraphResponse = {
  nodes: [
    {
      id: "n-repo-1",
      type: "repo",
      label: "payments-api",
      ref: null,
      stale: false,
      conflicted: false,
      degree: 4,
    },
    {
      id: "n-svc-1",
      type: "service",
      label: "payments",
      ref: null,
      stale: false,
      conflicted: false,
      degree: 2,
    },
    {
      id: "n-user-1",
      type: "user",
      label: "Priya Nair",
      ref: null,
      stale: false,
      conflicted: false,
      degree: 1,
    },
    {
      id: "n-team-1",
      type: "team",
      label: "Payments Squad",
      ref: null,
      stale: false,
      conflicted: false,
      degree: 2,
    },
    {
      id: "n-doc-1",
      type: "doc",
      label: "Payment retries runbook",
      ref: "0f1e2d3c-0000-4000-8000-000000000001",
      stale: true,
      conflicted: false,
      degree: 2,
    },
    {
      id: "n-doc-2",
      type: "doc",
      label: "Refunds API guide",
      ref: "0f1e2d3c-0000-4000-8000-000000000002",
      stale: false,
      conflicted: true,
      degree: 1,
    },
    {
      id: "n-pkt-1",
      type: "context_packet",
      label: "Fix retry backoff bug",
      ref: "0f1e2d3c-0000-4000-8000-00000000000a",
      stale: false,
      conflicted: false,
      degree: 2,
    },
    {
      id: "n-run-1",
      type: "agent_run",
      label: "claude-code run #42",
      ref: "0f1e2d3c-0000-4000-8000-00000000000b",
      stale: false,
      conflicted: false,
      degree: 1,
    },
  ],
  edges: [
    { id: "e-1", source: "n-team-1", target: "n-repo-1", type: "owns", weight: 1 },
    { id: "e-2", source: "n-user-1", target: "n-team-1", type: "member_of", weight: 1 },
    { id: "e-3", source: "n-repo-1", target: "n-doc-1", type: "references", weight: 2 },
    { id: "e-4", source: "n-repo-1", target: "n-svc-1", type: "depends_on", weight: 1 },
    { id: "e-5", source: "n-doc-2", target: "n-svc-1", type: "references", weight: 1 },
    { id: "e-6", source: "n-pkt-1", target: "n-doc-1", type: "uses", weight: 3 },
    { id: "e-7", source: "n-run-1", target: "n-pkt-1", type: "uses", weight: 1 },
  ],
};

export const pathFixture: PathResponse = {
  found: true,
  path: [
    { node: graphFixture.nodes[2], edge: null }, // Priya Nair
    { node: graphFixture.nodes[3], edge: graphFixture.edges[1] }, // member_of → team
    { node: graphFixture.nodes[0], edge: graphFixture.edges[0] }, // owns → repo
    { node: graphFixture.nodes[4], edge: graphFixture.edges[2] }, // references → doc
  ],
};

export const noPathFixture: PathResponse = { found: false, path: [] };

/* --------------------------------- heatmaps ---------------------------------- */

/** 14 consecutive days ending 2026-07-03. */
export const heatmapDays: string[] = Array.from({ length: 14 }, (_, i) => {
  const date = new Date(Date.UTC(2026, 5, 20 + i));
  return date.toISOString().slice(0, 10);
});

function cells(values: number[]): { day: string; value: number }[] {
  return heatmapDays.map((day, i) => ({ day, value: values[i] ?? 0 }));
}

export const heatmapUsersFixture: HeatmapUsersResponse = {
  days: heatmapDays,
  rows: [
    {
      user_id: "u-1",
      user_name: "Priya Nair",
      team_name: "Payments Squad",
      cells: cells([2, 0, 3, 9, 1, 0, 0, 4, 2, 5, 1, 0, 2, 3]),
      total: 32,
    },
    {
      user_id: "u-2",
      user_name: "Marco Ruiz",
      team_name: "Payments Squad",
      cells: cells([1, 1, 0, 2, 0, 0, 1, 3, 0, 2, 4, 1, 0, 1]),
      total: 16,
    },
    {
      user_id: "u-3",
      user_name: "Lena Fischer",
      team_name: "Platform",
      cells: cells([0, 0, 1, 0, 2, 0, 0, 0, 1, 0, 0, 3, 0, 0]),
      total: 7,
    },
  ],
};

export const ownershipFixture: OwnershipResponse = {
  rows: [
    {
      key: "payments-api",
      owner_team: "Payments Squad",
      doc_count: 42,
      owner_user_names: ["Priya Nair", "Marco Ruiz"],
      coverage_score: 0.86,
      last_activity_at: "2026-07-01T09:00:00Z",
    },
    {
      key: "billing-svc",
      owner_team: null,
      doc_count: 7,
      owner_user_names: [],
      coverage_score: 0.31,
      last_activity_at: "2026-05-12T10:30:00Z",
    },
    {
      key: "web-app",
      owner_team: "Platform",
      doc_count: 19,
      owner_user_names: ["Lena Fischer", "Priya Nair", "Marco Ruiz"],
      coverage_score: 0.55,
      last_activity_at: "2026-06-20T15:45:00Z",
    },
  ],
};

export const contextDebtFixture: ContextDebtHeatmapResponse = {
  rows: [
    {
      key: "payments-api",
      repo: "payments-api",
      service: null,
      team_name: "Payments Squad",
      stale_count: 12,
      missing_owner: false,
      conflict_count: 3,
      rejected_count: 8,
      failed_runs: 2,
      debt_score: 0.91,
    },
    {
      key: "billing-svc",
      repo: null,
      service: "billing-svc",
      team_name: null,
      stale_count: 4,
      missing_owner: true,
      conflict_count: 1,
      rejected_count: 0,
      failed_runs: 0,
      debt_score: 0.42,
    },
    {
      key: "web-app",
      repo: "web-app",
      service: null,
      team_name: "Platform",
      stale_count: 0,
      missing_owner: false,
      conflict_count: 0,
      rejected_count: 1,
      failed_runs: 0,
      debt_score: 0.12,
    },
  ],
};

/**
 * Central React Query key factory. Always use these instead of ad-hoc arrays
 * so invalidation stays consistent across pages.
 */
export const queryKeys = {
  me: (apiKey?: string) => ["me", apiKey ?? "current"] as const,

  dashboardSummary: () => ["dashboard", "summary"] as const,
  dashboardTrends: (days: number) => ["dashboard", "trends", days] as const,

  search: (request: unknown) => ["search", request] as const,
  document: (id: string) => ["documents", id] as const,

  packets: (filters: unknown) => ["context-packets", "list", filters] as const,
  packet: (id: string) => ["context-packets", "detail", id] as const,

  graph: (params: unknown) => ["relationships", "graph", params] as const,
  path: (fromId: string, toId: string) =>
    ["relationships", "path", fromId, toId] as const,

  heatmapUsers: (params: unknown) => ["heatmaps", "users", params] as const,
  heatmapOwnership: () => ["heatmaps", "ownership"] as const,
  heatmapContextDebt: () => ["heatmaps", "context-debt"] as const,

  agentRuns: (filters: unknown) => ["agent-runs", "list", filters] as const,
  agentRun: (id: string) => ["agent-runs", "detail", id] as const,

  evals: (page: number) => ["evals", "list", page] as const,
  evalRun: (id: string) => ["evals", "detail", id] as const,
  goldenTasks: () => ["evals", "golden-tasks"] as const,

  sources: () => ["sources"] as const,

  conflicts: (filters: unknown) => ["conflicts", "list", filters] as const,
  conflict: (id: string) => ["conflicts", "detail", id] as const,

  contextDebt: () => ["context-debt"] as const,

  adminUsers: () => ["admin", "users"] as const,
  adminTeams: () => ["admin", "teams"] as const,
  adminApiKeys: () => ["admin", "api-keys"] as const,
  auditLogs: (filters: unknown) => ["admin", "audit-logs", filters] as const,
  settings: () => ["settings"] as const,
};

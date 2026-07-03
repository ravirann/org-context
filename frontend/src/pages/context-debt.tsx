import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip as RechartsTooltip,
  XAxis,
  YAxis,
} from "recharts";

import { DebtCard } from "@/components/debt/debt-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/ui/error-state";
import { PageHeader } from "@/components/ui/page-header";
import { PermissionDenied } from "@/components/ui/permission-denied";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { usePageTitle } from "@/hooks/use-page-title";
import { api, isApiError } from "@/lib/api";
import { queryKeys } from "@/lib/queryKeys";
import type { ContextDebtReport, StaleDocsRow } from "@/lib/types";
import { formatDate } from "@/lib/utils";

const SECTIONS = [
  { id: "stale-docs", label: "Stale" },
  { id: "missing-owners", label: "Owners" },
  { id: "undocumented-apis", label: "APIs" },
  { id: "repeated-misses", label: "Misses" },
  { id: "failed-agent-areas", label: "Failures" },
  { id: "never-used-docs", label: "Unused" },
  { id: "frequently-rejected", label: "Rejected" },
  { id: "conflicts-by-source", label: "Conflicts" },
] as const;

const CHART_COLORS = [
  "var(--chart-1)",
  "var(--chart-2)",
  "var(--chart-3)",
  "var(--chart-4)",
  "var(--chart-5)",
  "var(--chart-6)",
];

function staleRowLabel(row: StaleDocsRow): string {
  return row.repo ?? row.service ?? row.team_name ?? "unassigned";
}

function StaleDocsCard({ rows }: { rows: StaleDocsRow[] }) {
  const [view, setView] = useState<"chart" | "table">("chart");
  const data = rows.map((row) => ({ ...row, label: staleRowLabel(row) }));

  return (
    <DebtCard
      id="stale-docs"
      title="Stale docs by repo / service / team"
      description="Documents past their freshness window, grouped by owner area."
      count={rows.reduce((acc, r) => acc + r.count, 0)}
      isEmpty={rows.length === 0}
      emptyLabel="None found — every document is inside its freshness window."
      actions={
        <>
          <Button
            variant={view === "chart" ? "secondary" : "ghost"}
            size="sm"
            aria-pressed={view === "chart"}
            onClick={() => setView("chart")}
          >
            Chart
          </Button>
          <Button
            variant={view === "table" ? "secondary" : "ghost"}
            size="sm"
            aria-pressed={view === "table"}
            onClick={() => setView("table")}
          >
            Table
          </Button>
        </>
      }
    >
      {view === "chart" ? (
        <div
          data-testid="stale-docs-chart"
          style={{ height: Math.max(160, data.length * 32) }}
        >
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data} layout="vertical" margin={{ left: 8, right: 8 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" horizontal={false} />
              <XAxis type="number" allowDecimals={false} tick={{ fontSize: 10 }} />
              <YAxis
                type="category"
                dataKey="label"
                width={120}
                tick={{ fontSize: 10 }}
              />
              <RechartsTooltip
                cursor={{ fill: "var(--muted)" }}
                contentStyle={{
                  background: "var(--card)",
                  border: "1px solid var(--border)",
                  borderRadius: 6,
                  fontSize: 11,
                }}
              />
              <Bar dataKey="count" fill="var(--chart-1)" radius={[0, 3, 3, 0]} barSize={16} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <Table data-testid="stale-docs-table">
          <TableHeader>
            <TableRow>
              <TableHead>Area</TableHead>
              <TableHead>Team</TableHead>
              <TableHead className="text-right">Stale docs</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.map((row) => (
              <TableRow key={row.label}>
                <TableCell className="font-mono text-xs">{row.label}</TableCell>
                <TableCell className="text-muted-foreground">
                  {row.team_name ?? "—"}
                </TableCell>
                <TableCell className="text-right tabular-nums">{row.count}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </DebtCard>
  );
}

export default function ContextDebtPage() {
  usePageTitle("Context Debt");

  const query = useQuery({
    queryKey: queryKeys.contextDebt(),
    queryFn: () => api.get<ContextDebtReport>("/v1/context-debt"),
  });

  if (query.isPending) {
    return (
      <>
        <PageHeader title="Context Debt" />
        <div data-testid="page-context-debt">
          <div className="grid gap-4 xl:grid-cols-2" data-testid="context-debt-loading">
            {Array.from({ length: 8 }).map((_, i) => (
              <Skeleton key={i} className="h-48 w-full" />
            ))}
          </div>
        </div>
      </>
    );
  }

  if (query.isError) {
    const is403 = isApiError(query.error) && query.error.status === 403;
    return (
      <>
        <PageHeader title="Context Debt" />
        <div data-testid="page-context-debt">
          {is403 ? (
            <PermissionDenied />
          ) : (
            <ErrorState
              message={
                isApiError(query.error)
                  ? query.error.detail
                  : "Failed to load the context debt report"
              }
              onRetry={() => void query.refetch()}
            />
          )}
        </div>
      </>
    );
  }

  const report = query.data;

  return (
    <>
      <PageHeader
        title="Context Debt"
        description="Where organizational knowledge is stale, missing, contested or unused."
      />
      <div data-testid="page-context-debt" className="space-y-4">
        <nav aria-label="Report sections" className="flex flex-wrap gap-1.5">
          {SECTIONS.map((section) => (
            <a
              key={section.id}
              href={`#${section.id}`}
              className="rounded-full border px-2.5 py-0.5 text-[11px] text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
            >
              {section.label}
            </a>
          ))}
        </nav>

        <div className="grid items-start gap-4 xl:grid-cols-2">
          <StaleDocsCard rows={report.stale_docs} />

          <DebtCard
            id="missing-owners"
            title="Missing owners"
            description="Repos and services whose documents have nobody accountable."
            count={report.missing_owners.length}
            isEmpty={report.missing_owners.length === 0}
            emptyLabel="None found — everything has an owner."
          >
            <ul className="space-y-1.5">
              {report.missing_owners.map((row) => (
                <li
                  key={row.key}
                  className="flex items-center justify-between gap-2 rounded-md border border-destructive/30 bg-destructive/5 px-2.5 py-1.5"
                >
                  <code className="font-mono text-xs">{row.key}</code>
                  <span className="text-xs text-muted-foreground">
                    {row.doc_count} doc{row.doc_count === 1 ? "" : "s"}
                  </span>
                </li>
              ))}
            </ul>
          </DebtCard>

          <DebtCard
            id="undocumented-apis"
            title="Undocumented APIs"
            description="Endpoints referenced in code or traffic with no matching docs."
            count={report.undocumented_apis.length}
            isEmpty={report.undocumented_apis.length === 0}
          >
            <div className="flex flex-wrap gap-1.5">
              {report.undocumented_apis.map((apiRow) => (
                <Badge
                  key={`${apiRow.service}:${apiRow.name}`}
                  variant="outline"
                  className="font-mono text-[10px]"
                >
                  {apiRow.name}
                  <span className="text-muted-foreground">@ {apiRow.service}</span>
                </Badge>
              ))}
            </div>
          </DebtCard>

          <DebtCard
            id="repeated-misses"
            title="Repeated context misses"
            description="Queries that repeatedly returned nothing useful."
            count={report.repeated_misses.length}
            isEmpty={report.repeated_misses.length === 0}
          >
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Query</TableHead>
                  <TableHead className="text-right">Misses</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {report.repeated_misses.map((row) => (
                  <TableRow key={row.query}>
                    <TableCell className="font-mono text-xs">{row.query}</TableCell>
                    <TableCell className="text-right tabular-nums">{row.count}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </DebtCard>

          <DebtCard
            id="failed-agent-areas"
            title="Failed-agent areas"
            description="Repos and services where agent runs fail most often."
            count={report.failed_agent_areas.length}
            isEmpty={report.failed_agent_areas.length === 0}
          >
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Area</TableHead>
                  <TableHead className="text-right">Failed / total</TableHead>
                  <TableHead className="w-32">Failure rate</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {report.failed_agent_areas.map((row) => {
                  const label = row.repo ?? row.service ?? "unknown";
                  const ratio = row.total > 0 ? row.failed / row.total : 0;
                  return (
                    <TableRow key={label}>
                      <TableCell className="font-mono text-xs">{label}</TableCell>
                      <TableCell className="text-right tabular-nums">
                        {row.failed} / {row.total}
                      </TableCell>
                      <TableCell>
                        <div
                          className="h-1.5 w-full overflow-hidden rounded-full bg-muted"
                          role="img"
                          aria-label={`${Math.round(ratio * 100)}% failure rate`}
                        >
                          <div
                            className="h-full rounded-full bg-destructive"
                            style={{ width: `${Math.min(100, ratio * 100)}%` }}
                          />
                        </div>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </DebtCard>

          <DebtCard
            id="never-used-docs"
            title="Docs never used"
            description="Indexed documents that no context packet has ever selected."
            count={report.never_used_docs.length}
            isEmpty={report.never_used_docs.length === 0}
          >
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Title</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Created</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {report.never_used_docs.map((doc) => (
                  <TableRow key={doc.id}>
                    <TableCell className="max-w-64">
                      <Link
                        to={`/explorer/documents/${doc.id}`}
                        className="line-clamp-1 font-medium text-primary hover:underline"
                      >
                        {doc.title}
                      </Link>
                    </TableCell>
                    <TableCell>
                      <Badge variant="secondary">{doc.doc_type}</Badge>
                    </TableCell>
                    <TableCell className="whitespace-nowrap text-xs text-muted-foreground">
                      {formatDate(doc.created_at)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </DebtCard>

          <DebtCard
            id="frequently-rejected"
            title="Docs frequently rejected"
            description="Retrieved often but rejected by the compiler or by feedback."
            count={report.frequently_rejected_docs.length}
            isEmpty={report.frequently_rejected_docs.length === 0}
          >
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Title</TableHead>
                  <TableHead className="text-right">Rejections</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {report.frequently_rejected_docs.map((doc) => (
                  <TableRow key={doc.id}>
                    <TableCell className="max-w-64">
                      <Link
                        to={`/explorer/documents/${doc.id}`}
                        className="line-clamp-1 font-medium text-primary hover:underline"
                      >
                        {doc.title}
                      </Link>
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {doc.rejection_count}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </DebtCard>

          <DebtCard
            id="conflicts-by-source"
            title="Conflicts by source type"
            description="Which source types most often disagree with the rest."
            count={report.conflicts_by_source_type.reduce((acc, r) => acc + r.count, 0)}
            isEmpty={report.conflicts_by_source_type.length === 0}
          >
            <div data-testid="conflicts-by-source-chart" style={{ height: 200 }}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={report.conflicts_by_source_type}
                  margin={{ left: 8, right: 8 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
                  <XAxis dataKey="source_type" tick={{ fontSize: 10 }} />
                  <YAxis allowDecimals={false} tick={{ fontSize: 10 }} width={28} />
                  <RechartsTooltip
                    cursor={{ fill: "var(--muted)" }}
                    contentStyle={{
                      background: "var(--card)",
                      border: "1px solid var(--border)",
                      borderRadius: 6,
                      fontSize: 11,
                    }}
                  />
                  <Bar dataKey="count" radius={[3, 3, 0, 0]} barSize={28}>
                    {report.conflicts_by_source_type.map((row, index) => (
                      <Cell
                        key={row.source_type}
                        fill={CHART_COLORS[index % CHART_COLORS.length]}
                      />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
            <ul className="mt-2 flex flex-wrap gap-x-3 gap-y-1">
              {report.conflicts_by_source_type.map((row, index) => (
                <li key={row.source_type} className="flex items-center gap-1.5 text-[11px]">
                  <span
                    aria-hidden="true"
                    className="size-2 rounded-sm"
                    style={{ background: CHART_COLORS[index % CHART_COLORS.length] }}
                  />
                  <span className="font-mono">{row.source_type}</span>
                  <span className="tabular-nums text-muted-foreground">{row.count}</span>
                </li>
              ))}
            </ul>
          </DebtCard>
        </div>
      </div>
    </>
  );
}

import { useQuery } from "@tanstack/react-query";
import { ArrowUpDown, Download } from "lucide-react";
import { useMemo, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";

import { aggregateByTeam } from "@/components/heatmaps/aggregate";
import {
  debtCsv,
  downloadCsv,
  ownershipCsv,
  teamHeatmapCsv,
  userHeatmapCsv,
} from "@/components/heatmaps/csv";
import { RANGE_PRESETS, dateRange, isoDaysAgo } from "@/components/heatmaps/date-range";
import {
  HeatmapGrid,
  intensityStep,
  type HeatmapGridRow,
} from "@/components/heatmaps/heatmap-grid";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { PermissionDenied } from "@/components/ui/permission-denied";
import { ScoreBadge } from "@/components/ui/score-badge";
import { Select } from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useToast } from "@/components/ui/toast";
import { useDebounce } from "@/hooks/use-debounce";
import { useMe } from "@/hooks/use-me";
import { usePageTitle } from "@/hooks/use-page-title";
import { api, isApiError } from "@/lib/api";
import { queryKeys } from "@/lib/queryKeys";
import type {
  ContextDebtHeatmapResponse,
  ContextDebtRow,
  HeatmapMetric,
  HeatmapUsersResponse,
  OwnershipResponse,
  OwnershipRow,
} from "@/lib/types";
import { cn, formatDate, timeAgo } from "@/lib/utils";

type Tab = "users" | "teams" | "ownership" | "debt";

const METRIC_OPTIONS: Array<{ value: HeatmapMetric; label: string }> = [
  { value: "all", label: "All metrics" },
  { value: "commit", label: "Commits" },
  { value: "pr", label: "PRs" },
  { value: "review", label: "Reviews" },
  { value: "doc_edit", label: "Doc edits" },
  { value: "ticket", label: "Tickets" },
  { value: "incident", label: "Incidents" },
  { value: "packet_use", label: "Packet uses" },
];

function metricLabel(metric: HeatmapMetric): string {
  return METRIC_OPTIONS.find((m) => m.value === metric)?.label ?? metric;
}

interface CellDrilldown {
  name: string;
  team: string | null;
  day: string;
  value: number;
}

export default function HeatmapsPage() {
  usePageTitle("Heatmaps");
  const { data: me } = useMe();
  const { toast } = useToast();

  const [tab, setTab] = useState<Tab>("users");
  const [days, setDays] = useState<number>(30);
  const [metric, setMetric] = useState<HeatmapMetric>("all");
  const [teamId, setTeamId] = useState("");
  const [repo, setRepo] = useState("");
  const [service, setService] = useState("");
  const debouncedTeamId = useDebounce(teamId, 250);
  const debouncedRepo = useDebounce(repo, 250);
  const debouncedService = useDebounce(service, 250);

  const [cellDrill, setCellDrill] = useState<CellDrilldown | null>(null);
  const [debtDrill, setDebtDrill] = useState<ContextDebtRow | null>(null);
  const [ownSort, setOwnSort] = useState<{
    key: "coverage_score" | "doc_count";
    desc: boolean;
  }>({ key: "coverage_score", desc: true });

  const range = useMemo(() => dateRange(days), [days]);

  const usersParams = useMemo(
    () => ({
      from: range.from,
      to: range.to,
      metric,
      team_id: debouncedTeamId || undefined,
      repo: debouncedRepo || undefined,
      service: debouncedService || undefined,
    }),
    [range, metric, debouncedTeamId, debouncedRepo, debouncedService],
  );

  const usersQuery = useQuery({
    queryKey: queryKeys.heatmapUsers(usersParams),
    queryFn: () =>
      api.get<HeatmapUsersResponse>("/v1/heatmaps/users", usersParams),
    enabled: tab === "users" || tab === "teams",
  });

  const ownershipQuery = useQuery({
    queryKey: queryKeys.heatmapOwnership(),
    queryFn: () => api.get<OwnershipResponse>("/v1/heatmaps/ownership"),
    enabled: tab === "ownership",
  });

  const debtQuery = useQuery({
    queryKey: queryKeys.heatmapContextDebt(),
    queryFn: () =>
      api.get<ContextDebtHeatmapResponse>("/v1/heatmaps/context-debt"),
    enabled: tab === "debt",
  });

  const userRows: HeatmapGridRow[] = useMemo(
    () =>
      (usersQuery.data?.rows ?? [])
        .slice()
        .sort((a, b) => b.total - a.total || a.user_name.localeCompare(b.user_name))
        .map((row) => ({
          id: row.user_id,
          name: row.user_name,
          subtext: row.team_name,
          cells: row.cells,
          total: row.total,
        })),
    [usersQuery.data],
  );

  const teamRows: HeatmapGridRow[] = useMemo(
    () =>
      aggregateByTeam(usersQuery.data?.rows ?? []).map((row) => ({
        id: row.team_name,
        name: row.team_name,
        subtext: `${row.user_count} user${row.user_count === 1 ? "" : "s"}`,
        cells: row.cells,
        total: row.total,
      })),
    [usersQuery.data],
  );

  const ownershipRows = useMemo(() => {
    const rows = (ownershipQuery.data?.rows ?? []).slice();
    const dir = ownSort.desc ? -1 : 1;
    rows.sort((a, b) => dir * (a[ownSort.key] - b[ownSort.key]));
    return rows;
  }, [ownershipQuery.data, ownSort]);

  const debtRows = debtQuery.data?.rows ?? [];

  const handleExport = () => {
    let csv: string | null = null;
    if (tab === "users" && usersQuery.data) {
      csv = userHeatmapCsv(usersQuery.data.rows, usersQuery.data.days);
    } else if (tab === "teams" && usersQuery.data) {
      csv = teamHeatmapCsv(
        aggregateByTeam(usersQuery.data.rows),
        usersQuery.data.days,
      );
    } else if (tab === "ownership" && ownershipQuery.data) {
      csv = ownershipCsv(ownershipQuery.data.rows);
    } else if (tab === "debt" && debtQuery.data) {
      csv = debtCsv(debtQuery.data.rows);
    }
    if (!csv) {
      toast({ title: "Nothing to export yet", variant: "info" });
      return;
    }
    downloadCsv(`heatmap-${tab}-${isoDaysAgo(0)}.csv`, csv);
  };

  const toggleOwnSort = (key: "coverage_score" | "doc_count") =>
    setOwnSort((prev) =>
      prev.key === key ? { key, desc: !prev.desc } : { key, desc: true },
    );

  const activityControls = tab === "users" || tab === "teams";

  return (
    <>
      <PageHeader
        title="Heatmaps"
        description="Activity, ownership and context-debt intensity across the org."
        actions={
          <Button size="sm" variant="outline" onClick={handleExport}>
            <Download aria-hidden="true" /> Export CSV
          </Button>
        }
      />
      <div data-testid="page-heatmaps" className="flex flex-col gap-3">
        <Tabs value={tab} onValueChange={(value) => setTab(value as Tab)}>
          <div className="flex flex-wrap items-center gap-2">
            <TabsList>
              <TabsTrigger value="users">User activity</TabsTrigger>
              <TabsTrigger value="teams">Team activity</TabsTrigger>
              <TabsTrigger value="ownership">Ownership</TabsTrigger>
              <TabsTrigger value="debt">Context debt</TabsTrigger>
            </TabsList>
            {activityControls ? (
              <div className="flex flex-wrap items-center gap-2">
                <Select
                  aria-label="Date range"
                  value={String(days)}
                  onChange={(e) => setDays(Number(e.target.value))}
                  className="w-36"
                >
                  {RANGE_PRESETS.map((preset) => (
                    <option key={preset} value={preset}>
                      Last {preset} days
                    </option>
                  ))}
                </Select>
                <Select
                  aria-label="Metric"
                  value={metric}
                  onChange={(e) => setMetric(e.target.value as HeatmapMetric)}
                  className="w-36"
                >
                  {METRIC_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </Select>
                <Input
                  aria-label="Filter by team id"
                  placeholder="Team ID"
                  value={teamId}
                  onChange={(e) => setTeamId(e.target.value)}
                  className="w-32"
                />
                <Input
                  aria-label="Filter by repo"
                  placeholder="Repo"
                  value={repo}
                  onChange={(e) => setRepo(e.target.value)}
                  className="w-32"
                />
                <Input
                  aria-label="Filter by service"
                  placeholder="Service"
                  value={service}
                  onChange={(e) => setService(e.target.value)}
                  className="w-32"
                />
              </div>
            ) : null}
          </div>

          {/* ----------------------------- user activity ---------------------------- */}
          <TabsContent value="users">
            <QueryState query={usersQuery} role={me?.role}>
              {userRows.length === 0 ? (
                <EmptyState
                  title="No activity"
                  description="No user activity in the selected range and filters."
                />
              ) : (
                <HeatmapGrid
                  data-testid="user-heatmap"
                  rows={userRows}
                  days={usersQuery.data?.days ?? []}
                  onCellClick={(row, cell) =>
                    setCellDrill({
                      name: row.name,
                      team: row.subtext ?? null,
                      day: cell.day,
                      value: cell.value,
                    })
                  }
                />
              )}
            </QueryState>
          </TabsContent>

          {/* ----------------------------- team activity ---------------------------- */}
          <TabsContent value="teams">
            <QueryState query={usersQuery} role={me?.role}>
              {teamRows.length === 0 ? (
                <EmptyState
                  title="No activity"
                  description="No team activity in the selected range and filters."
                />
              ) : (
                <HeatmapGrid
                  data-testid="team-heatmap"
                  rows={teamRows}
                  days={usersQuery.data?.days ?? []}
                  onCellClick={(row, cell) =>
                    setCellDrill({
                      name: row.name,
                      team: null,
                      day: cell.day,
                      value: cell.value,
                    })
                  }
                />
              )}
            </QueryState>
          </TabsContent>

          {/* ------------------------------- ownership ------------------------------ */}
          <TabsContent value="ownership">
            <QueryState query={ownershipQuery} role={me?.role}>
              {ownershipRows.length === 0 ? (
                <EmptyState
                  title="No ownership data"
                  description="No repos or services with ownership signals yet."
                />
              ) : (
                <div className="overflow-x-auto rounded-lg border">
                  <Table data-testid="ownership-table">
                    <TableHeader>
                      <TableRow>
                        <TableHead>Key</TableHead>
                        <TableHead>Owner team</TableHead>
                        <TableHead
                          aria-sort={
                            ownSort.key === "doc_count"
                              ? ownSort.desc
                                ? "descending"
                                : "ascending"
                              : "none"
                          }
                        >
                          <button
                            type="button"
                            className="inline-flex items-center gap-1"
                            onClick={() => toggleOwnSort("doc_count")}
                          >
                            Docs <ArrowUpDown className="size-3" aria-hidden="true" />
                          </button>
                        </TableHead>
                        <TableHead>Owners</TableHead>
                        <TableHead
                          aria-sort={
                            ownSort.key === "coverage_score"
                              ? ownSort.desc
                                ? "descending"
                                : "ascending"
                              : "none"
                          }
                        >
                          <button
                            type="button"
                            className="inline-flex items-center gap-1"
                            onClick={() => toggleOwnSort("coverage_score")}
                          >
                            Coverage{" "}
                            <ArrowUpDown className="size-3" aria-hidden="true" />
                          </button>
                        </TableHead>
                        <TableHead>Last activity</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {ownershipRows.map((row) => (
                        <OwnershipTableRow key={row.key} row={row} />
                      ))}
                    </TableBody>
                  </Table>
                </div>
              )}
            </QueryState>
          </TabsContent>

          {/* ------------------------------ context debt ---------------------------- */}
          <TabsContent value="debt">
            <QueryState query={debtQuery} role={me?.role}>
              {debtRows.length === 0 ? (
                <EmptyState
                  title="No context debt"
                  description="Nothing stale, conflicted or failing right now."
                />
              ) : (
                <DebtMatrix rows={debtRows} onRowClick={setDebtDrill} />
              )}
            </QueryState>
          </TabsContent>
        </Tabs>
      </div>

      {/* ---------------------------- drilldown dialogs --------------------------- */}
      <Dialog
        open={cellDrill !== null}
        onOpenChange={(open) => !open && setCellDrill(null)}
      >
        <DialogContent data-testid="cell-drilldown">
          {cellDrill ? (
            <>
              <DialogHeader>
                <DialogTitle>{cellDrill.name}</DialogTitle>
                <DialogDescription>
                  {formatDate(cellDrill.day)}
                  {cellDrill.team ? ` · ${cellDrill.team}` : ""}
                </DialogDescription>
              </DialogHeader>
              <dl className="grid grid-cols-2 gap-x-3 gap-y-1 text-sm">
                <dt className="text-muted-foreground">Metric</dt>
                <dd>{metricLabel(metric)}</dd>
                <dt className="text-muted-foreground">Day</dt>
                <dd className="tabular-nums">{cellDrill.day}</dd>
                <dt className="text-muted-foreground">Value</dt>
                <dd className="tabular-nums">{cellDrill.value}</dd>
              </dl>
              <div>
                <Link
                  to={`/graph?q=${encodeURIComponent(cellDrill.name)}`}
                  className={buttonVariants({ variant: "outline", size: "sm" })}
                >
                  View user in graph
                </Link>
              </div>
            </>
          ) : null}
        </DialogContent>
      </Dialog>

      <Dialog
        open={debtDrill !== null}
        onOpenChange={(open) => !open && setDebtDrill(null)}
      >
        <DialogContent data-testid="debt-drilldown">
          {debtDrill ? (
            <>
              <DialogHeader>
                <DialogTitle>{debtDrill.key}</DialogTitle>
                <DialogDescription>
                  {debtDrill.team_name ?? "No owning team"}
                </DialogDescription>
              </DialogHeader>
              <dl className="grid grid-cols-2 gap-x-3 gap-y-1 text-sm">
                <dt className="text-muted-foreground">Stale docs</dt>
                <dd className="tabular-nums">{debtDrill.stale_count}</dd>
                <dt className="text-muted-foreground">Conflicts</dt>
                <dd className="tabular-nums">{debtDrill.conflict_count}</dd>
                <dt className="text-muted-foreground">Rejected sources</dt>
                <dd className="tabular-nums">{debtDrill.rejected_count}</dd>
                <dt className="text-muted-foreground">Failed runs</dt>
                <dd className="tabular-nums">{debtDrill.failed_runs}</dd>
                <dt className="text-muted-foreground">Debt score</dt>
                <dd>
                  <DebtScoreBadge score={debtDrill.debt_score} />
                </dd>
                <dt className="text-muted-foreground">Owner</dt>
                <dd>
                  {debtDrill.missing_owner ? (
                    <Badge variant="destructive">Missing owner</Badge>
                  ) : (
                    (debtDrill.team_name ?? "—")
                  )}
                </dd>
              </dl>
              <div className="flex gap-2">
                <Link
                  to="/context-debt"
                  className={buttonVariants({ variant: "outline", size: "sm" })}
                >
                  Open context debt
                </Link>
                <Link
                  to="/conflicts"
                  className={buttonVariants({ variant: "outline", size: "sm" })}
                >
                  Open conflicts
                </Link>
              </div>
            </>
          ) : null}
        </DialogContent>
      </Dialog>
    </>
  );
}

/* -------------------------------- sub-components ------------------------------- */

interface QueryStateProps {
  query: {
    isPending: boolean;
    isError: boolean;
    error: unknown;
    refetch: () => unknown;
  };
  role: string | undefined;
  children: ReactNode;
}

/** Loading / 403 / error wrapper; renders children once data is available. */
function QueryState({ query, role, children }: QueryStateProps) {
  if (query.isPending) {
    return (
      <div data-testid="heatmap-skeleton" className="flex flex-col gap-1.5">
        {Array.from({ length: 6 }, (_, i) => (
          <Skeleton key={i} className="h-7 w-full" />
        ))}
      </div>
    );
  }
  if (query.isError) {
    if (isApiError(query.error) && query.error.status === 403) {
      return <PermissionDenied role={role} />;
    }
    return (
      <ErrorState
        message={
          isApiError(query.error) ? query.error.detail : String(query.error)
        }
        onRetry={() => void query.refetch()}
      />
    );
  }
  return <>{children}</>;
}

function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((word) => word[0]!.toUpperCase())
    .join("");
}

function OwnershipTableRow({ row }: { row: OwnershipRow }) {
  const shown = row.owner_user_names.slice(0, 4);
  const extra = row.owner_user_names.length - shown.length;
  const missing = !row.owner_team;
  return (
    <TableRow data-testid={`ownership-row-${row.key}`}>
      <TableCell className="font-medium">{row.key}</TableCell>
      <TableCell>
        {missing ? (
          <Badge variant="destructive">Missing owner</Badge>
        ) : (
          row.owner_team
        )}
      </TableCell>
      <TableCell className="tabular-nums">{row.doc_count}</TableCell>
      <TableCell>
        <span className="flex items-center gap-1">
          {shown.map((name) => (
            <span
              key={name}
              title={name}
              className="inline-flex size-5 items-center justify-center rounded-full bg-muted text-[9px] font-medium text-muted-foreground"
            >
              {initials(name)}
            </span>
          ))}
          {extra > 0 ? (
            <span className="text-[10px] text-muted-foreground">+{extra}</span>
          ) : null}
          {shown.length === 0 ? (
            <span className="text-muted-foreground">—</span>
          ) : null}
        </span>
      </TableCell>
      <TableCell>
        <ScoreBadge score={row.coverage_score} />
      </TableCell>
      <TableCell className="text-muted-foreground">
        {timeAgo(row.last_activity_at)}
      </TableCell>
    </TableRow>
  );
}

/** Inverted score badge: high debt is bad (red), low is good (green). */
function DebtScoreBadge({ score }: { score: number }) {
  const classes =
    score >= 0.66
      ? "bg-red-500/12 text-red-700 dark:text-red-400"
      : score >= 0.33
        ? "bg-amber-500/15 text-amber-700 dark:text-amber-400"
        : "bg-emerald-500/12 text-emerald-700 dark:text-emerald-400";
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium tabular-nums leading-4",
        classes,
      )}
    >
      {score.toFixed(2)}
    </span>
  );
}

const DEBT_COLUMNS = [
  { key: "stale_count", label: "Stale" },
  { key: "conflict_count", label: "Conflicts" },
  { key: "rejected_count", label: "Rejected" },
  { key: "failed_runs", label: "Failed runs" },
] as const;

interface DebtMatrixProps {
  rows: ContextDebtRow[];
  onRowClick: (row: ContextDebtRow) => void;
}

function DebtMatrix({ rows, onRowClick }: DebtMatrixProps) {
  const maxima = useMemo(() => {
    const out: Record<string, number> = {};
    for (const col of DEBT_COLUMNS) {
      out[col.key] = rows.reduce((m, r) => Math.max(m, r[col.key]), 0);
    }
    return out;
  }, [rows]);

  const cellBackground = (value: number, max: number): string => {
    const step = intensityStep(value, max);
    if (step === 0) return "transparent";
    if (step === 4) return "color-mix(in oklab, var(--chart-5) 55%, transparent)";
    return `color-mix(in oklab, var(--chart-5) ${step * 13}%, transparent)`;
  };

  return (
    <div className="overflow-x-auto rounded-lg border">
      <Table data-testid="debt-table">
        <TableHeader>
          <TableRow>
            <TableHead>Repo / service</TableHead>
            <TableHead>Team</TableHead>
            {DEBT_COLUMNS.map((col) => (
              <TableHead key={col.key} className="text-right">
                {col.label}
              </TableHead>
            ))}
            <TableHead>Owner</TableHead>
            <TableHead className="text-right">Debt score</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((row) => (
            <TableRow
              key={row.key}
              data-testid={`debt-row-${row.key}`}
              tabIndex={0}
              className="cursor-pointer"
              onClick={() => onRowClick(row)}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  onRowClick(row);
                }
              }}
            >
              <TableCell className="font-medium">{row.key}</TableCell>
              <TableCell className="text-muted-foreground">
                {row.team_name ?? "—"}
              </TableCell>
              {DEBT_COLUMNS.map((col) => (
                <TableCell
                  key={col.key}
                  className="text-right tabular-nums"
                  data-intensity={intensityStep(row[col.key], maxima[col.key])}
                  style={{
                    background: cellBackground(row[col.key], maxima[col.key]),
                  }}
                >
                  {row[col.key]}
                </TableCell>
              ))}
              <TableCell>
                {row.missing_owner ? (
                  <Badge variant="destructive">Missing owner</Badge>
                ) : (
                  <Badge variant="muted">Owned</Badge>
                )}
              </TableCell>
              <TableCell className="text-right">
                <DebtScoreBadge score={row.debt_score} />
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

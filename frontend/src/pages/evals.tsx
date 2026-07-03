import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, FlaskConical } from "lucide-react";
import { useNavigate, useSearchParams } from "react-router-dom";

import {
  EvalModeBadge,
  EvalStatusBadge,
  formatPercent,
} from "@/components/evals/eval-badges";
import { ComparisonBarChart, ScoreTrendChart } from "@/components/evals/eval-charts";
import { GoldenTasksTable } from "@/components/evals/golden-tasks-table";
import { RunEvalButton } from "@/components/evals/run-eval-button";
import { PaginationControls } from "@/components/runs/pagination-controls";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { PageHeader } from "@/components/ui/page-header";
import { PermissionDenied } from "@/components/ui/permission-denied";
import { ScoreBadge } from "@/components/ui/score-badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tooltip } from "@/components/ui/tooltip";
import { useMe } from "@/hooks/use-me";
import { usePageTitle } from "@/hooks/use-page-title";
import { api, isApiError } from "@/lib/api";
import { queryKeys } from "@/lib/queryKeys";
import type { EvalRun, GoldenTasksResponse, Paginated } from "@/lib/types";
import { formatDateTime, formatNumber } from "@/lib/utils";

function EvalsSkeleton() {
  return (
    <div data-testid="evals-loading" className="flex flex-col gap-3">
      <div className="grid gap-3 md:grid-cols-3">
        <Skeleton className="h-40 w-full" />
        <Skeleton className="h-40 w-full" />
        <Skeleton className="h-40 w-full" />
      </div>
      <Skeleton className="h-64 w-full" />
    </div>
  );
}

function LatestRunCards({ latest }: { latest: EvalRun }) {
  const summary = latest.summary;
  if (!summary) return null;
  const hasBaseline = summary.baseline_avg_score !== null;

  return (
    <div className="grid gap-3 md:grid-cols-3" data-testid="latest-run-summary">
      <Card>
        <CardHeader>
          <CardTitle>Latest run</CardTitle>
          <CardDescription>
            {formatDateTime(latest.started_at)} · <EvalModeBadge mode={latest.mode} />
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-2">
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground">Avg score</span>
            <ScoreBadge score={summary.avg_score} />
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground">Pass rate</span>
            <span className="text-sm font-semibold tabular-nums">
              {formatPercent(summary.pass_rate)}
            </span>
          </div>
          {summary.regression ? (
            <Tooltip
              content={
                summary.regressed_task_names.length > 0
                  ? summary.regressed_task_names.join(", ")
                  : "Score dropped below baseline"
              }
            >
              <Badge variant="destructive" data-testid="regression-badge">
                <AlertTriangle className="size-3" aria-hidden="true" />
                regression
              </Badge>
            </Tooltip>
          ) : (
            <Badge variant="success">no regression</Badge>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Baseline vs context engine</CardTitle>
          <CardDescription>Average eval score</CardDescription>
        </CardHeader>
        <CardContent>
          {hasBaseline ? (
            <ComparisonBarChart
              domainMax={1}
              data={[
                { name: "baseline", value: summary.baseline_avg_score ?? 0 },
                { name: "context engine", value: summary.avg_score },
              ]}
            />
          ) : (
            <p className="text-xs text-muted-foreground">
              No baseline in the latest run — run a comparison eval to see this.
            </p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Token usage</CardTitle>
          <CardDescription>
            {summary.baseline_total_tokens !== null
              ? `baseline ${formatNumber(summary.baseline_total_tokens)} vs context engine ${formatNumber(summary.total_tokens)}`
              : `total ${formatNumber(summary.total_tokens)}`}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {summary.baseline_total_tokens !== null ? (
            <ComparisonBarChart
              data={[
                { name: "baseline", value: summary.baseline_total_tokens },
                { name: "context engine", value: summary.total_tokens },
              ]}
            />
          ) : (
            <p className="text-2xl font-semibold tabular-nums">
              {formatNumber(summary.total_tokens)}
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function EvalHistoryTable({ runs }: { runs: EvalRun[] }) {
  return (
    <Table data-testid="eval-history-table">
      <TableHeader>
        <TableRow>
          <TableHead>Started</TableHead>
          <TableHead>Mode</TableHead>
          <TableHead>Status</TableHead>
          <TableHead>Avg score</TableHead>
          <TableHead>Pass rate</TableHead>
          <TableHead className="text-right">Tokens</TableHead>
          <TableHead>Regression</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {runs.map((run) => (
          <EvalHistoryRow key={run.id} run={run} />
        ))}
      </TableBody>
    </Table>
  );
}

function EvalHistoryRow({ run }: { run: EvalRun }) {
  const navigate = useNavigate();
  return (
    <TableRow
      data-testid={`eval-row-${run.id}`}
      className="cursor-pointer"
      onClick={() => navigate(`/evals/${run.id}`)}
    >
      <TableCell className="whitespace-nowrap text-xs tabular-nums">
        {formatDateTime(run.started_at)}
      </TableCell>
      <TableCell>
        <EvalModeBadge mode={run.mode} />
      </TableCell>
      <TableCell>
        <EvalStatusBadge status={run.status} />
      </TableCell>
      <TableCell>
        <ScoreBadge score={run.summary?.avg_score ?? null} />
      </TableCell>
      <TableCell className="tabular-nums text-xs">
        {formatPercent(run.summary?.pass_rate)}
      </TableCell>
      <TableCell className="text-right tabular-nums text-xs">
        {run.summary ? formatNumber(run.summary.total_tokens) : "—"}
      </TableCell>
      <TableCell>
        {run.summary?.regression ? (
          <AlertTriangle
            role="img"
            aria-label="regression"
            className="size-4 text-destructive"
          />
        ) : (
          <span className="text-xs text-muted-foreground">—</span>
        )}
      </TableCell>
    </TableRow>
  );
}

export default function EvalsPage() {
  usePageTitle("Evals");
  const { data: me } = useMe();
  const [searchParams, setSearchParams] = useSearchParams();
  const page = Math.max(1, Number(searchParams.get("page") ?? "1") || 1);

  const runsQuery = useQuery({
    queryKey: queryKeys.evals(page),
    queryFn: () => api.get<Paginated<EvalRun>>("/v1/evals", { page }),
    placeholderData: (previous) => previous,
  });

  const goldenQuery = useQuery({
    queryKey: queryKeys.goldenTasks(),
    queryFn: () => api.get<GoldenTasksResponse>("/v1/evals/golden-tasks"),
  });

  const setPage = (next: number) => {
    setSearchParams((params) => {
      if (next <= 1) params.delete("page");
      else params.set("page", String(next));
      return params;
    });
  };

  const { data, error, isPending, refetch } = runsQuery;

  let content;
  if (isPending) {
    content = <EvalsSkeleton />;
  } else if (error) {
    content =
      isApiError(error) && error.status === 403 ? (
        <PermissionDenied role={me?.role} />
      ) : (
        <ErrorState
          message={isApiError(error) ? error.detail : "Failed to load eval runs."}
          onRetry={() => void refetch()}
        />
      );
  } else if (data.items.length === 0) {
    content = (
      <EmptyState
        icon={FlaskConical}
        title="No eval runs yet"
        description='Queue your first run with the "Run eval" button to grade the context engine against the golden tasks.'
      />
    );
  } else {
    const latest = data.items.find((run) => run.summary !== null);
    content = (
      <div className="flex flex-col gap-3">
        {latest ? <LatestRunCards latest={latest} /> : null}

        <Card>
          <CardHeader>
            <CardTitle>Score trend</CardTitle>
            <CardDescription>Average score per eval run</CardDescription>
          </CardHeader>
          <CardContent>
            <ScoreTrendChart runs={data.items} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Run history</CardTitle>
          </CardHeader>
          <CardContent>
            <EvalHistoryTable runs={data.items} />
            <PaginationControls
              page={data.page}
              pageSize={data.page_size}
              total={data.total}
              onPageChange={setPage}
            />
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <>
      <PageHeader
        title="Evals"
        description="Grade the context engine against golden tasks and watch for regressions."
        actions={<RunEvalButton />}
      />
      <div data-testid="page-evals" className="flex flex-col gap-3">
        {content}

        <Card>
          <CardHeader>
            <CardTitle>Golden tasks</CardTitle>
            <CardDescription>
              The reference tasks every eval run is graded against.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {goldenQuery.isPending ? (
              <Skeleton data-testid="golden-tasks-loading" className="h-32 w-full" />
            ) : goldenQuery.error ? (
              <ErrorState
                message="Failed to load golden tasks."
                onRetry={() => void goldenQuery.refetch()}
              />
            ) : goldenQuery.data.items.length === 0 ? (
              <EmptyState
                title="No golden tasks"
                description="Seed golden tasks to enable evals."
              />
            ) : (
              <GoldenTasksTable tasks={goldenQuery.data.items} />
            )}
          </CardContent>
        </Card>
      </div>
    </>
  );
}

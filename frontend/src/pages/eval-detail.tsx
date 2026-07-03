import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";

import {
  EvalModeBadge,
  EvalStatusBadge,
  formatPercent,
} from "@/components/evals/eval-badges";
import { EvalResultsTable } from "@/components/evals/eval-results-table";
import { RegressionBanner } from "@/components/evals/regression-banner";
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
import { Skeleton } from "@/components/ui/skeleton";
import { StatCard } from "@/components/ui/stat-card";
import { useMe } from "@/hooks/use-me";
import { usePageTitle } from "@/hooks/use-page-title";
import { api, isApiError } from "@/lib/api";
import { queryKeys } from "@/lib/queryKeys";
import type { EvalRunDetail } from "@/lib/types";
import { formatDateTime, formatNumber } from "@/lib/utils";

function DetailSkeleton() {
  return (
    <div data-testid="eval-detail-loading" className="flex flex-col gap-3">
      <div className="grid gap-3 md:grid-cols-3">
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-24 w-full" />
      </div>
      <Skeleton className="h-64 w-full" />
    </div>
  );
}

function roundDelta(value: number): number {
  return Number(value.toFixed(2));
}

function RunBody({ run }: { run: EvalRunDetail }) {
  const summary = run.summary;
  const isComparison = summary?.baseline_avg_score !== null && summary !== null;

  return (
    <div className="flex flex-col gap-3">
      {summary?.regression ? (
        <RegressionBanner taskNames={summary.regressed_task_names} />
      ) : null}

      {summary ? (
        <div className="grid gap-3 sm:grid-cols-3" data-testid="eval-summary-cards">
          <StatCard
            label="Avg score"
            value={summary.avg_score.toFixed(2)}
            delta={
              isComparison
                ? roundDelta(summary.avg_score - (summary.baseline_avg_score ?? 0))
                : undefined
            }
            hint={
              isComparison
                ? `baseline ${summary.baseline_avg_score?.toFixed(2)}`
                : undefined
            }
          />
          <StatCard label="Pass rate" value={formatPercent(summary.pass_rate)} />
          <StatCard
            label="Total tokens"
            value={formatNumber(summary.total_tokens)}
            delta={
              summary.baseline_total_tokens !== null
                ? summary.total_tokens - summary.baseline_total_tokens
                : undefined
            }
            hint={
              summary.baseline_total_tokens !== null
                ? `baseline ${formatNumber(summary.baseline_total_tokens)}`
                : undefined
            }
          />
        </div>
      ) : (
        <p className="text-xs text-muted-foreground">
          No summary yet — the run may still be in progress.
        </p>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Score breakdown</CardTitle>
          <CardDescription>
            {run.results.length} results across {run.golden_tasks_total} golden
            tasks. Expand a failed row to read the grader&apos;s explanation.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {run.results.length > 0 ? (
            <EvalResultsTable results={run.results} />
          ) : (
            <EmptyState
              title="No results"
              description="This run has not produced any per-task results yet."
            />
          )}
        </CardContent>
      </Card>
    </div>
  );
}

export default function EvalDetailPage() {
  usePageTitle("Eval Run");
  const { id = "" } = useParams();
  const { data: me } = useMe();

  const { data, error, isPending, refetch } = useQuery({
    queryKey: queryKeys.evalRun(id),
    queryFn: () => api.get<EvalRunDetail>(`/v1/evals/${id}`),
    enabled: id !== "",
  });

  let content;
  if (isPending) {
    content = <DetailSkeleton />;
  } else if (error) {
    if (isApiError(error) && error.status === 403) {
      content = <PermissionDenied role={me?.role} />;
    } else if (isApiError(error) && error.status === 404) {
      content = (
        <ErrorState
          title="Eval run not found"
          message={`No eval run exists with id ${id}.`}
        />
      );
    } else {
      content = (
        <ErrorState
          message={isApiError(error) ? error.detail : "Failed to load the eval run."}
          onRetry={() => void refetch()}
        />
      );
    }
  } else {
    content = <RunBody run={data} />;
  }

  return (
    <>
      <PageHeader
        title="Eval Run"
        description={
          data
            ? `Started ${formatDateTime(data.started_at)} · finished ${formatDateTime(data.finished_at)}`
            : undefined
        }
        actions={
          data ? (
            <div className="flex items-center gap-2">
              <EvalModeBadge mode={data.mode} />
              <EvalStatusBadge status={data.status} />
            </div>
          ) : undefined
        }
      />
      <div data-testid="page-eval-detail">{content}</div>
    </>
  );
}

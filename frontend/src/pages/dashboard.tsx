import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  AlertTriangle,
  Bot,
  Boxes,
  Database,
  FileText,
  GitBranch,
  Package,
  ShieldAlert,
  Users,
  XCircle,
} from "lucide-react";
import { useState, type ReactNode } from "react";
import { Link } from "react-router-dom";

import { TrendChartCard } from "@/components/dashboard/trend-chart-card";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { PageHeader } from "@/components/ui/page-header";
import { PermissionDenied } from "@/components/ui/permission-denied";
import { ScoreBadge } from "@/components/ui/score-badge";
import { StatCard } from "@/components/ui/stat-card";
import { useMe } from "@/hooks/use-me";
import { usePageTitle } from "@/hooks/use-page-title";
import { api, isApiError } from "@/lib/api";
import { queryKeys } from "@/lib/queryKeys";
import type { DashboardSummary, Trends } from "@/lib/types";
import { formatNumber } from "@/lib/utils";

const DAY_OPTIONS = [7, 30, 90] as const;

const scoreFormatter = (v: number) => v.toFixed(2);
const countFormatter = (v: number) => formatNumber(v);

/** Wraps a StatCard in a link (stale docs / conflicts / failed runs). */
function LinkedStat({
  to,
  label,
  children,
}: {
  to: string;
  label: string;
  children: ReactNode;
}) {
  return (
    <Link
      to={to}
      aria-label={label}
      className="block rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring [&>div]:transition-colors [&>div]:hover:border-ring/60"
    >
      {children}
    </Link>
  );
}

export default function DashboardPage() {
  usePageTitle("Dashboard");
  const { data: me } = useMe();
  const [days, setDays] = useState<number>(30);

  const summaryQuery = useQuery({
    queryKey: queryKeys.dashboardSummary(),
    queryFn: () => api.get<DashboardSummary>("/v1/dashboard/summary"),
  });

  const trendsQuery = useQuery({
    queryKey: queryKeys.dashboardTrends(days),
    queryFn: () => api.get<Trends>("/v1/dashboard/trends", { days }),
  });

  const daysSelector = (
    <div role="group" aria-label="Trend window" className="flex items-center gap-1">
      {DAY_OPTIONS.map((option) => (
        <Button
          key={option}
          size="sm"
          variant={days === option ? "secondary" : "ghost"}
          aria-pressed={days === option}
          onClick={() => setDays(option)}
        >
          {option}d
        </Button>
      ))}
    </div>
  );

  const error = summaryQuery.error ?? trendsQuery.error;
  if (error) {
    const denied = isApiError(error) && error.status === 403;
    return (
      <>
        <PageHeader title="Dashboard" description="Org-wide context health at a glance" />
        <div data-testid="page-dashboard">
          {denied ? (
            <PermissionDenied role={me?.role} />
          ) : (
            <ErrorState
              message={isApiError(error) ? error.detail : "Failed to load the dashboard."}
              onRetry={() => {
                if (summaryQuery.isError) void summaryQuery.refetch();
                if (trendsQuery.isError) void trendsQuery.refetch();
              }}
            />
          )}
        </div>
      </>
    );
  }

  const summary = summaryQuery.data;
  const loading = summaryQuery.isPending;
  const trends = trendsQuery.data;

  const trendsEmpty =
    trends !== undefined &&
    trends.eval_scores.length === 0 &&
    trends.source_freshness.length === 0 &&
    trends.review_rework.length === 0 &&
    trends.packets_per_day.length === 0;

  return (
    <>
      <PageHeader
        title="Dashboard"
        description="Org-wide context health at a glance"
        actions={daysSelector}
      />
      <div data-testid="page-dashboard" className="flex flex-col gap-4">
        <section
          aria-label="Key metrics"
          className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-6"
        >
          <StatCard
            label="Indexed documents"
            value={formatNumber(summary?.total_documents)}
            icon={FileText}
            loading={loading}
          />
          <StatCard
            label="Connected sources"
            value={formatNumber(summary?.connected_sources)}
            icon={Database}
            loading={loading}
          />
          <StatCard
            label="Active repos"
            value={formatNumber(summary?.active_repos)}
            icon={GitBranch}
            loading={loading}
          />
          <StatCard
            label="Active services"
            value={formatNumber(summary?.active_services)}
            icon={Boxes}
            loading={loading}
          />
          <StatCard
            label="Active users"
            value={formatNumber(summary?.active_users)}
            icon={Users}
            loading={loading}
          />
          <StatCard
            label="Context packets"
            value={formatNumber(summary?.context_packets)}
            icon={Package}
            loading={loading}
          />
          <StatCard
            label="Agent runs"
            value={formatNumber(summary?.agent_runs)}
            icon={Bot}
            loading={loading}
          />
          {loading ? (
            <StatCard label="Failed agent runs" value="" loading />
          ) : (
            <LinkedStat to="/agent-runs?status=failed" label="Failed agent runs — view failed runs">
              <StatCard
                label="Failed agent runs"
                value={formatNumber(summary?.failed_agent_runs)}
                hint="view runs"
                icon={XCircle}
              />
            </LinkedStat>
          )}
          {loading ? (
            <StatCard label="Stale documents" value="" loading />
          ) : (
            <LinkedStat to="/context-debt" label="Stale documents — view context debt">
              <StatCard
                label="Stale documents"
                value={formatNumber(summary?.stale_documents)}
                hint="view debt"
                icon={AlertTriangle}
              />
            </LinkedStat>
          )}
          {loading ? (
            <StatCard label="Conflicting documents" value="" loading />
          ) : (
            <LinkedStat to="/conflicts" label="Conflicting documents — view conflicts">
              <StatCard
                label="Conflicting documents"
                value={formatNumber(summary?.conflicting_documents)}
                hint="view conflicts"
                icon={Activity}
              />
            </LinkedStat>
          )}
          <StatCard
            label="ACL violations blocked"
            value={formatNumber(summary?.acl_violations_blocked)}
            icon={ShieldAlert}
            loading={loading}
          />
          <StatCard
            label="Latest eval score"
            value={<ScoreBadge score={summary?.latest_eval_score} className="text-sm" />}
            loading={loading}
          />
        </section>

        <section aria-label="Trends" className="flex flex-col gap-3">
          {trendsEmpty ? (
            <EmptyState
              title="No trend data yet"
              description="Trends appear once documents are indexed and context packets are compiled."
            />
          ) : (
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2 2xl:grid-cols-4">
              <TrendChartCard
                title="Eval score trend"
                kind="line"
                color="var(--chart-1)"
                data={trends?.eval_scores ?? []}
                valueFormatter={scoreFormatter}
                loading={trendsQuery.isPending}
              />
              <TrendChartCard
                title="Source freshness"
                kind="area"
                color="var(--chart-2)"
                data={trends?.source_freshness ?? []}
                valueFormatter={scoreFormatter}
                loading={trendsQuery.isPending}
              />
              <TrendChartCard
                title="Review rework"
                kind="line"
                color="var(--chart-4)"
                data={trends?.review_rework ?? []}
                valueFormatter={countFormatter}
                loading={trendsQuery.isPending}
              />
              <TrendChartCard
                title="Packets per day"
                kind="bar"
                color="var(--chart-3)"
                data={trends?.packets_per_day ?? []}
                valueFormatter={countFormatter}
                loading={trendsQuery.isPending}
              />
            </div>
          )}
        </section>
      </div>
    </>
  );
}

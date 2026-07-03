import { useQuery } from "@tanstack/react-query";
import { Bot } from "lucide-react";
import { useSearchParams } from "react-router-dom";

import { PaginationControls } from "@/components/runs/pagination-controls";
import { RunsFilterBar, type RunFilters } from "@/components/runs/runs-filter-bar";
import { RunsTable } from "@/components/runs/runs-table";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { PageHeader } from "@/components/ui/page-header";
import { PermissionDenied } from "@/components/ui/permission-denied";
import { Skeleton } from "@/components/ui/skeleton";
import { useMe } from "@/hooks/use-me";
import { usePageTitle } from "@/hooks/use-page-title";
import { api, isApiError } from "@/lib/api";
import { queryKeys } from "@/lib/queryKeys";
import type { AgentRunSummary, Paginated } from "@/lib/types";

const PAGE_SIZE = 20;
const FILTER_KEYS: (keyof RunFilters)[] = [
  "agent",
  "repo",
  "service",
  "user_id",
  "status",
  "from",
  "to",
];

function RunsTableSkeleton() {
  return (
    <div data-testid="runs-loading" className="flex flex-col gap-2">
      {Array.from({ length: 8 }, (_, i) => (
        <Skeleton key={i} className="h-9 w-full" />
      ))}
    </div>
  );
}

export default function AgentRunsPage() {
  usePageTitle("Agent Runs");
  const { data: me } = useMe();
  const [searchParams, setSearchParams] = useSearchParams();

  const filters: RunFilters = {
    agent: searchParams.get("agent") ?? "",
    repo: searchParams.get("repo") ?? "",
    service: searchParams.get("service") ?? "",
    user_id: searchParams.get("user_id") ?? "",
    status: searchParams.get("status") ?? "",
    from: searchParams.get("from") ?? "",
    to: searchParams.get("to") ?? "",
  };
  const page = Math.max(1, Number(searchParams.get("page") ?? "1") || 1);

  const { data, error, isPending, refetch } = useQuery({
    queryKey: queryKeys.agentRuns({ ...filters, page }),
    queryFn: () =>
      api.get<Paginated<AgentRunSummary>>("/v1/agent-runs", {
        ...filters,
        page,
        page_size: PAGE_SIZE,
      }),
    placeholderData: (previous) => previous,
  });

  const setFilter = (key: keyof RunFilters, value: string) => {
    setSearchParams((params) => {
      if (value === "") params.delete(key);
      else params.set(key, value);
      params.delete("page"); // filters changed — restart at page 1
      return params;
    });
  };

  const clearFilters = () => {
    setSearchParams((params) => {
      for (const key of FILTER_KEYS) params.delete(key);
      params.delete("page");
      return params;
    });
  };

  const setPage = (next: number) => {
    setSearchParams((params) => {
      if (next <= 1) params.delete("page");
      else params.set("page", String(next));
      return params;
    });
  };

  let content;
  if (isPending) {
    content = <RunsTableSkeleton />;
  } else if (error) {
    content =
      isApiError(error) && error.status === 403 ? (
        <PermissionDenied role={me?.role} />
      ) : (
        <ErrorState
          message={isApiError(error) ? error.detail : "Failed to load agent runs."}
          onRetry={() => void refetch()}
        />
      );
  } else if (data.items.length === 0) {
    content = (
      <EmptyState
        icon={Bot}
        title="No agent runs found"
        description="No runs match the current filters. Adjust or clear the filters, or kick off an agent to see runs here."
      />
    );
  } else {
    content = (
      <>
        <RunsTable runs={data.items} />
        <PaginationControls
          page={data.page}
          pageSize={data.page_size}
          total={data.total}
          onPageChange={setPage}
        />
      </>
    );
  }

  return (
    <>
      <PageHeader
        title="Agent Runs"
        description="Every coding-agent execution, its context packet and its outcome."
      />
      <div data-testid="page-agent-runs">
        <RunsFilterBar filters={filters} onChange={setFilter} onClear={clearFilters} />
        {content}
      </div>
    </>
  );
}

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useNavigate, useSearchParams } from "react-router-dom";

import { AffectedChips } from "@/components/conflicts/affected-chips";
import { ConflictStatusBadge } from "@/components/conflicts/conflict-status-badge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
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
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { usePageTitle } from "@/hooks/use-page-title";
import { api, isApiError } from "@/lib/api";
import { queryKeys } from "@/lib/queryKeys";
import type { Conflict, Paginated } from "@/lib/types";
import { timeAgo } from "@/lib/utils";

type StatusTab = "open" | "resolved" | "all";

const STATUS_TABS: Array<{ value: StatusTab; label: string }> = [
  { value: "open", label: "Open" },
  { value: "resolved", label: "Resolved" },
  { value: "all", label: "All" },
];

const EMPTY_COPY: Record<StatusTab, { title: string; description: string }> = {
  open: {
    title: "No open conflicts",
    description: "Every detected disagreement between sources has been resolved.",
  },
  resolved: {
    title: "No resolved conflicts yet",
    description: "Conflicts you resolve will show up here with their resolution notes.",
  },
  all: {
    title: "No conflicts detected",
    description: "The ingestion pipeline has not flagged any contradicting documents.",
  },
};

function parseTab(raw: string | null): StatusTab {
  return raw === "resolved" || raw === "all" ? raw : "open";
}

export default function ConflictsPage() {
  usePageTitle("Conflicts");
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const tab = parseTab(searchParams.get("status"));
  const page = Math.max(1, Number(searchParams.get("page")) || 1);

  const query = useQuery({
    queryKey: queryKeys.conflicts({ status: tab, page }),
    queryFn: () =>
      api.get<Paginated<Conflict>>("/v1/conflicts", {
        status: tab === "all" ? undefined : tab,
        page,
      }),
    placeholderData: keepPreviousData,
  });

  const setTab = (value: string) => {
    setSearchParams({ status: value });
  };
  const setPage = (next: number) => {
    setSearchParams({ status: tab, page: String(next) });
  };

  const renderBody = () => {
    if (query.isPending) {
      return (
        <div className="space-y-2" data-testid="conflicts-loading">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-9 w-full" />
          ))}
        </div>
      );
    }
    if (query.isError) {
      if (isApiError(query.error) && query.error.status === 403) {
        return <PermissionDenied />;
      }
      return (
        <ErrorState
          message={
            isApiError(query.error) ? query.error.detail : "Failed to load conflicts"
          }
          onRetry={() => void query.refetch()}
        />
      );
    }

    const data = query.data;
    if (data.items.length === 0) {
      return (
        <EmptyState
          title={EMPTY_COPY[tab].title}
          description={EMPTY_COPY[tab].description}
        />
      );
    }

    const pageCount = Math.max(1, Math.ceil(data.total / data.page_size));
    return (
      <>
        <Table data-testid="conflicts-table">
          <TableHeader>
            <TableRow>
              <TableHead>Conflict</TableHead>
              <TableHead>Topic</TableHead>
              <TableHead className="text-right">Docs</TableHead>
              <TableHead>Affected</TableHead>
              <TableHead>Detected</TableHead>
              <TableHead>Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.items.map((conflict) => (
              <TableRow
                key={conflict.id}
                className="cursor-pointer"
                onClick={() => navigate(`/conflicts/${conflict.id}`)}
              >
                <TableCell className="max-w-72">
                  <span className="line-clamp-1 font-medium text-primary hover:underline">
                    {conflict.title}
                  </span>
                </TableCell>
                <TableCell>
                  <Badge variant="outline" className="font-mono text-[10px]">
                    {conflict.topic_key}
                  </Badge>
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {conflict.document_count}
                </TableCell>
                <TableCell>
                  <AffectedChips affected={conflict.affected} />
                </TableCell>
                <TableCell className="whitespace-nowrap text-xs text-muted-foreground">
                  {timeAgo(conflict.created_at)}
                </TableCell>
                <TableCell>
                  <ConflictStatusBadge status={conflict.status} />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        {pageCount > 1 ? (
          <div className="mt-3 flex items-center justify-between text-xs text-muted-foreground">
            <span>
              Page {data.page} of {pageCount} · {data.total} conflicts
            </span>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                disabled={data.page <= 1}
                onClick={() => setPage(data.page - 1)}
              >
                Previous
              </Button>
              <Button
                variant="outline"
                size="sm"
                disabled={data.page >= pageCount}
                onClick={() => setPage(data.page + 1)}
              >
                Next
              </Button>
            </div>
          </div>
        ) : null}
      </>
    );
  };

  return (
    <>
      <PageHeader
        title="Conflict Center"
        description="Contradicting documents detected across sources — compare and pick a source of truth."
      />
      <div data-testid="page-conflicts" className="space-y-3">
        <Tabs value={tab} onValueChange={setTab}>
          <TabsList>
            {STATUS_TABS.map((t) => (
              <TabsTrigger key={t.value} value={t.value}>
                {t.label}
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>
        {renderBody()}
      </div>
    </>
  );
}

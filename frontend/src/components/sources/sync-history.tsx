import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, ChevronDown, ChevronRight, History } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { api, isApiError } from "@/lib/api";
import { queryKeys } from "@/lib/queryKeys";
import type { ItemsResponse, SyncRun, SyncRunStatus, SyncRunTrigger } from "@/lib/types";
import { formatNumber, timeAgo } from "@/lib/utils";

/** Compact status dot for a sync run: running=info pulse, ok=success, error=destructive. */
function SyncRunStatusDot({ status }: { status: SyncRunStatus }) {
  if (status === "running") {
    return (
      <span
        data-testid="sync-run-dot-running"
        className="inline-block size-2 animate-pulse rounded-full bg-primary"
        aria-hidden="true"
      />
    );
  }
  if (status === "ok") {
    return (
      <span
        data-testid="sync-run-dot-ok"
        className="inline-block size-2 rounded-full bg-emerald-500"
        aria-hidden="true"
      />
    );
  }
  return (
    <span
      data-testid="sync-run-dot-error"
      className="inline-block size-2 rounded-full bg-destructive"
      aria-hidden="true"
    />
  );
}

function SyncRunStatusBadge({ status }: { status: SyncRunStatus }) {
  if (status === "running") {
    return (
      <Badge variant="default">
        <Spinner className="size-3 text-primary" label="Running" />
        running
      </Badge>
    );
  }
  if (status === "ok") return <Badge variant="success">ok</Badge>;
  return <Badge variant="destructive">error</Badge>;
}

function SyncRunTriggerBadge({ trigger }: { trigger: SyncRunTrigger }) {
  return (
    <Badge variant={trigger === "scheduled" ? "muted" : "outline"}>{trigger}</Badge>
  );
}

/** "3m 12s" between two ISO timestamps; "—" while running (no finished_at). */
function formatDuration(startedAt: string, finishedAt: string | null): string {
  if (!finishedAt) return "—";
  const start = new Date(startedAt).getTime();
  const end = new Date(finishedAt).getTime();
  if (Number.isNaN(start) || Number.isNaN(end) || end < start) return "—";
  const totalSeconds = Math.floor((end - start) / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  if (minutes === 0) return `${seconds}s`;
  return `${minutes}m ${seconds}s`;
}

/** Inline summary of a source's last sync run — used in the sources table row. */
function LastSyncRunSummary({ run }: { run: SyncRun | null | undefined }) {
  if (!run) {
    return <span className="text-xs text-muted-foreground">no runs yet</span>;
  }
  return (
    <span
      data-testid="last-sync-run-summary"
      className="flex items-center gap-1.5 whitespace-nowrap text-xs"
    >
      <SyncRunStatusDot status={run.status} />
      <span className="text-muted-foreground">{timeAgo(run.started_at)}</span>
      {run.status === "error" ? (
        <AlertTriangle
          className="size-3 text-destructive"
          aria-label="Last run had errors"
        />
      ) : (
        <span className="tabular-nums text-muted-foreground">
          +{formatNumber(run.docs_upserted)} docs
        </span>
      )}
    </span>
  );
}

function ErrorsCell({ errors }: { errors: SyncRun["errors"] }) {
  const [open, setOpen] = useState(false);
  if (errors.length === 0) {
    return <span className="text-xs text-muted-foreground">—</span>;
  }
  return (
    <div>
      <button
        type="button"
        aria-expanded={open}
        aria-label={`Toggle ${errors.length} error${errors.length === 1 ? "" : "s"}`}
        className="inline-flex items-center gap-0.5 rounded-sm text-xs text-destructive transition-colors hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        onClick={() => setOpen((o) => !o)}
      >
        {open ? (
          <ChevronDown className="size-3" aria-hidden="true" />
        ) : (
          <ChevronRight className="size-3" aria-hidden="true" />
        )}
        {errors.length} error{errors.length === 1 ? "" : "s"}
      </button>
      {open ? (
        <ul className="mt-1 space-y-0.5 rounded-md border border-destructive/30 bg-destructive/8 p-2 font-mono text-[11px] text-destructive">
          {errors.map((e, i) => (
            <li key={i} className="truncate">
              {(e.external_id ?? "(unknown)") + ": " + e.error}
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

function SyncHistorySkeleton() {
  return (
    <div data-testid="sync-history-loading" className="flex flex-col gap-2 p-2">
      {Array.from({ length: 3 }, (_, i) => (
        <Skeleton key={i} className="h-8 w-full" />
      ))}
    </div>
  );
}

/** Expandable inline panel of a source's sync run history. */
function SyncHistoryPanel({ sourceId }: { sourceId: string }) {
  const { data, error, isPending, refetch } = useQuery({
    queryKey: queryKeys.sourceSyncRuns(sourceId),
    queryFn: () => api.get<ItemsResponse<SyncRun>>(`/v1/sources/${sourceId}/sync-runs`),
  });

  if (isPending) return <SyncHistorySkeleton />;
  if (error) {
    return (
      <ErrorState
        message={isApiError(error) ? error.detail : "Failed to load sync history."}
        onRetry={() => void refetch()}
      />
    );
  }
  if (data.items.length === 0) {
    return (
      <EmptyState
        icon={History}
        title="No sync runs yet"
        description="This source hasn't been synced yet — trigger a sync to see history here."
      />
    );
  }

  return (
    <Table data-testid={`sync-history-table-${sourceId}`}>
      <TableHeader>
        <TableRow>
          <TableHead>Status</TableHead>
          <TableHead>Trigger</TableHead>
          <TableHead>Started</TableHead>
          <TableHead>Duration</TableHead>
          <TableHead className="text-right">Upserted</TableHead>
          <TableHead className="text-right">Skipped</TableHead>
          <TableHead className="text-right">Pruned</TableHead>
          <TableHead className="text-right">Chunks</TableHead>
          <TableHead>Errors</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {data.items.map((run) => (
          <TableRow key={run.id} data-testid={`sync-run-row-${run.id}`}>
            <TableCell>
              <SyncRunStatusBadge status={run.status} />
            </TableCell>
            <TableCell>
              <SyncRunTriggerBadge trigger={run.trigger} />
            </TableCell>
            <TableCell className="whitespace-nowrap text-xs text-muted-foreground">
              {timeAgo(run.started_at)}
            </TableCell>
            <TableCell className="whitespace-nowrap text-xs tabular-nums text-muted-foreground">
              {formatDuration(run.started_at, run.finished_at)}
            </TableCell>
            <TableCell className="text-right text-xs tabular-nums">
              {formatNumber(run.docs_upserted)}
            </TableCell>
            <TableCell className="text-right text-xs tabular-nums">
              {formatNumber(run.docs_skipped)}
            </TableCell>
            <TableCell className="text-right text-xs tabular-nums">
              {formatNumber(run.docs_pruned)}
            </TableCell>
            <TableCell className="text-right text-xs tabular-nums">
              {formatNumber(run.chunks_indexed)}
            </TableCell>
            <TableCell>
              <ErrorsCell errors={run.errors} />
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

interface SyncHistoryToggleProps {
  sourceId: string;
  sourceName: string;
  open: boolean;
  onToggle: () => void;
}

/** "History" action button that expands/collapses the inline sync history panel. */
function SyncHistoryToggle({ sourceId, sourceName, open, onToggle }: SyncHistoryToggleProps) {
  return (
    <Button
      variant="outline"
      size="sm"
      aria-expanded={open}
      aria-label={`Toggle sync history for ${sourceName}`}
      onClick={onToggle}
      data-testid={`sync-history-toggle-${sourceId}`}
    >
      <History aria-hidden="true" />
      History
    </Button>
  );
}

export {
  ErrorsCell,
  formatDuration,
  LastSyncRunSummary,
  SyncHistoryPanel,
  SyncHistoryToggle,
  SyncRunStatusBadge,
  SyncRunStatusDot,
  SyncRunTriggerBadge,
};

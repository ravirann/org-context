import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronDown, ChevronRight, Database, RefreshCw, Trash2 } from "lucide-react";
import { Fragment, useState } from "react";

import { AddSourceDialog } from "@/components/sources/add-source-dialog";
import { ConfigureSourceDialog } from "@/components/sources/configure-source-dialog";
import { EnabledSwitch } from "@/components/sources/enabled-switch";
import { InlineNumberInput } from "@/components/sources/inline-number-input";
import { SourceTypeBadge, SyncStatusBadge } from "@/components/sources/source-badges";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
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
import { useToast } from "@/components/ui/toast";
import { useMe } from "@/hooks/use-me";
import { usePageTitle } from "@/hooks/use-page-title";
import { api, isApiError } from "@/lib/api";
import { queryKeys } from "@/lib/queryKeys";
import type { ItemsResponse, Source, SourceUpdate, SyncEnqueued } from "@/lib/types";
import { formatNumber, timeAgo } from "@/lib/utils";

function SourcesSkeleton() {
  return (
    <div data-testid="sources-loading" className="flex flex-col gap-2">
      {Array.from({ length: 6 }, (_, i) => (
        <Skeleton key={i} className="h-10 w-full" />
      ))}
    </div>
  );
}

interface SourceRowProps {
  source: Source;
  canManage: boolean;
  canConfigure: boolean;
  onPatch: (id: string, body: SourceUpdate) => void;
  onSync: (id: string) => void;
  onDelete: (source: Source) => void;
}

function SourceRow({
  source,
  canManage,
  canConfigure,
  onPatch,
  onSync,
  onDelete,
}: SourceRowProps) {
  const [errorOpen, setErrorOpen] = useState(false);

  return (
    <Fragment>
      <TableRow data-testid={`source-row-${source.id}`}>
        <TableCell>
          <SourceTypeBadge type={source.type} />
        </TableCell>
        <TableCell className="max-w-[200px] truncate text-xs font-medium">
          {source.name}
        </TableCell>
        <TableCell>
          <EnabledSwitch
            checked={source.enabled}
            disabled={!canManage}
            aria-label={`Toggle ${source.name}`}
            onCheckedChange={(enabled) => onPatch(source.id, { enabled })}
          />
        </TableCell>
        <TableCell>
          <span className="flex items-center gap-1.5">
            <SyncStatusBadge status={source.sync_status} />
            {source.last_error ? (
              <button
                type="button"
                aria-expanded={errorOpen}
                aria-label={`Toggle last error for ${source.name}`}
                className="inline-flex items-center gap-0.5 rounded-sm text-[11px] text-destructive transition-colors hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                onClick={() => setErrorOpen((open) => !open)}
              >
                {errorOpen ? (
                  <ChevronDown className="size-3" aria-hidden="true" />
                ) : (
                  <ChevronRight className="size-3" aria-hidden="true" />
                )}
                error
              </button>
            ) : null}
          </span>
        </TableCell>
        <TableCell className="whitespace-nowrap text-xs tabular-nums text-muted-foreground">
          {timeAgo(source.last_synced_at)}
        </TableCell>
        <TableCell className="text-right text-xs tabular-nums">
          {formatNumber(source.document_count)}
        </TableCell>
        <TableCell>
          <Badge variant={source.acl_sync_status === "ok" ? "success" : "muted"}>
            {source.acl_sync_status}
          </Badge>
        </TableCell>
        <TableCell>
          <InlineNumberInput
            value={source.authority_rank}
            min={0}
            max={100}
            disabled={!canManage}
            aria-label={`Authority rank for ${source.name}`}
            onCommit={(authority_rank) => onPatch(source.id, { authority_rank })}
          />
        </TableCell>
        <TableCell>
          <InlineNumberInput
            value={source.freshness_window_days}
            min={1}
            max={365}
            disabled={!canManage}
            aria-label={`Freshness window days for ${source.name}`}
            onCommit={(freshness_window_days) =>
              onPatch(source.id, { freshness_window_days })
            }
          />
        </TableCell>
        <TableCell>
          <span className="flex items-center justify-end gap-1">
            <ConfigureSourceDialog source={source} readOnly={!canConfigure} />
            <Button
              variant="outline"
              size="sm"
              disabled={!canManage || source.sync_status === "syncing"}
              aria-label={`Sync ${source.name} now`}
              onClick={() => onSync(source.id)}
            >
              <RefreshCw aria-hidden="true" />
              Sync now
            </Button>
            <Button
              variant="ghost"
              size="icon"
              disabled={!canManage}
              aria-label={`Delete ${source.name}`}
              onClick={() => onDelete(source)}
            >
              <Trash2 className="text-destructive" aria-hidden="true" />
            </Button>
          </span>
        </TableCell>
      </TableRow>
      {errorOpen && source.last_error ? (
        <TableRow
          data-testid={`source-error-${source.id}`}
          className="hover:bg-transparent"
        >
          <TableCell colSpan={10} className="py-0 pb-2">
            <div className="rounded-md border border-destructive/30 bg-destructive/8 px-3 py-2 font-mono text-xs text-destructive">
              {source.last_error}
            </div>
          </TableCell>
        </TableRow>
      ) : null}
    </Fragment>
  );
}

export default function SourcesPage() {
  usePageTitle("Sources");
  const { data: me } = useMe();
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [deleteTarget, setDeleteTarget] = useState<Source | null>(null);

  const canManage = me?.role === "admin" || me?.role === "lead";
  const canConfigure = me?.role === "admin";

  const { data, error, isPending, refetch } = useQuery({
    queryKey: queryKeys.sources(),
    queryFn: () => api.get<ItemsResponse<Source>>("/v1/sources"),
  });

  const handleMutationError = (error: unknown, fallback: string) => {
    toast({
      title:
        isApiError(error) && error.status === 403 ? "Requires admin" : fallback,
      description: isApiError(error) ? error.detail : undefined,
      variant: "error",
    });
  };

  const patchMutation = useMutation({
    mutationFn: ({ id, body }: { id: string; body: SourceUpdate }) =>
      api.patch<Source>(`/v1/sources/${id}`, body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.sources() });
    },
    onError: (error) => handleMutationError(error, "Failed to update source"),
  });

  const syncMutation = useMutation({
    mutationFn: (id: string) =>
      api.post<SyncEnqueued>(`/v1/sources/${id}/sync`),
    onMutate: async (id) => {
      // Optimistically flip the source into "syncing".
      await queryClient.cancelQueries({ queryKey: queryKeys.sources() });
      const previous = queryClient.getQueryData<ItemsResponse<Source>>(
        queryKeys.sources(),
      );
      if (previous) {
        queryClient.setQueryData<ItemsResponse<Source>>(queryKeys.sources(), {
          items: previous.items.map((source) =>
            source.id === id ? { ...source, sync_status: "syncing" } : source,
          ),
        });
      }
      return { previous };
    },
    onSuccess: () => {
      toast({ title: "Sync queued", variant: "success" });
    },
    onError: (error, _id, context) => {
      if (context?.previous) {
        queryClient.setQueryData(queryKeys.sources(), context.previous);
      }
      handleMutationError(error, "Failed to queue sync");
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/v1/sources/${id}`),
    onSuccess: () => {
      toast({ title: "Source deleted", variant: "success" });
      setDeleteTarget(null);
      void queryClient.invalidateQueries({ queryKey: queryKeys.sources() });
    },
    onError: (error) => handleMutationError(error, "Failed to delete source"),
  });

  let content;
  if (isPending) {
    content = <SourcesSkeleton />;
  } else if (error) {
    content =
      isApiError(error) && error.status === 403 ? (
        <PermissionDenied role={me?.role} />
      ) : (
        <ErrorState
          message={isApiError(error) ? error.detail : "Failed to load sources."}
          onRetry={() => void refetch()}
        />
      );
  } else if (data.items.length === 0) {
    content = (
      <EmptyState
        icon={Database}
        title="No sources connected"
        description='Connect GitHub, Jira, Slack and more with the "Add source" button to start ingesting context.'
      />
    );
  } else {
    content = (
      <Table data-testid="sources-table">
        <TableHeader>
          <TableRow>
            <TableHead>Type</TableHead>
            <TableHead>Name</TableHead>
            <TableHead>Enabled</TableHead>
            <TableHead>Sync</TableHead>
            <TableHead>Last synced</TableHead>
            <TableHead className="text-right">Docs</TableHead>
            <TableHead>ACL sync</TableHead>
            <TableHead>Authority</TableHead>
            <TableHead>Freshness (d)</TableHead>
            <TableHead className="text-right">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {data.items.map((source) => (
            <SourceRow
              key={source.id}
              source={source}
              canManage={canManage}
              canConfigure={canConfigure}
              onPatch={(id, body) => patchMutation.mutate({ id, body })}
              onSync={(id) => syncMutation.mutate(id)}
              onDelete={setDeleteTarget}
            />
          ))}
        </TableBody>
      </Table>
    );
  }

  return (
    <>
      <PageHeader
        title="Sources"
        description="Connected knowledge sources, their sync health and retrieval weighting."
        actions={<AddSourceDialog disabled={!canManage} />}
      />
      <div data-testid="page-sources">{content}</div>

      <Dialog
        open={deleteTarget !== null}
        onOpenChange={(open) => {
          if (!open) setDeleteTarget(null);
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete source</DialogTitle>
            <DialogDescription>
              {deleteTarget
                ? `This permanently removes "${deleteTarget.name}" and stops future syncs. Ingested documents are detached.`
                : null}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteTarget(null)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              disabled={deleteMutation.isPending}
              onClick={() => {
                if (deleteTarget) deleteMutation.mutate(deleteTarget.id);
              }}
            >
              Delete source
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { ChevronDown, ChevronRight } from "lucide-react";
import { Fragment, useState } from "react";

import { QueryBoundary } from "@/components/admin/query-boundary";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useDebounce } from "@/hooks/use-debounce";
import { api } from "@/lib/api";
import { queryKeys } from "@/lib/queryKeys";
import type { AuditLog, Paginated } from "@/lib/types";
import { formatDateTime } from "@/lib/utils";

/** Admin → Audit log: filterable, paginated action trail with JSON detail. */
function AuditLogTab() {
  const [action, setAction] = useState("");
  const [page, setPage] = useState(1);
  const [expanded, setExpanded] = useState<string | null>(null);
  const debouncedAction = useDebounce(action);

  const filters = { action: debouncedAction || undefined, page };
  const query = useQuery({
    queryKey: queryKeys.auditLogs(filters),
    queryFn: () => api.get<Paginated<AuditLog>>("/v1/admin/audit-logs", filters),
    placeholderData: keepPreviousData,
  });

  return (
    <div className="space-y-3">
      <Input
        value={action}
        onChange={(e) => {
          setAction(e.target.value);
          setPage(1);
        }}
        placeholder="Filter by action, e.g. settings.update"
        aria-label="Filter by action"
        className="max-w-72 font-mono text-xs"
      />
      <QueryBoundary query={query}>
        {(data) =>
          data.items.length === 0 ? (
            <EmptyState
              title="No audit entries"
              description={
                debouncedAction
                  ? `No entries match action "${debouncedAction}".`
                  : "Nothing has been audited yet."
              }
            />
          ) : (
            <>
              <Table data-testid="admin-audit-table">
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-6">
                      <span className="sr-only">Detail</span>
                    </TableHead>
                    <TableHead>When</TableHead>
                    <TableHead>Actor</TableHead>
                    <TableHead>Action</TableHead>
                    <TableHead>Resource</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data.items.map((log) => {
                    const isOpen = expanded === log.id;
                    return (
                      <Fragment key={log.id}>
                        <TableRow>
                          <TableCell>
                            <button
                              type="button"
                              aria-expanded={isOpen}
                              aria-label={`Toggle detail for ${log.action}`}
                              className="rounded-sm text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                              onClick={() => setExpanded(isOpen ? null : log.id)}
                            >
                              {isOpen ? (
                                <ChevronDown className="size-3.5" aria-hidden="true" />
                              ) : (
                                <ChevronRight className="size-3.5" aria-hidden="true" />
                              )}
                            </button>
                          </TableCell>
                          <TableCell className="whitespace-nowrap text-xs text-muted-foreground">
                            {formatDateTime(log.created_at)}
                          </TableCell>
                          <TableCell>{log.actor_name ?? "system"}</TableCell>
                          <TableCell>
                            <Badge variant="outline" className="font-mono text-[10px]">
                              {log.action}
                            </Badge>
                          </TableCell>
                          <TableCell className="font-mono text-xs text-muted-foreground">
                            {log.resource_type}
                            {log.resource_id ? `:${log.resource_id.slice(0, 8)}` : ""}
                          </TableCell>
                        </TableRow>
                        {isOpen ? (
                          <TableRow className="hover:bg-transparent">
                            <TableCell colSpan={5} className="bg-muted/30">
                              <pre className="scroll-area max-h-56 overflow-auto whitespace-pre-wrap break-all rounded-md p-2 font-mono text-[11px]">
                                {JSON.stringify(log.detail, null, 2)}
                              </pre>
                            </TableCell>
                          </TableRow>
                        ) : null}
                      </Fragment>
                    );
                  })}
                </TableBody>
              </Table>
              <div className="flex items-center justify-between text-xs text-muted-foreground">
                <span>
                  Page {data.page} of {Math.max(1, Math.ceil(data.total / data.page_size))}
                  {" · "}
                  {data.total} entries
                </span>
                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={data.page <= 1}
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                  >
                    Previous
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={data.page * data.page_size >= data.total}
                    onClick={() => setPage((p) => p + 1)}
                  >
                    Next
                  </Button>
                </div>
              </div>
            </>
          )
        }
      </QueryBoundary>
    </div>
  );
}

export { AuditLogTab };

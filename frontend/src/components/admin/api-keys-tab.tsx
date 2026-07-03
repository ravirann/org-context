import { useQuery } from "@tanstack/react-query";
import { ShieldCheck } from "lucide-react";

import { ActiveDot } from "@/components/admin/badges";
import { QueryBoundary } from "@/components/admin/query-boundary";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { api } from "@/lib/api";
import { queryKeys } from "@/lib/queryKeys";
import type { ApiKeyOut, ItemsResponse } from "@/lib/types";
import { timeAgo } from "@/lib/utils";

/** Admin → API keys: metadata only — key material is never returned. */
function ApiKeysTab() {
  const query = useQuery({
    queryKey: queryKeys.adminApiKeys(),
    queryFn: () => api.get<ItemsResponse<ApiKeyOut>>("/v1/admin/api-keys"),
  });

  return (
    <div className="space-y-3">
      <p className="flex items-start gap-2 rounded-md border bg-muted/40 px-3 py-2 text-xs text-muted-foreground">
        <ShieldCheck className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
        Key material is never displayed or returned by the API — only metadata is listed
        here. Rotate keys from the backend CLI.
      </p>
      <QueryBoundary query={query}>
        {({ items }) =>
          items.length === 0 ? (
            <EmptyState title="No API keys" description="No API keys have been issued yet." />
          ) : (
            <Table data-testid="admin-api-keys-table">
              <TableHeader>
                <TableRow>
                  <TableHead>Label</TableHead>
                  <TableHead>Kind</TableHead>
                  <TableHead>User</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Last used</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((key) => (
                  <TableRow key={key.id}>
                    <TableCell className="font-mono text-xs">{key.label}</TableCell>
                    <TableCell>
                      <Badge variant={key.kind === "mcp" ? "secondary" : "outline"}>
                        {key.kind}
                      </Badge>
                    </TableCell>
                    <TableCell>{key.user_name}</TableCell>
                    <TableCell>
                      <ActiveDot active={key.is_active} />
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {key.last_used_at ? timeAgo(key.last_used_at) : "never"}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )
        }
      </QueryBoundary>
    </div>
  );
}

export { ApiKeysTab };

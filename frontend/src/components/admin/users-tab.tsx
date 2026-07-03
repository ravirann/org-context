import { useQuery } from "@tanstack/react-query";

import { ActiveDot, RoleBadge } from "@/components/admin/badges";
import { QueryBoundary } from "@/components/admin/query-boundary";
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
import type { AdminUser, ItemsResponse } from "@/lib/types";

/** Admin → Users: read-only roster with role + active status. */
function UsersTab() {
  const query = useQuery({
    queryKey: queryKeys.adminUsers(),
    queryFn: () => api.get<ItemsResponse<AdminUser>>("/v1/admin/users"),
  });

  return (
    <QueryBoundary query={query}>
      {({ items }) =>
        items.length === 0 ? (
          <EmptyState title="No users" description="No users exist in this workspace yet." />
        ) : (
          <Table data-testid="admin-users-table">
            <TableHeader>
              <TableRow>
                <TableHead>Email</TableHead>
                <TableHead>Name</TableHead>
                <TableHead>Role</TableHead>
                <TableHead>Team</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((user) => (
                <TableRow key={user.id}>
                  <TableCell className="font-mono text-xs">{user.email}</TableCell>
                  <TableCell>{user.name}</TableCell>
                  <TableCell>
                    <RoleBadge role={user.role} />
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {user.team_name ?? "—"}
                  </TableCell>
                  <TableCell>
                    <ActiveDot active={user.is_active} />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )
      }
    </QueryBoundary>
  );
}

export { UsersTab };

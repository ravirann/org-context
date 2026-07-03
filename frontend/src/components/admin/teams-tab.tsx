import { useQuery } from "@tanstack/react-query";

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
import type { AdminTeam, ItemsResponse } from "@/lib/types";

/** Admin → Teams: team list with member counts. */
function TeamsTab() {
  const query = useQuery({
    queryKey: queryKeys.adminTeams(),
    queryFn: () => api.get<ItemsResponse<AdminTeam>>("/v1/admin/teams"),
  });

  return (
    <QueryBoundary query={query}>
      {({ items }) =>
        items.length === 0 ? (
          <EmptyState title="No teams" description="No teams exist in this workspace yet." />
        ) : (
          <Table data-testid="admin-teams-table">
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead className="text-right">Members</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((team) => (
                <TableRow key={team.id}>
                  <TableCell className="font-medium">{team.name}</TableCell>
                  <TableCell className="text-right tabular-nums">
                    {team.member_count}
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

export { TeamsTab };

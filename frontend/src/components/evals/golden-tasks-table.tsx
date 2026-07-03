import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tooltip } from "@/components/ui/tooltip";
import type { GoldenTask } from "@/lib/types";

/** Golden-task catalogue: what each eval run is graded against. */
function GoldenTasksTable({ tasks }: { tasks: GoldenTask[] }) {
  return (
    <Table data-testid="golden-tasks-table">
      <TableHeader>
        <TableRow>
          <TableHead>Name</TableHead>
          <TableHead>Task</TableHead>
          <TableHead>Repo / Service</TableHead>
          <TableHead>Expected keywords</TableHead>
          <TableHead>Active</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {tasks.map((task) => {
          const truncated =
            task.task.length > 70 ? `${task.task.slice(0, 70)}…` : task.task;
          return (
            <TableRow key={task.id} data-testid={`golden-task-row-${task.id}`}>
              <TableCell className="text-xs font-medium">{task.name}</TableCell>
              <TableCell className="max-w-[300px]">
                <Tooltip
                  content={
                    task.task.length > 120
                      ? `${task.task.slice(0, 120)}…`
                      : task.task
                  }
                >
                  <span className="block truncate text-xs text-muted-foreground">
                    {truncated}
                  </span>
                </Tooltip>
              </TableCell>
              <TableCell>
                <span className="flex flex-wrap gap-1">
                  {task.repo ? <Badge variant="outline">{task.repo}</Badge> : null}
                  {task.service ? (
                    <Badge variant="secondary">{task.service}</Badge>
                  ) : null}
                  {!task.repo && !task.service ? (
                    <span className="text-xs text-muted-foreground">—</span>
                  ) : null}
                </span>
              </TableCell>
              <TableCell>
                <span className="flex max-w-[260px] flex-wrap gap-1">
                  {task.expected_keywords.map((keyword) => (
                    <Badge key={keyword} variant="muted">
                      {keyword}
                    </Badge>
                  ))}
                </span>
              </TableCell>
              <TableCell>
                {task.is_active ? (
                  <Badge variant="success">active</Badge>
                ) : (
                  <Badge variant="muted">inactive</Badge>
                )}
              </TableCell>
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
}

export { GoldenTasksTable };

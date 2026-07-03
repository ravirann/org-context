import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  useReactTable,
} from "@tanstack/react-table";
import { PackageSearch } from "lucide-react";
import { useMemo } from "react";
import { Link, useNavigate } from "react-router-dom";

import { RunStatusBadge, formatDuration } from "@/components/runs/run-status-badge";
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
import type { AgentRunSummary } from "@/lib/types";
import { timeAgo } from "@/lib/utils";

const columnHelper = createColumnHelper<AgentRunSummary>();

const columns = [
  columnHelper.accessor("agent_name", {
    header: "Agent",
    cell: (info) => (
      <span className="font-medium">{info.getValue()}</span>
    ),
  }),
  columnHelper.accessor("task", {
    header: "Task",
    cell: (info) => {
      const task = info.getValue();
      const truncated = task.length > 60 ? `${task.slice(0, 60)}…` : task;
      return (
        <Tooltip content={task.length > 60 ? `${task.slice(0, 120)}…` : task}>
          <span className="block max-w-[280px] truncate text-muted-foreground">
            {truncated}
          </span>
        </Tooltip>
      );
    },
  }),
  columnHelper.display({
    id: "scope",
    header: "Repo / Service",
    cell: ({ row }) => (
      <span className="flex flex-wrap gap-1">
        {row.original.repo ? (
          <Badge variant="outline">{row.original.repo}</Badge>
        ) : null}
        {row.original.service ? (
          <Badge variant="secondary">{row.original.service}</Badge>
        ) : null}
        {!row.original.repo && !row.original.service ? (
          <span className="text-muted-foreground">—</span>
        ) : null}
      </span>
    ),
  }),
  columnHelper.accessor("user_name", {
    header: "User",
    cell: (info) => <span className="text-muted-foreground">{info.getValue()}</span>,
  }),
  columnHelper.accessor("status", {
    header: "Status",
    cell: (info) => <RunStatusBadge status={info.getValue()} />,
  }),
  columnHelper.accessor("started_at", {
    header: "Started",
    cell: (info) => (
      <span className="whitespace-nowrap tabular-nums text-muted-foreground">
        {timeAgo(info.getValue())}
      </span>
    ),
  }),
  columnHelper.display({
    id: "duration",
    header: "Duration",
    cell: ({ row }) => (
      <span className="whitespace-nowrap tabular-nums">
        {formatDuration(row.original.started_at, row.original.finished_at)}
      </span>
    ),
  }),
  columnHelper.display({
    id: "packet",
    header: "Packet",
    cell: ({ row }) =>
      row.original.context_packet_id ? (
        <Link
          to={`/packets/${row.original.context_packet_id}`}
          aria-label="Open context packet"
          className="inline-flex rounded-sm text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          onClick={(event) => event.stopPropagation()}
        >
          <PackageSearch className="size-4" aria-hidden="true" />
        </Link>
      ) : (
        <span className="text-muted-foreground">—</span>
      ),
  }),
];

/** Dense agent-runs table (TanStack Table). Row click opens the run detail. */
function RunsTable({ runs }: { runs: AgentRunSummary[] }) {
  const navigate = useNavigate();
  const data = useMemo(() => runs, [runs]);

  const table = useReactTable({
    data,
    columns,
    getCoreRowModel: getCoreRowModel(),
  });

  return (
    <Table data-testid="runs-table">
      <TableHeader>
        {table.getHeaderGroups().map((headerGroup) => (
          <TableRow key={headerGroup.id}>
            {headerGroup.headers.map((header) => (
              <TableHead key={header.id}>
                {flexRender(header.column.columnDef.header, header.getContext())}
              </TableHead>
            ))}
          </TableRow>
        ))}
      </TableHeader>
      <TableBody>
        {table.getRowModel().rows.map((row) => (
          <TableRow
            key={row.id}
            data-testid={`run-row-${row.original.id}`}
            className="cursor-pointer"
            onClick={() => navigate(`/agent-runs/${row.original.id}`)}
          >
            {row.getVisibleCells().map((cell) => (
              <TableCell key={cell.id}>
                {flexRender(cell.column.columnDef.cell, cell.getContext())}
              </TableCell>
            ))}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

export { RunsTable };

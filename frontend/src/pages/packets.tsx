import { keepPreviousData, useQuery } from "@tanstack/react-query";
import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  useReactTable,
} from "@tanstack/react-table";
import { ChevronLeft, ChevronRight, PackagePlus } from "lucide-react";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";

import { IntentBadge, OutcomeBadge } from "@/components/packets/badges";
import { CompilePacketDialog } from "@/components/packets/compile-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { PermissionDenied } from "@/components/ui/permission-denied";
import { ScoreBadge } from "@/components/ui/score-badge";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tooltip } from "@/components/ui/tooltip";
import { useDebounce } from "@/hooks/use-debounce";
import { useMe } from "@/hooks/use-me";
import { usePageTitle } from "@/hooks/use-page-title";
import { api, isApiError } from "@/lib/api";
import { queryKeys } from "@/lib/queryKeys";
import type { ContextPacketSummary, Intent, Paginated } from "@/lib/types";
import { formatNumber, timeAgo } from "@/lib/utils";

const INTENTS: Intent[] = [
  "bugfix",
  "feature",
  "refactor",
  "incident_response",
  "question",
  "unknown",
];

const columnHelper = createColumnHelper<ContextPacketSummary>();

const columns = [
  columnHelper.accessor("task", {
    header: "Task",
    cell: (info) => (
      <Tooltip content={info.getValue().slice(0, 80)}>
        <span className="block max-w-[28rem] truncate font-medium">{info.getValue()}</span>
      </Tooltip>
    ),
  }),
  columnHelper.accessor("intent", {
    header: "Intent",
    cell: (info) => <IntentBadge intent={info.getValue()} />,
  }),
  columnHelper.display({
    id: "scope",
    header: "Repo / Service",
    cell: ({ row }) => (
      <span className="flex flex-wrap gap-1">
        {row.original.repo ? <Badge variant="muted">{row.original.repo}</Badge> : null}
        {row.original.service ? <Badge variant="muted">{row.original.service}</Badge> : null}
        {!row.original.repo && !row.original.service ? (
          <span className="text-muted-foreground">—</span>
        ) : null}
      </span>
    ),
  }),
  columnHelper.accessor("source_count", {
    header: "Sources",
    cell: (info) => <span className="tabular-nums">{info.getValue()}</span>,
  }),
  columnHelper.accessor("token_estimate", {
    header: "Tokens",
    cell: (info) => <span className="tabular-nums">{formatNumber(info.getValue())}</span>,
  }),
  columnHelper.accessor("confidence_score", {
    header: "Confidence",
    cell: (info) => <ScoreBadge score={info.getValue()} />,
  }),
  columnHelper.accessor("agent_outcome", {
    header: "Outcome",
    cell: (info) => <OutcomeBadge outcome={info.getValue()} />,
  }),
  columnHelper.accessor("requested_by_name", {
    header: "Requested by",
    cell: (info) => <span className="text-muted-foreground">{info.getValue()}</span>,
  }),
  columnHelper.accessor("created_at", {
    header: "Created",
    cell: (info) => <span className="text-muted-foreground">{timeAgo(info.getValue())}</span>,
  }),
];

export default function PacketsPage() {
  usePageTitle("Context Packets");
  const navigate = useNavigate();
  const { data: me } = useMe();

  const [repoInput, setRepoInput] = useState("");
  const [serviceInput, setServiceInput] = useState("");
  const [intent, setIntent] = useState("");
  const [page, setPage] = useState(1);
  const [compileOpen, setCompileOpen] = useState(false);

  const repo = useDebounce(repoInput.trim(), 300);
  const service = useDebounce(serviceInput.trim(), 300);

  useEffect(() => {
    setPage(1);
  }, [repo, service, intent]);

  const filters = { repo, service, intent, page };
  const packetsQuery = useQuery({
    queryKey: queryKeys.packets(filters),
    queryFn: () =>
      api.get<Paginated<ContextPacketSummary>>("/v1/context-packets", {
        repo: repo || undefined,
        service: service || undefined,
        intent: intent || undefined,
        page,
      }),
    placeholderData: keepPreviousData,
  });

  const data = packetsQuery.data;
  const items = useMemo(() => data?.items ?? [], [data]);

  const table = useReactTable({
    data: items,
    columns,
    getCoreRowModel: getCoreRowModel(),
  });

  const totalPages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;

  let body: ReactNode;
  if (packetsQuery.isError) {
    const err = packetsQuery.error;
    body =
      isApiError(err) && err.status === 403 ? (
        <PermissionDenied role={me?.role} />
      ) : (
        <ErrorState
          message={isApiError(err) ? err.detail : "Failed to load context packets."}
          onRetry={() => void packetsQuery.refetch()}
        />
      );
  } else if (packetsQuery.isPending) {
    body = (
      <div className="flex flex-col gap-2" data-testid="packets-skeleton">
        {Array.from({ length: 6 }, (_, i) => (
          <Skeleton key={i} className="h-9 w-full" />
        ))}
      </div>
    );
  } else if (items.length === 0) {
    body = (
      <EmptyState
        title="No context packets"
        description="Compile a context packet for a task to see it listed here."
        action={
          <Button size="sm" onClick={() => setCompileOpen(true)}>
            <PackagePlus aria-hidden="true" /> Compile context
          </Button>
        }
      />
    );
  } else {
    body = (
      <>
        <Card>
          <Table>
            <TableHeader>
              {table.getHeaderGroups().map((headerGroup) => (
                <TableRow key={headerGroup.id}>
                  {headerGroup.headers.map((header) => (
                    <TableHead key={header.id}>
                      {header.isPlaceholder
                        ? null
                        : flexRender(header.column.columnDef.header, header.getContext())}
                    </TableHead>
                  ))}
                </TableRow>
              ))}
            </TableHeader>
            <TableBody>
              {table.getRowModel().rows.map((row) => (
                <TableRow
                  key={row.id}
                  tabIndex={0}
                  className="cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  aria-label={`Open packet: ${row.original.task}`}
                  onClick={() => navigate(`/packets/${row.original.id}`)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") navigate(`/packets/${row.original.id}`);
                  }}
                >
                  {row.getVisibleCells().map((cell) => (
                    <TableCell key={cell.id} className="text-xs">
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </TableCell>
                  ))}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Card>
        <nav
          aria-label="Pagination"
          className="flex items-center justify-between gap-2 pt-1 text-xs text-muted-foreground"
        >
          <span>
            Page {data?.page ?? page} of {totalPages} · {data?.total ?? 0} packets
          </span>
          <div className="flex items-center gap-1">
            <Button
              size="sm"
              variant="outline"
              aria-label="Previous page"
              disabled={(data?.page ?? 1) <= 1}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
            >
              <ChevronLeft aria-hidden="true" /> Prev
            </Button>
            <Button
              size="sm"
              variant="outline"
              aria-label="Next page"
              disabled={(data?.page ?? 1) >= totalPages}
              onClick={() => setPage((p) => p + 1)}
            >
              Next <ChevronRight aria-hidden="true" />
            </Button>
          </div>
        </nav>
      </>
    );
  }

  return (
    <>
      <PageHeader
        title="Context Packets"
        description="Compiled context bundles handed to agents and humans"
        actions={
          <Button size="sm" onClick={() => setCompileOpen(true)}>
            <PackagePlus aria-hidden="true" /> Compile context
          </Button>
        }
      />
      <div data-testid="page-packets" className="flex flex-col gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <Input
            aria-label="Filter by repo"
            placeholder="repo"
            className="h-7 w-36 text-xs"
            value={repoInput}
            onChange={(e) => setRepoInput(e.target.value)}
          />
          <Input
            aria-label="Filter by service"
            placeholder="service"
            className="h-7 w-36 text-xs"
            value={serviceInput}
            onChange={(e) => setServiceInput(e.target.value)}
          />
          <Select
            aria-label="Filter by intent"
            className="w-40"
            value={intent}
            onChange={(e) => setIntent(e.target.value)}
          >
            <option value="">Any intent</option>
            {INTENTS.map((i) => (
              <option key={i} value={i}>
                {i.replace(/_/g, " ")}
              </option>
            ))}
          </Select>
        </div>
        {body}
      </div>
      <CompilePacketDialog open={compileOpen} onOpenChange={setCompileOpen} />
    </>
  );
}

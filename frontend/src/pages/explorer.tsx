import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, SearchIcon, ShieldAlert } from "lucide-react";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { HighlightedText } from "@/components/explorer/highlighted-text";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { PermissionDenied } from "@/components/ui/permission-denied";
import { ScoreBadge } from "@/components/ui/score-badge";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { useDebounce } from "@/hooks/use-debounce";
import { useMe } from "@/hooks/use-me";
import { usePageTitle } from "@/hooks/use-page-title";
import { api, isApiError } from "@/lib/api";
import { queryKeys } from "@/lib/queryKeys";
import type { SearchRequest, SearchResponse, SearchResult } from "@/lib/types";
import { timeAgo } from "@/lib/utils";

const STATUS_OPTIONS = ["active", "stale", "deprecated", "archived"] as const;
const PAGE_SIZES = [10, 20, 50] as const;

function AclNotice({ count }: { count: number }) {
  return (
    <div
      role="note"
      className="flex items-center gap-2 rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-xs text-amber-700 dark:text-amber-400"
    >
      <ShieldAlert className="size-4 shrink-0" aria-hidden="true" />
      {count} result{count === 1 ? "" : "s"} hidden by access control
    </div>
  );
}

function ResultRow({ result, query }: { result: SearchResult; query: string }) {
  return (
    <li>
      <Link
        to={`/explorer/documents/${result.document_id}`}
        className="block rounded-lg border bg-card p-3 transition-colors hover:border-ring/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-1.5">
              <span className="truncate text-sm font-medium">{result.title}</span>
              <Badge variant="outline">{result.doc_type}</Badge>
              {result.status !== "active" ? (
                <Badge variant={result.status === "stale" ? "warning" : "muted"}>
                  {result.status}
                </Badge>
              ) : null}
            </div>
            <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">
              <HighlightedText text={result.snippet} query={query} />
            </p>
            <div className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px] text-muted-foreground">
              <span>{result.source_name}</span>
              {result.repo ? <Badge variant="muted">{result.repo}</Badge> : null}
              {result.service ? <Badge variant="muted">{result.service}</Badge> : null}
              <span>{timeAgo(result.last_activity_at)}</span>
            </div>
          </div>
          <div className="flex shrink-0 flex-col items-end gap-1 text-[11px] text-muted-foreground">
            <span className="font-medium tabular-nums text-foreground">
              {result.score.toFixed(2)}
            </span>
            <span className="flex items-center gap-1">
              fresh <ScoreBadge score={result.freshness_score} />
            </span>
            <span className="flex items-center gap-1">
              auth <ScoreBadge score={result.authority_score} />
            </span>
          </div>
        </div>
      </Link>
    </li>
  );
}

export default function ExplorerPage() {
  usePageTitle("Context Explorer");
  const { data: me } = useMe();
  const [searchParams, setSearchParams] = useSearchParams();

  const [input, setInput] = useState(searchParams.get("q") ?? "");
  const [docTypes, setDocTypes] = useState<string[]>([]);
  const [repoInput, setRepoInput] = useState("");
  const [serviceInput, setServiceInput] = useState("");
  const [status, setStatus] = useState("");
  const [pageSize, setPageSize] = useState<number>(20);
  const [page, setPage] = useState(1);

  const query = useDebounce(input.trim(), 300);
  const repo = useDebounce(repoInput.trim(), 300);
  const service = useDebounce(serviceInput.trim(), 300);

  // Keep ?q= in the URL in sync with the (debounced) input.
  useEffect(() => {
    setSearchParams(query ? { q: query } : {}, { replace: true });
  }, [query, setSearchParams]);

  // New query/filters restart pagination.
  useEffect(() => {
    setPage(1);
  }, [query, repo, service, status, docTypes, pageSize]);

  const request: SearchRequest = {
    query,
    doc_types: docTypes.length > 0 ? docTypes : undefined,
    repo: repo || undefined,
    service: service || undefined,
    status: status || undefined,
    page,
    page_size: pageSize,
  };

  const searchQuery = useQuery({
    queryKey: queryKeys.search(request),
    queryFn: () => api.post<SearchResponse>("/v1/search", request),
    enabled: query.length > 0,
    placeholderData: keepPreviousData,
  });

  const data = searchQuery.data;

  // Doc-type toggle options come from the current results plus anything already toggled.
  const docTypeOptions = useMemo(() => {
    const fromResults = data?.items.map((r) => r.doc_type) ?? [];
    return Array.from(new Set([...docTypes, ...fromResults])).sort();
  }, [data, docTypes]);

  const toggleDocType = (docType: string) => {
    setDocTypes((prev) =>
      prev.includes(docType) ? prev.filter((d) => d !== docType) : [...prev, docType],
    );
  };

  const totalPages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;

  let body: ReactNode;
  if (!query) {
    body = (
      <EmptyState
        icon={SearchIcon}
        title="Search your organization's context"
        description="Find docs, ADRs, runbooks, code docs and tickets across every connected source."
      />
    );
  } else if (searchQuery.isError) {
    const err = searchQuery.error;
    body =
      isApiError(err) && err.status === 403 ? (
        <PermissionDenied role={me?.role} />
      ) : (
        <ErrorState
          message={isApiError(err) ? err.detail : "Search failed."}
          onRetry={() => void searchQuery.refetch()}
        />
      );
  } else if (searchQuery.isPending) {
    body = (
      <div className="flex flex-col gap-2" data-testid="explorer-skeleton">
        {Array.from({ length: 5 }, (_, i) => (
          <Skeleton key={i} className="h-20 w-full" />
        ))}
      </div>
    );
  } else if (data && data.items.length === 0) {
    body = (
      <>
        {data.acl_blocked_count > 0 ? <AclNotice count={data.acl_blocked_count} /> : null}
        <EmptyState
          title="No results"
          description={`Nothing matched "${query}". Try different terms or fewer filters.`}
        />
      </>
    );
  } else if (data) {
    body = (
      <>
        {data.acl_blocked_count > 0 ? <AclNotice count={data.acl_blocked_count} /> : null}
        <p className="text-xs text-muted-foreground" aria-live="polite">
          {data.total} result{data.total === 1 ? "" : "s"}
        </p>
        <ul className="flex flex-col gap-2" aria-label="Search results">
          {data.items.map((result) => (
            <ResultRow key={result.chunk_id} result={result} query={query} />
          ))}
        </ul>
        <nav
          aria-label="Pagination"
          className="flex items-center justify-between gap-2 pt-1 text-xs text-muted-foreground"
        >
          <span>
            Page {data.page} of {totalPages}
          </span>
          <div className="flex items-center gap-1">
            <Button
              size="sm"
              variant="outline"
              aria-label="Previous page"
              disabled={data.page <= 1}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
            >
              <ChevronLeft aria-hidden="true" /> Prev
            </Button>
            <Button
              size="sm"
              variant="outline"
              aria-label="Next page"
              disabled={data.page >= totalPages}
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
        title="Context Explorer"
        description="Full-text + semantic search across all indexed sources"
      />
      <div data-testid="page-explorer" className="flex flex-col gap-3">
        <div className="flex flex-col gap-2">
          <div className="relative">
            <SearchIcon
              className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
              aria-hidden="true"
            />
            <Input
              type="search"
              aria-label="Search query"
              placeholder="Search docs, ADRs, runbooks, tickets…"
              className="pl-8"
              value={input}
              onChange={(e) => setInput(e.target.value)}
            />
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {docTypeOptions.length > 0 ? (
              <div
                role="group"
                aria-label="Filter by document type"
                className="flex flex-wrap items-center gap-1"
              >
                {docTypeOptions.map((docType) => {
                  const active = docTypes.includes(docType);
                  return (
                    <button
                      key={docType}
                      type="button"
                      aria-pressed={active}
                      onClick={() => toggleDocType(docType)}
                      className="rounded-full focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    >
                      <Badge variant={active ? "default" : "outline"}>{docType}</Badge>
                    </button>
                  );
                })}
              </div>
            ) : null}
            <Input
              aria-label="Filter by repo"
              placeholder="repo"
              className="h-7 w-32 text-xs"
              value={repoInput}
              onChange={(e) => setRepoInput(e.target.value)}
            />
            <Input
              aria-label="Filter by service"
              placeholder="service"
              className="h-7 w-32 text-xs"
              value={serviceInput}
              onChange={(e) => setServiceInput(e.target.value)}
            />
            <Select
              aria-label="Filter by status"
              className="w-32"
              value={status}
              onChange={(e) => setStatus(e.target.value)}
            >
              <option value="">Any status</option>
              {STATUS_OPTIONS.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </Select>
            <Select
              aria-label="Results per page"
              className="w-28"
              value={String(pageSize)}
              onChange={(e) => setPageSize(Number(e.target.value))}
            >
              {PAGE_SIZES.map((size) => (
                <option key={size} value={size}>
                  {size} / page
                </option>
              ))}
            </Select>
          </div>
        </div>
        {body}
      </div>
    </>
  );
}

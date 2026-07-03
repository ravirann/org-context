import { useQuery } from "@tanstack/react-query";
import {
  ExternalLink,
  FileCode2,
  GitPullRequest,
  MessageSquare,
} from "lucide-react";
import type { ReactNode } from "react";
import { useParams } from "react-router-dom";

import { PacketSummaryCard } from "@/components/runs/packet-summary-card";
import { RunStatusBadge, formatDuration } from "@/components/runs/run-status-badge";
import { TerminalOutput } from "@/components/runs/terminal-output";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { ErrorState } from "@/components/ui/error-state";
import { PageHeader } from "@/components/ui/page-header";
import { PermissionDenied } from "@/components/ui/permission-denied";
import { Skeleton } from "@/components/ui/skeleton";
import { useMe } from "@/hooks/use-me";
import { usePageTitle } from "@/hooks/use-page-title";
import { api, isApiError } from "@/lib/api";
import { queryKeys } from "@/lib/queryKeys";
import type { AgentRunDetail } from "@/lib/types";
import { cn, formatDateTime } from "@/lib/utils";

function DetailSkeleton() {
  return (
    <div data-testid="run-detail-loading" className="flex flex-col gap-3">
      <Skeleton className="h-24 w-full" />
      <div className="grid gap-3 md:grid-cols-2">
        <Skeleton className="h-48 w-full" />
        <Skeleton className="h-48 w-full" />
        <Skeleton className="h-48 w-full" />
        <Skeleton className="h-48 w-full" />
      </div>
    </div>
  );
}

function MetaItem({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="min-w-0">
      <dt className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </dt>
      <dd className="mt-0.5 truncate text-sm tabular-nums">{value}</dd>
    </div>
  );
}

function RunBody({ run }: { run: AgentRunDetail }) {
  return (
    <div className="flex flex-col gap-3">
      {/* Header card */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex flex-wrap items-center gap-2">
            <CardTitle className="text-base">{run.agent_name}</CardTitle>
            <RunStatusBadge status={run.status} />
            {run.repo ? <Badge variant="outline">{run.repo}</Badge> : null}
            {run.service ? <Badge variant="secondary">{run.service}</Badge> : null}
          </div>
          <p className="text-xs text-muted-foreground">{run.task}</p>
        </CardHeader>
        <CardContent>
          <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <MetaItem label="Triggered by" value={run.user_name} />
            <MetaItem label="Started" value={formatDateTime(run.started_at)} />
            <MetaItem label="Finished" value={formatDateTime(run.finished_at)} />
            <MetaItem
              label="Duration"
              value={formatDuration(run.started_at, run.finished_at)}
            />
          </dl>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            {run.pr_url ? (
              <a
                href={run.pr_url}
                target="_blank"
                rel="noreferrer"
                className={cn(buttonVariants({ variant: "outline", size: "sm" }))}
              >
                <GitPullRequest aria-hidden="true" />
                View pull request
                <ExternalLink aria-hidden="true" />
              </a>
            ) : null}
            {run.langfuse_trace_url ? (
              <a
                href={run.langfuse_trace_url}
                target="_blank"
                rel="noreferrer"
                className={cn(buttonVariants({ variant: "outline", size: "sm" }))}
              >
                Langfuse trace
                <ExternalLink aria-hidden="true" />
              </a>
            ) : (
              <span className="text-xs text-muted-foreground">
                No trace recorded
              </span>
            )}
          </div>
        </CardContent>
      </Card>

      <div className="grid items-start gap-3 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Original task</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="whitespace-pre-wrap text-sm leading-6">{run.task}</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Compiled context</CardTitle>
          </CardHeader>
          <CardContent>
            {run.context_packet ? (
              <PacketSummaryCard packet={run.context_packet} />
            ) : (
              <p className="text-xs text-muted-foreground">
                No context packet was attached to this run.
              </p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Agent plan</CardTitle>
          </CardHeader>
          <CardContent>
            {run.plan ? (
              <pre className="scroll-area max-h-80 overflow-auto whitespace-pre-wrap rounded-md bg-muted/50 p-3 font-mono text-xs leading-5">
                {run.plan}
              </pre>
            ) : (
              <p className="text-xs text-muted-foreground">No plan recorded.</p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex-row items-center justify-between space-y-0">
            <CardTitle>Changed files</CardTitle>
            <Badge variant="secondary" aria-label={`${run.changed_files.length} changed files`}>
              {run.changed_files.length}
            </Badge>
          </CardHeader>
          <CardContent>
            {run.changed_files.length > 0 ? (
              <ul className="flex flex-col gap-1">
                {run.changed_files.map((file) => (
                  <li
                    key={file}
                    className="flex items-center gap-1.5 font-mono text-xs"
                  >
                    <FileCode2
                      className="size-3.5 shrink-0 text-muted-foreground"
                      aria-hidden="true"
                    />
                    <span className="truncate">{file}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-xs text-muted-foreground">No files changed.</p>
            )}
          </CardContent>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Test output</CardTitle>
          </CardHeader>
          <CardContent>
            {run.test_output ? (
              <TerminalOutput output={run.test_output} />
            ) : (
              <p className="text-xs text-muted-foreground">
                No test output captured.
              </p>
            )}
          </CardContent>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader className="flex-row items-center justify-between space-y-0">
            <CardTitle>Reviewer comments</CardTitle>
            <Badge variant="secondary">{run.reviewer_comments.length}</Badge>
          </CardHeader>
          <CardContent>
            {run.reviewer_comments.length > 0 ? (
              <ul className="flex flex-col gap-2">
                {run.reviewer_comments.map((comment, index) => (
                  <li key={index} className="flex items-start gap-2">
                    <MessageSquare
                      className="mt-1 size-3.5 shrink-0 text-muted-foreground"
                      aria-hidden="true"
                    />
                    <div className="min-w-0 rounded-lg border bg-muted/40 px-3 py-2">
                      <p className="text-xs font-medium">{comment.author}</p>
                      <p className="mt-0.5 text-xs text-muted-foreground">
                        {comment.comment}
                      </p>
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-xs text-muted-foreground">
                No reviewer comments yet.
              </p>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

export default function AgentRunDetailPage() {
  usePageTitle("Agent Run");
  const { id = "" } = useParams();
  const { data: me } = useMe();

  const { data, error, isPending, refetch } = useQuery({
    queryKey: queryKeys.agentRun(id),
    queryFn: () => api.get<AgentRunDetail>(`/v1/agent-runs/${id}`),
    enabled: id !== "",
  });

  let content;
  if (isPending) {
    content = <DetailSkeleton />;
  } else if (error) {
    if (isApiError(error) && error.status === 403) {
      content = <PermissionDenied role={me?.role} />;
    } else if (isApiError(error) && error.status === 404) {
      content = (
        <ErrorState
          title="Agent run not found"
          message={`No agent run exists with id ${id}.`}
        />
      );
    } else {
      content = (
        <ErrorState
          message={isApiError(error) ? error.detail : "Failed to load the run."}
          onRetry={() => void refetch()}
        />
      );
    }
  } else {
    content = <RunBody run={data} />;
  }

  return (
    <>
      <PageHeader
        title={data ? data.agent_name : "Agent Run"}
        description={data ? `Run ${data.id}` : undefined}
      />
      <div data-testid="page-agent-run-detail">{content}</div>
    </>
  );
}

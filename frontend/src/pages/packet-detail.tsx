import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  Bot,
  CheckSquare,
  ChevronDown,
  ChevronRight,
  MessageSquare,
  ShieldAlert,
  ThumbsDown,
  ThumbsUp,
} from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import { IntentBadge, OutcomeBadge } from "@/components/packets/badges";
import { PacketFeedbackDialog } from "@/components/packets/feedback-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { PageHeader } from "@/components/ui/page-header";
import { PermissionDenied } from "@/components/ui/permission-denied";
import { ScoreBadge } from "@/components/ui/score-badge";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { useMe } from "@/hooks/use-me";
import { usePageTitle } from "@/hooks/use-page-title";
import { api, isApiError } from "@/lib/api";
import { queryKeys } from "@/lib/queryKeys";
import type { ContextPacketDetail, FeedbackType } from "@/lib/types";
import { formatDateTime, formatNumber, timeAgo } from "@/lib/utils";

const FEEDBACK_BADGES: Record<string, "success" | "destructive" | "warning" | "muted"> = {
  useful: "success",
  irrelevant: "destructive",
  missing_context: "warning",
};

export default function PacketDetailPage() {
  usePageTitle("Context Packet");
  const { id = "" } = useParams();
  const { data: me } = useMe();
  const [rejectedOpen, setRejectedOpen] = useState(false);
  const [feedbackType, setFeedbackType] = useState<FeedbackType | null>(null);

  const packetQuery = useQuery({
    queryKey: queryKeys.packet(id),
    queryFn: () => api.get<ContextPacketDetail>(`/v1/context-packets/${id}`),
    enabled: id.length > 0,
  });

  if (packetQuery.isError) {
    const err = packetQuery.error;
    const denied = isApiError(err) && err.status === 403;
    return (
      <>
        <PageHeader title="Context Packet" />
        <div data-testid="page-packet-detail">
          {denied ? (
            <PermissionDenied role={me?.role} />
          ) : isApiError(err) && err.status === 404 ? (
            <ErrorState
              title="Packet not found"
              message="Context packet not found or not accessible."
            />
          ) : (
            <ErrorState
              message={isApiError(err) ? err.detail : "Failed to load the context packet."}
              onRetry={() => void packetQuery.refetch()}
            />
          )}
        </div>
      </>
    );
  }

  if (packetQuery.isPending) {
    return (
      <>
        <PageHeader title="Context Packet" />
        <div data-testid="page-packet-detail" className="flex flex-col gap-3">
          <Skeleton className="h-24 w-full" />
          <div className="grid gap-3 lg:grid-cols-2">
            <Skeleton className="h-72 w-full" />
            <Skeleton className="h-72 w-full" />
          </div>
        </div>
      </>
    );
  }

  const packet = packetQuery.data;

  return (
    <>
      <PageHeader
        title="Context Packet"
        actions={
          <div className="flex items-center gap-2" role="group" aria-label="Packet feedback">
            <Button size="sm" variant="outline" onClick={() => setFeedbackType("useful")}>
              <ThumbsUp aria-hidden="true" /> Useful
            </Button>
            <Button size="sm" variant="outline" onClick={() => setFeedbackType("irrelevant")}>
              <ThumbsDown aria-hidden="true" /> Irrelevant
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => setFeedbackType("missing_context")}
            >
              <MessageSquare aria-hidden="true" /> Missing context
            </Button>
          </div>
        }
      />
      <div data-testid="page-packet-detail" className="flex flex-col gap-3">
        {/* Summary header */}
        <Card>
          <CardContent className="flex flex-col gap-2 pt-4">
            <p className="text-sm font-medium leading-5">{packet.task}</p>
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 text-xs text-muted-foreground">
              <IntentBadge intent={packet.intent} />
              {packet.repo ? <Badge variant="muted">{packet.repo}</Badge> : null}
              {packet.service ? <Badge variant="muted">{packet.service}</Badge> : null}
              <span>requested by {packet.requested_by_name}</span>
              <span title={formatDateTime(packet.created_at)}>
                {timeAgo(packet.created_at)}
              </span>
              <OutcomeBadge outcome={packet.agent_outcome} />
            </div>
            <Separator />
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 text-xs text-muted-foreground">
              <span className="flex items-center gap-1">
                confidence <ScoreBadge score={packet.confidence_score} />
              </span>
              <span className="flex items-center gap-1">
                freshness <ScoreBadge score={packet.freshness_score} />
              </span>
              <span className="flex items-center gap-1">
                authority <ScoreBadge score={packet.authority_score} />
              </span>
              <span className="tabular-nums">
                ~{formatNumber(packet.token_estimate)} tokens
              </span>
            </div>
          </CardContent>
        </Card>

        <div className="grid gap-3 lg:grid-cols-5">
          {/* Left column: sources */}
          <div className="flex flex-col gap-3 lg:col-span-2">
            <Card>
              <CardHeader>
                <CardTitle>Selected sources ({packet.selected_sources.length})</CardTitle>
              </CardHeader>
              <CardContent className="flex flex-col gap-1.5">
                {packet.selected_sources.length === 0 ? (
                  <EmptyState
                    title="No sources selected"
                    description="The engine could not find relevant context for this task."
                    className="py-6"
                  />
                ) : (
                  packet.selected_sources.map((source) => (
                    <div
                      key={source.document_id}
                      className="rounded-md border px-3 py-2"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <Link
                          to={`/explorer/documents/${source.document_id}`}
                          className="min-w-0 flex-1 truncate text-sm font-medium text-primary hover:underline"
                        >
                          {source.title}
                        </Link>
                        <Badge variant="outline">{source.doc_type}</Badge>
                        <span className="text-xs tabular-nums text-muted-foreground">
                          {source.score.toFixed(2)}
                        </span>
                      </div>
                      {source.reasons.length > 0 ? (
                        <div className="mt-1 flex flex-wrap gap-1">
                          {source.reasons.map((reason) => (
                            <Badge key={reason} variant="muted">
                              {reason}
                            </Badge>
                          ))}
                        </div>
                      ) : null}
                    </div>
                  ))
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <button
                  type="button"
                  aria-expanded={rejectedOpen}
                  onClick={() => setRejectedOpen((v) => !v)}
                  className="flex items-center gap-1.5 text-sm font-semibold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  {rejectedOpen ? (
                    <ChevronDown className="size-4" aria-hidden="true" />
                  ) : (
                    <ChevronRight className="size-4" aria-hidden="true" />
                  )}
                  Rejected sources ({packet.rejected_sources.length})
                </button>
              </CardHeader>
              {rejectedOpen ? (
                <CardContent className="flex flex-col gap-1.5">
                  {packet.rejected_sources.length === 0 ? (
                    <p className="text-xs text-muted-foreground">Nothing was rejected.</p>
                  ) : (
                    packet.rejected_sources.map((source) => (
                      <div
                        key={source.document_id}
                        className="rounded-md border border-dashed px-3 py-2 text-muted-foreground"
                      >
                        <div className="flex items-center justify-between gap-2">
                          <Link
                            to={`/explorer/documents/${source.document_id}`}
                            className="min-w-0 flex-1 truncate text-sm hover:underline"
                          >
                            {source.title}
                          </Link>
                          <Badge variant="muted">{source.doc_type}</Badge>
                          <span className="text-xs tabular-nums">{source.score.toFixed(2)}</span>
                        </div>
                        <p className="mt-0.5 text-xs italic">{source.reason}</p>
                      </div>
                    ))
                  )}
                </CardContent>
              ) : null}
            </Card>

            {packet.agent_run ? (
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-1.5">
                    <Bot className="size-4" aria-hidden="true" /> Agent run
                  </CardTitle>
                </CardHeader>
                <CardContent className="flex flex-col gap-1.5 text-xs text-muted-foreground">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-medium text-foreground">
                      {packet.agent_run.agent_name}
                    </span>
                    <Badge
                      variant={
                        packet.agent_run.status === "succeeded"
                          ? "success"
                          : packet.agent_run.status === "failed"
                            ? "destructive"
                            : "muted"
                      }
                    >
                      {packet.agent_run.status}
                    </Badge>
                    <span>{timeAgo(packet.agent_run.started_at)}</span>
                  </div>
                  <Link
                    to={`/agent-runs/${packet.agent_run.id}`}
                    className="text-primary hover:underline"
                  >
                    View run details
                  </Link>
                </CardContent>
              </Card>
            ) : null}

            <Card>
              <CardHeader>
                <CardTitle>Human feedback ({packet.feedback.length})</CardTitle>
              </CardHeader>
              <CardContent className="flex flex-col gap-1.5">
                {packet.feedback.length === 0 ? (
                  <p className="text-xs text-muted-foreground">
                    No feedback yet — use the buttons above to rate this packet.
                  </p>
                ) : (
                  <ul className="flex flex-col gap-1.5" aria-label="Feedback entries">
                    {packet.feedback.map((entry) => (
                      <li key={entry.id} className="rounded-md border px-3 py-2 text-xs">
                        <div className="flex flex-wrap items-center gap-2">
                          <Badge variant={FEEDBACK_BADGES[entry.type] ?? "muted"}>
                            {entry.type.replace(/_/g, " ")}
                          </Badge>
                          <span className="text-muted-foreground">
                            {entry.user_name} · {timeAgo(entry.created_at)}
                          </span>
                        </div>
                        {entry.comment ? <p className="mt-1">{entry.comment}</p> : null}
                      </li>
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Right column: compiled context + annotations */}
          <div className="flex flex-col gap-3 lg:col-span-3">
            <Card>
              <CardHeader>
                <CardTitle>Compiled context</CardTitle>
              </CardHeader>
              <CardContent>
                <pre className="max-h-[32rem] overflow-y-auto whitespace-pre-wrap rounded-md bg-muted/40 p-3 font-mono text-xs leading-5">
                  {packet.compiled_context}
                </pre>
              </CardContent>
            </Card>

            {packet.citations.length > 0 ? (
              <Card>
                <CardHeader>
                  <CardTitle>Citations ({packet.citations.length})</CardTitle>
                </CardHeader>
                <CardContent className="flex flex-col gap-2">
                  {packet.citations.map((citation) => (
                    <div key={citation.marker} className="flex gap-2 text-xs">
                      <Badge variant="secondary" className="h-fit shrink-0 font-mono">
                        {citation.marker}
                      </Badge>
                      <div className="min-w-0 flex-1">
                        <Link
                          to={`/explorer/documents/${citation.document_id}`}
                          className="font-medium text-primary hover:underline"
                        >
                          {citation.title}
                        </Link>
                        <blockquote className="mt-0.5 border-l-2 border-border pl-2 text-muted-foreground">
                          {citation.quote}
                        </blockquote>
                      </div>
                    </div>
                  ))}
                </CardContent>
              </Card>
            ) : null}

            {packet.conflict_notes.length > 0 ? (
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-1.5">
                    <AlertTriangle
                      className="size-4 text-amber-600 dark:text-amber-400"
                      aria-hidden="true"
                    />
                    Conflict resolution notes
                  </CardTitle>
                </CardHeader>
                <CardContent className="flex flex-col gap-2 text-xs">
                  {packet.conflict_notes.map((note) => (
                    <div key={note.conflict_id} className="rounded-md border px-3 py-2">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-mono text-[11px] text-muted-foreground">
                          {note.topic_key}
                        </span>
                        {note.chosen_document_id ? (
                          <Link
                            to={`/explorer/documents/${note.chosen_document_id}`}
                            className="text-primary hover:underline"
                          >
                            chosen document
                          </Link>
                        ) : null}
                      </div>
                      <p className="mt-1">{note.note}</p>
                    </div>
                  ))}
                </CardContent>
              </Card>
            ) : null}

            {packet.acl_notes.blocked_count > 0 ? (
              <div
                role="note"
                className="flex items-start gap-2 rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-xs text-amber-700 dark:text-amber-400"
              >
                <ShieldAlert className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
                <span>
                  {packet.acl_notes.blocked_count} source
                  {packet.acl_notes.blocked_count === 1 ? "" : "s"} filtered by access control.{" "}
                  {packet.acl_notes.note}
                </span>
              </div>
            ) : null}

            {packet.risks.length > 0 ? (
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-1.5">
                    <AlertTriangle
                      className="size-4 text-amber-600 dark:text-amber-400"
                      aria-hidden="true"
                    />
                    Risks
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <ul
                    className="ml-4 list-disc text-xs text-amber-700 dark:text-amber-400"
                    aria-label="Risks"
                  >
                    {packet.risks.map((risk) => (
                      <li key={risk} className="mt-0.5">
                        {risk}
                      </li>
                    ))}
                  </ul>
                </CardContent>
              </Card>
            ) : null}

            {packet.recommended_tests.length > 0 ? (
              <Card>
                <CardHeader>
                  <CardTitle>Recommended tests</CardTitle>
                </CardHeader>
                <CardContent>
                  <ul className="flex flex-col gap-1 text-xs" aria-label="Recommended tests">
                    {packet.recommended_tests.map((test) => (
                      <li key={test} className="flex items-start gap-1.5">
                        <CheckSquare
                          className="mt-0.5 size-3.5 shrink-0 text-muted-foreground"
                          aria-hidden="true"
                        />
                        {test}
                      </li>
                    ))}
                  </ul>
                </CardContent>
              </Card>
            ) : null}
          </div>
        </div>
      </div>
      <PacketFeedbackDialog
        packetId={id}
        type={feedbackType}
        onClose={() => setFeedbackType(null)}
      />
    </>
  );
}

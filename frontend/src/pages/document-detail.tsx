import { useMutation, useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  Clock,
  ExternalLink,
  Globe,
  Lock,
  ShieldQuestion,
} from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { PageHeader } from "@/components/ui/page-header";
import { PermissionDenied } from "@/components/ui/permission-denied";
import { ScoreBadge } from "@/components/ui/score-badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useToast } from "@/components/ui/toast";
import { useMe } from "@/hooks/use-me";
import { usePageTitle } from "@/hooks/use-page-title";
import { api, isApiError } from "@/lib/api";
import { queryKeys } from "@/lib/queryKeys";
import type { DocumentDetail, Feedback, FeedbackType } from "@/lib/types";
import { formatNumber, timeAgo } from "@/lib/utils";

const PREVIEW_CHARS = 120;

function ChunkRow({ chunk }: { chunk: DocumentDetail["chunks"][number] }) {
  const [expanded, setExpanded] = useState(false);
  const truncated = chunk.content.length > PREVIEW_CHARS;
  const preview = truncated ? `${chunk.content.slice(0, PREVIEW_CHARS)}…` : chunk.content;
  return (
    <TableRow>
      <TableCell className="w-12 tabular-nums text-muted-foreground">{chunk.ord}</TableCell>
      <TableCell className="w-20 tabular-nums">{formatNumber(chunk.token_count)}</TableCell>
      <TableCell>
        <span className="whitespace-pre-wrap text-xs">{expanded ? chunk.content : preview}</span>
      </TableCell>
      <TableCell className="w-20 text-right">
        {truncated ? (
          <Button
            size="sm"
            variant="ghost"
            aria-expanded={expanded}
            aria-label={`${expanded ? "Collapse" : "Expand"} chunk ${chunk.ord}`}
            onClick={() => setExpanded((v) => !v)}
          >
            {expanded ? "Collapse" : "Expand"}
          </Button>
        ) : null}
      </TableCell>
    </TableRow>
  );
}

export default function DocumentDetailPage() {
  usePageTitle("Document");
  const { id = "" } = useParams();
  const { data: me } = useMe();
  const { toast } = useToast();

  const docQuery = useQuery({
    queryKey: queryKeys.document(id),
    queryFn: () => api.get<DocumentDetail>(`/v1/documents/${id}`),
    enabled: id.length > 0,
  });

  const feedbackMutation = useMutation({
    mutationFn: (type: FeedbackType) =>
      api.post<Feedback>("/v1/feedback", { type, document_id: id }),
    onSuccess: (_, type) => {
      toast({
        title: type === "stale_context" ? "Reported as stale" : "Permission issue reported",
        variant: "success",
      });
    },
    onError: (error) => {
      toast({
        title: "Failed to send feedback",
        description: isApiError(error) ? error.detail : "Unexpected error",
        variant: "error",
      });
    },
  });

  if (docQuery.isError) {
    const err = docQuery.error;
    const denied = isApiError(err) && err.status === 403;
    const notFound = isApiError(err) && err.status === 404;
    return (
      <>
        <PageHeader title="Document" />
        <div data-testid="page-document-detail">
          {denied ? (
            <PermissionDenied role={me?.role} />
          ) : notFound ? (
            <ErrorState
              title="Document not found"
              message="Document not found or not accessible."
            />
          ) : (
            <ErrorState
              message={isApiError(err) ? err.detail : "Failed to load the document."}
              onRetry={() => void docQuery.refetch()}
            />
          )}
        </div>
      </>
    );
  }

  if (docQuery.isPending) {
    return (
      <>
        <PageHeader title="Document" />
        <div data-testid="page-document-detail" className="flex flex-col gap-3">
          <Skeleton className="h-8 w-2/3" />
          <Skeleton className="h-4 w-1/2" />
          <Skeleton className="h-64 w-full" />
        </div>
      </>
    );
  }

  const doc = docQuery.data;

  return (
    <>
      <PageHeader
        title={doc.title}
        actions={
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              variant="outline"
              disabled={feedbackMutation.isPending}
              onClick={() => feedbackMutation.mutate("stale_context")}
            >
              <Clock aria-hidden="true" /> Report stale
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={feedbackMutation.isPending}
              onClick={() => feedbackMutation.mutate("permission_issue")}
            >
              <ShieldQuestion aria-hidden="true" /> Report permission issue
            </Button>
          </div>
        }
      />
      <div data-testid="page-document-detail" className="flex flex-col gap-3">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 text-xs text-muted-foreground">
          <Badge variant="outline">{doc.doc_type}</Badge>
          <Badge
            variant={
              doc.status === "active" ? "success" : doc.status === "stale" ? "warning" : "muted"
            }
          >
            {doc.status}
          </Badge>
          <span>
            {doc.source.name} ({doc.source.type})
          </span>
          {doc.author_name ? <span>by {doc.author_name}</span> : null}
          {doc.team_name ? <Badge variant="muted">{doc.team_name}</Badge> : null}
          {doc.repo ? <Badge variant="muted">{doc.repo}</Badge> : null}
          {doc.service ? <Badge variant="muted">{doc.service}</Badge> : null}
          {doc.topic_key ? (
            <span className="font-mono text-[11px]">{doc.topic_key}</span>
          ) : null}
          <span className="flex items-center gap-1">
            fresh <ScoreBadge score={doc.freshness_score} />
          </span>
          <span className="flex items-center gap-1">
            auth <ScoreBadge score={doc.authority_score} />
          </span>
          <span>{timeAgo(doc.last_activity_at)}</span>
          <span>used in {formatNumber(doc.citations_of)} packets</span>
          {doc.url ? (
            <a
              href={doc.url}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 text-primary hover:underline"
            >
              Open source <ExternalLink className="size-3" aria-hidden="true" />
            </a>
          ) : null}
        </div>

        {doc.conflicts.length > 0 ? (
          <div
            role="alert"
            className="flex flex-col gap-1.5 rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-xs text-amber-700 dark:text-amber-400"
          >
            <span className="flex items-center gap-1.5 font-medium">
              <AlertTriangle className="size-4" aria-hidden="true" />
              This document conflicts with other sources
            </span>
            <ul className="ml-5 list-disc">
              {doc.conflicts.map((conflict) => (
                <li key={conflict.id}>
                  <Link to={`/conflicts/${conflict.id}`} className="hover:underline">
                    {conflict.title}
                  </Link>{" "}
                  <span className="font-mono">({conflict.topic_key})</span> — {conflict.status}
                </li>
              ))}
            </ul>
          </div>
        ) : null}

        <Tabs defaultValue="content">
          <TabsList>
            <TabsTrigger value="content">Content</TabsTrigger>
            <TabsTrigger value="chunks">Chunks ({doc.chunks.length})</TabsTrigger>
            <TabsTrigger value="permissions">Permissions</TabsTrigger>
            <TabsTrigger value="related">Related ({doc.related.length})</TabsTrigger>
            <TabsTrigger value="usage">Usage ({doc.packet_usage.length})</TabsTrigger>
          </TabsList>

          <TabsContent value="content">
            <Card>
              <CardContent className="pt-4">
                <article className="max-w-3xl whitespace-pre-wrap text-sm leading-6">
                  {doc.content}
                </article>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="chunks">
            {doc.chunks.length === 0 ? (
              <EmptyState title="No chunks" description="This document has not been indexed yet." />
            ) : (
              <Card>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Ord</TableHead>
                      <TableHead>Tokens</TableHead>
                      <TableHead>Content</TableHead>
                      <TableHead />
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {doc.chunks.map((chunk) => (
                      <ChunkRow key={chunk.id} chunk={chunk} />
                    ))}
                  </TableBody>
                </Table>
              </Card>
            )}
          </TabsContent>

          <TabsContent value="permissions">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-1.5">
                  {doc.acl.public ? (
                    <Globe className="size-4" aria-hidden="true" />
                  ) : (
                    <Lock className="size-4" aria-hidden="true" />
                  )}
                  Access control
                </CardTitle>
              </CardHeader>
              <CardContent className="flex flex-col gap-2 text-sm">
                {doc.acl.public ? (
                  <p>This document is public — everyone in the organization can read it.</p>
                ) : (
                  <>
                    <p>
                      Restricted document. Visible to {doc.acl.team_names.length} team
                      {doc.acl.team_names.length === 1 ? "" : "s"} and {doc.acl.user_count} user
                      {doc.acl.user_count === 1 ? "" : "s"} with direct access.
                    </p>
                    {doc.acl.team_names.length > 0 ? (
                      <div className="flex flex-wrap gap-1">
                        {doc.acl.team_names.map((team) => (
                          <Badge key={team} variant="secondary">
                            {team}
                          </Badge>
                        ))}
                      </div>
                    ) : null}
                  </>
                )}
                <p className="text-xs text-muted-foreground">
                  Search results and context packets only include this document for callers who
                  pass this ACL; everyone else never sees it.
                </p>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="related">
            {doc.related.length === 0 ? (
              <EmptyState
                title="No related documents"
                description="No entity edges link this document to others yet."
              />
            ) : (
              <ul className="flex flex-col gap-1.5" aria-label="Related documents">
                {doc.related.map((rel) => (
                  <li key={rel.id}>
                    <Link
                      to={`/explorer/documents/${rel.id}`}
                      className="flex items-center gap-2 rounded-md border bg-card px-3 py-2 text-sm transition-colors hover:border-ring/60"
                    >
                      <span className="min-w-0 flex-1 truncate">{rel.title}</span>
                      <Badge variant="outline">{rel.doc_type}</Badge>
                      <Badge variant="muted">{rel.relation}</Badge>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </TabsContent>

          <TabsContent value="usage">
            {doc.packet_usage.length === 0 ? (
              <EmptyState
                title="Not used in any packets"
                description="This document has not been retrieved for a context packet yet."
              />
            ) : (
              <Card>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Task</TableHead>
                      <TableHead>When</TableHead>
                      <TableHead>Outcome</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {doc.packet_usage.map((usage) => (
                      <TableRow key={`${usage.packet_id}-${usage.created_at}`}>
                        <TableCell>
                          <Link
                            to={`/packets/${usage.packet_id}`}
                            className="text-primary hover:underline"
                          >
                            {usage.task}
                          </Link>
                        </TableCell>
                        <TableCell className="text-xs text-muted-foreground">
                          {timeAgo(usage.created_at)}
                        </TableCell>
                        <TableCell>
                          {usage.was_selected ? (
                            <Badge variant="success">selected</Badge>
                          ) : (
                            <Badge variant="muted">rejected</Badge>
                          )}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </Card>
            )}
          </TabsContent>
        </Tabs>
      </div>
    </>
  );
}

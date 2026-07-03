import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ExternalLink } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useParams } from "react-router-dom";

import { AffectedChips } from "@/components/conflicts/affected-chips";
import { ConflictDocumentCard } from "@/components/conflicts/conflict-document-card";
import { ConflictStatusBadge } from "@/components/conflicts/conflict-status-badge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { ErrorState } from "@/components/ui/error-state";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { PermissionDenied } from "@/components/ui/permission-denied";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/toast";
import { useMe } from "@/hooks/use-me";
import { usePageTitle } from "@/hooks/use-page-title";
import { api, isApiError } from "@/lib/api";
import { queryKeys } from "@/lib/queryKeys";
import type { ConflictDetail, ConflictResolveRequest } from "@/lib/types";
import { formatDateTime } from "@/lib/utils";

/**
 * The recommended source of truth: the API's pick when present, otherwise the
 * document with the highest authority × freshness product.
 */
function computeRecommendedId(detail: ConflictDetail): string | null {
  if (detail.recommended_document_id) return detail.recommended_document_id;
  let bestId: string | null = null;
  let bestScore = -Infinity;
  for (const doc of detail.documents) {
    const score = doc.authority_score * doc.freshness_score;
    if (score > bestScore) {
      bestScore = score;
      bestId = doc.id;
    }
  }
  return bestId;
}

function ResolutionSummary({ detail }: { detail: ConflictDetail }) {
  return (
    <Card data-testid="resolution-summary">
      <CardHeader>
        <CardTitle>Resolution</CardTitle>
        <CardDescription>
          Resolved by {detail.resolved_by_name ?? "unknown"} ·{" "}
          {formatDateTime(detail.resolved_at)}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-2">
        <p className="whitespace-pre-wrap text-sm">{detail.resolution_note}</p>
        {detail.linked_adr_url ? (
          <a
            href={detail.linked_adr_url}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline"
          >
            Linked ADR / document
            <ExternalLink className="size-3" aria-hidden="true" />
          </a>
        ) : null}
      </CardContent>
    </Card>
  );
}

function ResolutionForm({
  detail,
  selectedId,
  canResolve,
  role,
}: {
  detail: ConflictDetail;
  selectedId: string | null;
  canResolve: boolean;
  role: string | undefined;
}) {
  const [note, setNote] = useState("");
  const [adrUrl, setAdrUrl] = useState("");
  const [noteError, setNoteError] = useState(false);
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const resolve = useMutation({
    mutationFn: (body: ConflictResolveRequest) =>
      api.post<ConflictDetail>(`/v1/conflicts/${detail.id}/resolve`, body),
    onSuccess: () => {
      toast({ title: "Conflict resolved", variant: "success" });
      void queryClient.invalidateQueries({ queryKey: queryKeys.conflict(detail.id) });
      void queryClient.invalidateQueries({ queryKey: ["conflicts", "list"] });
    },
    onError: (error) => {
      toast({
        title: "Failed to resolve conflict",
        description: isApiError(error) ? error.detail : String(error),
        variant: "error",
      });
    },
  });

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    if (!note.trim()) {
      setNoteError(true);
      return;
    }
    setNoteError(false);
    resolve.mutate({
      recommended_document_id: selectedId ?? undefined,
      note: note.trim(),
      linked_adr_url: adrUrl.trim() || undefined,
    });
  };

  const disabled = !canResolve || resolve.isPending;

  return (
    <Card data-testid="resolution-form">
      <CardHeader>
        <CardTitle>Resolve this conflict</CardTitle>
        <CardDescription>
          Pick the source of truth on a card above, explain the decision and optionally
          link the ADR that settles it.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {!canResolve ? (
          <p className="mb-3 rounded-md border border-dashed px-3 py-2 text-xs text-muted-foreground">
            Only admins and leads can resolve conflicts — your current role
            {role ? ` (${role})` : ""} has read-only access here.
          </p>
        ) : null}
        <form onSubmit={onSubmit} className="space-y-3">
          <div className="space-y-1">
            <label htmlFor="resolution-note" className="text-xs font-medium">
              Resolution note <span className="text-destructive">*</span>
            </label>
            <Textarea
              id="resolution-note"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="Why is the selected document the source of truth?"
              disabled={disabled}
              aria-invalid={noteError}
            />
            {noteError ? (
              <p role="alert" className="text-xs text-destructive">
                A resolution note is required.
              </p>
            ) : null}
          </div>
          <div className="space-y-1">
            <label htmlFor="resolution-adr" className="text-xs font-medium">
              Linked ADR / doc URL <span className="text-muted-foreground">(optional)</span>
            </label>
            <Input
              id="resolution-adr"
              type="url"
              value={adrUrl}
              onChange={(e) => setAdrUrl(e.target.value)}
              placeholder="https://…"
              disabled={disabled}
            />
          </div>
          <Button type="submit" disabled={disabled}>
            {resolve.isPending ? "Resolving…" : "Resolve conflict"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}

export default function ConflictDetailPage() {
  const { id = "" } = useParams();
  const meQuery = useMe();
  const [selected, setSelected] = useState<string | null>(null);

  const query = useQuery({
    queryKey: queryKeys.conflict(id),
    queryFn: () => api.get<ConflictDetail>(`/v1/conflicts/${id}`),
    enabled: id !== "",
  });

  usePageTitle(query.data ? `Conflict · ${query.data.title}` : "Conflict");

  if (query.isPending) {
    return (
      <>
        <PageHeader title="Conflict" />
        <div data-testid="page-conflict-detail" className="space-y-3">
          <div className="grid gap-3 md:grid-cols-2" data-testid="conflict-detail-loading">
            <Skeleton className="h-56 w-full" />
            <Skeleton className="h-56 w-full" />
          </div>
          <Skeleton className="h-40 w-full" />
        </div>
      </>
    );
  }

  if (query.isError) {
    const is403 = isApiError(query.error) && query.error.status === 403;
    return (
      <>
        <PageHeader title="Conflict" />
        <div data-testid="page-conflict-detail">
          {is403 ? (
            <PermissionDenied role={meQuery.data?.role} />
          ) : (
            <ErrorState
              message={
                isApiError(query.error) ? query.error.detail : "Failed to load conflict"
              }
              onRetry={() => void query.refetch()}
            />
          )}
        </div>
      </>
    );
  }

  const detail = query.data;
  const recommendedId = computeRecommendedId(detail);
  const selectedId = selected ?? recommendedId;
  const role = meQuery.data?.role;
  const canResolve = role === "admin" || role === "lead";
  const isOpen = detail.status === "open";

  return (
    <>
      <PageHeader
        title={detail.title}
        description="Compare the conflicting documents and record which one wins."
      />
      <div data-testid="page-conflict-detail" className="space-y-4">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="outline" className="font-mono text-[10px]">
            {detail.topic_key}
          </Badge>
          <ConflictStatusBadge status={detail.status} />
          <AffectedChips affected={detail.affected} max={6} />
        </div>

        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {detail.documents.map((doc) => (
            <ConflictDocumentCard
              key={doc.id}
              document={doc}
              recommended={doc.id === recommendedId}
              selectable={isOpen && canResolve}
              selected={doc.id === selectedId}
              onSelect={setSelected}
            />
          ))}
        </div>

        {isOpen ? (
          <ResolutionForm
            detail={detail}
            selectedId={selectedId}
            canResolve={canResolve}
            role={role}
          />
        ) : (
          <ResolutionSummary detail={detail} />
        )}
      </div>
    </>
  );
}

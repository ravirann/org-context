import { CheckCircle2, ExternalLink } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { ScoreBadge } from "@/components/ui/score-badge";
import type { ConflictDocument } from "@/lib/types";
import { cn, timeAgo } from "@/lib/utils";

interface ConflictDocumentCardProps {
  document: ConflictDocument;
  /** Highlighted as the recommended source of truth. */
  recommended: boolean;
  /** Show the "use as source of truth" radio (open conflicts, resolvers only). */
  selectable: boolean;
  selected: boolean;
  onSelect: (documentId: string) => void;
}

/**
 * One side of the conflict comparison grid: source, scores, excerpt and a
 * radio to pick it as the recommended source of truth while resolving.
 */
function ConflictDocumentCard({
  document,
  recommended,
  selectable,
  selected,
  onSelect,
}: ConflictDocumentCardProps) {
  const [expanded, setExpanded] = useState(false);
  const clampable = document.excerpt.length > 240;

  return (
    <Card
      data-testid={`conflict-doc-${document.id}`}
      className={cn(
        "flex flex-col",
        recommended && "ring-2 ring-primary",
        selectable && selected && !recommended && "ring-1 ring-ring",
      )}
    >
      <CardHeader className="gap-1.5">
        {recommended ? (
          <Badge className="self-start">
            <CheckCircle2 className="size-3" aria-hidden="true" />
            Recommended source of truth
          </Badge>
        ) : null}
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="text-sm font-semibold leading-tight">
            {document.source_name}
          </span>
          <Badge variant="secondary">{document.doc_type}</Badge>
        </div>
        <p className="text-xs text-muted-foreground">{document.title}</p>
        <dl className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-muted-foreground">
          <div className="flex items-center gap-1">
            <dt>Freshness</dt>
            <dd>
              <ScoreBadge score={document.freshness_score} />
            </dd>
          </div>
          <div className="flex items-center gap-1">
            <dt>Authority</dt>
            <dd>
              <ScoreBadge score={document.authority_score} />
            </dd>
          </div>
          <div className="flex items-center gap-1">
            <dt className="sr-only">Last activity</dt>
            <dd>{timeAgo(document.last_activity_at)}</dd>
          </div>
        </dl>
      </CardHeader>
      <CardContent className="flex flex-1 flex-col gap-2">
        <blockquote
          className={cn(
            "whitespace-pre-wrap border-l-2 border-border pl-2.5 text-xs leading-relaxed text-foreground/90",
            !expanded && "line-clamp-4",
          )}
        >
          {document.excerpt}
        </blockquote>
        {clampable ? (
          <Button
            variant="ghost"
            size="sm"
            className="self-start px-1 text-xs text-muted-foreground"
            aria-expanded={expanded}
            onClick={() => setExpanded((v) => !v)}
          >
            {expanded ? "Show less" : "Show more"}
          </Button>
        ) : null}
        <div className="mt-auto flex items-center justify-between gap-2 border-t pt-2.5">
          <Link
            to={`/explorer/documents/${document.id}`}
            className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline"
          >
            Open document
            <ExternalLink className="size-3" aria-hidden="true" />
          </Link>
          {selectable ? (
            <label className="flex cursor-pointer items-center gap-1.5 text-xs text-muted-foreground">
              <input
                type="radio"
                name="recommended-document"
                className="size-3.5 accent-[var(--primary)]"
                checked={selected}
                onChange={() => onSelect(document.id)}
                aria-label={`Use ${document.source_name} — ${document.title} as source of truth`}
              />
              Source of truth
            </label>
          ) : null}
        </div>
      </CardContent>
    </Card>
  );
}

export { ConflictDocumentCard };

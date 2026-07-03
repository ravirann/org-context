import { Badge } from "@/components/ui/badge";
import type { EvalMode, EvalRunStatus } from "@/lib/types";

/** Status badge for eval runs: running (info + pulse), completed, failed. */
function EvalStatusBadge({ status }: { status: EvalRunStatus }) {
  if (status === "running") {
    return (
      <Badge variant="default">
        <span className="relative flex size-1.5" aria-hidden="true">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-primary opacity-75" />
          <span className="relative inline-flex size-1.5 rounded-full bg-primary" />
        </span>
        running
      </Badge>
    );
  }
  if (status === "completed") {
    return <Badge variant="success">completed</Badge>;
  }
  return <Badge variant="destructive">failed</Badge>;
}

/** Neutral badge for the eval mode (baseline / context_engine / comparison). */
function EvalModeBadge({ mode }: { mode: EvalMode }) {
  return <Badge variant="outline">{mode}</Badge>;
}

/** 0..1 rate -> "86%". */
function formatPercent(rate: number | null | undefined): string {
  if (rate === null || rate === undefined || Number.isNaN(rate)) return "—";
  return `${Math.round(rate * 100)}%`;
}

export { EvalStatusBadge, EvalModeBadge, formatPercent };

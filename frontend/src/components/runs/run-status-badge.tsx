import { Badge } from "@/components/ui/badge";
import type { AgentRunStatus } from "@/lib/types";

/** Status badge for agent runs: running (info + pulse), succeeded, failed. */
function RunStatusBadge({ status }: { status: AgentRunStatus }) {
  if (status === "running") {
    return (
      <Badge variant="default" data-testid="run-status-running">
        <span className="relative flex size-1.5" aria-hidden="true">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-primary opacity-75" />
          <span className="relative inline-flex size-1.5 rounded-full bg-primary" />
        </span>
        running
      </Badge>
    );
  }
  if (status === "succeeded") {
    return <Badge variant="success">succeeded</Badge>;
  }
  return <Badge variant="destructive">failed</Badge>;
}

/**
 * Humanized duration between two ISO timestamps: "4s", "2m 14s", "1h 5m".
 * Returns an em dash while the run has not finished.
 */
function formatDuration(
  startedAt: string,
  finishedAt: string | null,
): string {
  if (!finishedAt) return "—";
  const ms = new Date(finishedAt).getTime() - new Date(startedAt).getTime();
  if (Number.isNaN(ms) || ms < 0) return "—";
  const totalSeconds = Math.round(ms / 1000);
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  if (hours > 0) return `${hours}h ${minutes}m`;
  if (minutes > 0) return `${minutes}m ${seconds}s`;
  return `${seconds}s`;
}

export { RunStatusBadge, formatDuration };

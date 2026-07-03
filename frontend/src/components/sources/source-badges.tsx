import {
  AlertTriangle,
  BookOpen,
  FileText,
  Github,
  MessageSquare,
  MessagesSquare,
  ScrollText,
  Ticket,
  Workflow,
  type LucideIcon,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Spinner } from "@/components/ui/spinner";

export const SOURCE_TYPES = [
  "github",
  "jira",
  "slack",
  "confluence",
  "adr",
  "incident",
  "ci",
  "feedback",
] as const;

const TYPE_ICONS: Record<string, LucideIcon> = {
  github: Github,
  jira: Ticket,
  slack: MessageSquare,
  confluence: BookOpen,
  adr: ScrollText,
  incident: AlertTriangle,
  ci: Workflow,
  feedback: MessagesSquare,
};

/** Icon + label badge for a source type (github/jira/slack/...). */
function SourceTypeBadge({ type }: { type: string }) {
  const Icon = TYPE_ICONS[type] ?? FileText;
  return (
    <Badge variant="outline" data-testid={`source-type-${type}`}>
      <Icon className="size-3" aria-hidden="true" />
      {type}
    </Badge>
  );
}

/**
 * Sync status badge: idle=muted, syncing=info+spinner, ok=success,
 * error=destructive. Unknown statuses fall back to muted.
 */
function SyncStatusBadge({ status }: { status: string }) {
  if (status === "syncing") {
    return (
      <Badge variant="default" data-testid="sync-status-syncing">
        <Spinner className="size-3 text-primary" label="Syncing" />
        syncing
      </Badge>
    );
  }
  if (status === "ok") {
    return <Badge variant="success">ok</Badge>;
  }
  if (status === "error") {
    return <Badge variant="destructive">error</Badge>;
  }
  return <Badge variant="muted">{status}</Badge>;
}

export { SourceTypeBadge, SyncStatusBadge };

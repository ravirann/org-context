import { Badge, type BadgeProps } from "@/components/ui/badge";
import type { AgentOutcome, Intent } from "@/lib/types";

const INTENT_VARIANTS: Record<Intent, NonNullable<BadgeProps["variant"]>> = {
  bugfix: "destructive",
  feature: "default",
  refactor: "secondary",
  incident_response: "warning",
  question: "outline",
  unknown: "muted",
};

/** Colored badge for a packet intent (bugfix, feature, ...). */
function IntentBadge({ intent }: { intent: Intent }) {
  return (
    <Badge variant={INTENT_VARIANTS[intent] ?? "muted"}>
      {intent.replace(/_/g, " ")}
    </Badge>
  );
}

const OUTCOME_VARIANTS: Record<AgentOutcome, NonNullable<BadgeProps["variant"]>> = {
  pending: "muted",
  succeeded: "success",
  failed: "destructive",
  abandoned: "warning",
};

/** Colored badge for an agent outcome (pending/succeeded/failed/abandoned). */
function OutcomeBadge({ outcome }: { outcome: AgentOutcome }) {
  return <Badge variant={OUTCOME_VARIANTS[outcome] ?? "muted"}>{outcome}</Badge>;
}

export { IntentBadge, OutcomeBadge };

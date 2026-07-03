import { GitBranch, Server } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import type { ConflictAffected } from "@/lib/types";

interface AffectedChipsProps {
  affected: ConflictAffected;
  /** Chips shown before collapsing into a "+N" overflow badge. */
  max?: number;
}

/** Repo/service chips for a conflict, with a "+N" overflow badge. */
function AffectedChips({ affected, max = 3 }: AffectedChipsProps) {
  const chips = [
    ...affected.repos.map((label) => ({ kind: "repo" as const, label })),
    ...affected.services.map((label) => ({ kind: "service" as const, label })),
  ];

  if (chips.length === 0) {
    return <span className="text-xs text-muted-foreground">—</span>;
  }

  const visible = chips.slice(0, max);
  const overflow = chips.length - visible.length;

  return (
    <span className="inline-flex flex-wrap items-center gap-1">
      {visible.map((chip) => (
        <Badge
          key={`${chip.kind}:${chip.label}`}
          variant="outline"
          className="max-w-40 font-mono text-[10px]"
          title={`${chip.kind}: ${chip.label}`}
        >
          {chip.kind === "repo" ? (
            <GitBranch className="size-2.5 shrink-0" aria-hidden="true" />
          ) : (
            <Server className="size-2.5 shrink-0" aria-hidden="true" />
          )}
          <span className="truncate">{chip.label}</span>
        </Badge>
      ))}
      {overflow > 0 ? <Badge variant="muted">+{overflow}</Badge> : null}
    </span>
  );
}

export { AffectedChips };

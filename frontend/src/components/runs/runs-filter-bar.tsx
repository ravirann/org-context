import { X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { AgentRunStatus } from "@/lib/types";
import { cn } from "@/lib/utils";

export interface RunFilters {
  agent: string;
  repo: string;
  service: string;
  user_id: string;
  status: string;
  from: string;
  to: string;
}

const STATUSES: AgentRunStatus[] = ["running", "succeeded", "failed"];

const STATUS_ACTIVE_CLASSES: Record<AgentRunStatus, string> = {
  running: "border-primary/40 bg-primary/12 text-primary",
  succeeded:
    "border-emerald-500/40 bg-emerald-500/12 text-emerald-700 dark:text-emerald-400",
  failed: "border-destructive/40 bg-destructive/12 text-destructive",
};

interface RunsFilterBarProps {
  filters: RunFilters;
  onChange: (key: keyof RunFilters, value: string) => void;
  onClear: () => void;
}

/** Dense filter bar for the agent-runs list, fully controlled from the URL. */
function RunsFilterBar({ filters, onChange, onClear }: RunsFilterBarProps) {
  const hasFilters = Object.values(filters).some((value) => value !== "");

  return (
    <div
      data-testid="runs-filter-bar"
      className="mb-3 flex flex-wrap items-center gap-2"
    >
      <div
        role="group"
        aria-label="Filter by status"
        className="inline-flex items-center gap-1"
      >
        {STATUSES.map((status) => {
          const active = filters.status === status;
          return (
            <button
              key={status}
              type="button"
              aria-pressed={active}
              onClick={() => onChange("status", active ? "" : status)}
              className={cn(
                "inline-flex items-center rounded-full border px-2.5 py-0.5 text-[11px] font-medium leading-4 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                active
                  ? STATUS_ACTIVE_CLASSES[status]
                  : "border-border text-muted-foreground hover:text-foreground",
              )}
            >
              {status}
            </button>
          );
        })}
      </div>

      <Input
        aria-label="Filter by agent"
        placeholder="Agent"
        className="h-7 w-32 text-xs"
        value={filters.agent}
        onChange={(e) => onChange("agent", e.target.value)}
      />
      <Input
        aria-label="Filter by repo"
        placeholder="Repo"
        className="h-7 w-36 text-xs"
        value={filters.repo}
        onChange={(e) => onChange("repo", e.target.value)}
      />
      <Input
        aria-label="Filter by service"
        placeholder="Service"
        className="h-7 w-36 text-xs"
        value={filters.service}
        onChange={(e) => onChange("service", e.target.value)}
      />
      <Input
        aria-label="Filter by user id"
        placeholder="User ID"
        className="h-7 w-36 text-xs"
        value={filters.user_id}
        onChange={(e) => onChange("user_id", e.target.value)}
      />
      <Input
        aria-label="From date"
        type="date"
        className="h-7 w-36 text-xs"
        value={filters.from}
        onChange={(e) => onChange("from", e.target.value)}
      />
      <Input
        aria-label="To date"
        type="date"
        className="h-7 w-36 text-xs"
        value={filters.to}
        onChange={(e) => onChange("to", e.target.value)}
      />

      {hasFilters ? (
        <Button variant="ghost" size="sm" onClick={onClear}>
          <X aria-hidden="true" />
          Clear
        </Button>
      ) : null}
    </div>
  );
}

export { RunsFilterBar };

import { ChevronRight } from "lucide-react";
import { Fragment } from "react";
import { Link, useLocation } from "react-router-dom";

import { cn } from "@/lib/utils";

const SEGMENT_LABELS: Record<string, string> = {
  explorer: "Context Explorer",
  documents: "Documents",
  graph: "Relationship Graph",
  heatmaps: "Heatmaps",
  packets: "Context Packets",
  "agent-runs": "Agent Runs",
  evals: "Evals",
  sources: "Sources",
  conflicts: "Conflicts",
  "context-debt": "Context Debt",
  feedback: "Feedback",
  admin: "Settings",
};

function labelFor(segment: string): string {
  const known = SEGMENT_LABELS[segment];
  if (known) return known;
  // UUIDs / opaque ids — truncate for display.
  if (segment.length > 12) return `${segment.slice(0, 8)}…`;
  return segment;
}

interface BreadcrumbsProps {
  className?: string;
}

/** Breadcrumb trail derived from the current pathname. Hidden on "/". */
function Breadcrumbs({ className }: BreadcrumbsProps) {
  const { pathname } = useLocation();
  const segments = pathname.split("/").filter(Boolean);
  if (segments.length === 0) return null;

  return (
    <nav aria-label="Breadcrumb" className={className}>
      <ol className="flex flex-wrap items-center gap-1 text-xs text-muted-foreground">
        <li>
          <Link
            to="/"
            className="rounded-sm transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            Dashboard
          </Link>
        </li>
        {segments.map((segment, index) => {
          const href = `/${segments.slice(0, index + 1).join("/")}`;
          const isLast = index === segments.length - 1;
          return (
            <Fragment key={href}>
              <li aria-hidden="true">
                <ChevronRight className="size-3" />
              </li>
              <li>
                {isLast ? (
                  <span aria-current="page" className={cn("text-foreground")}>
                    {labelFor(segment)}
                  </span>
                ) : (
                  <Link
                    to={href}
                    className="rounded-sm transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  >
                    {labelFor(segment)}
                  </Link>
                )}
              </li>
            </Fragment>
          );
        })}
      </ol>
    </nav>
  );
}

export { Breadcrumbs };

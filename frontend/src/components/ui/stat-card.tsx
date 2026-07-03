import { ArrowDownRight, ArrowUpRight, type LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

interface StatCardProps {
  label: string;
  value: ReactNode;
  /** Optional delta (e.g. +0.12 or -3): rendered green up / red down. */
  delta?: number;
  /** Extra context under the value (e.g. "vs last 30 days"). */
  hint?: string;
  icon?: LucideIcon;
  loading?: boolean;
  className?: string;
}

/** Compact dashboard KPI card with a loading skeleton variant. */
function StatCard({
  label,
  value,
  delta,
  hint,
  icon: Icon,
  loading = false,
  className,
}: StatCardProps) {
  if (loading) {
    return (
      <Card className={cn("p-4", className)}>
        <Skeleton className="h-3 w-20" />
        <Skeleton className="mt-2.5 h-6 w-16" />
        <Skeleton className="mt-2 h-3 w-24" />
      </Card>
    );
  }

  const showDelta = delta !== undefined && delta !== 0;
  const positive = (delta ?? 0) > 0;

  return (
    <Card className={cn("p-4", className)}>
      <div className="flex items-center justify-between gap-2">
        <p className="truncate text-xs font-medium text-muted-foreground">
          {label}
        </p>
        {Icon ? (
          <Icon className="size-4 shrink-0 text-muted-foreground/70" aria-hidden="true" />
        ) : null}
      </div>
      <p className="mt-1.5 text-2xl font-semibold tabular-nums tracking-tight">
        {value}
      </p>
      {(showDelta || hint) && (
        <p className="mt-1 flex items-center gap-1 text-xs text-muted-foreground">
          {showDelta ? (
            <span
              className={cn(
                "inline-flex items-center gap-0.5 font-medium tabular-nums",
                positive
                  ? "text-emerald-600 dark:text-emerald-400"
                  : "text-red-600 dark:text-red-400",
              )}
            >
              {positive ? (
                <ArrowUpRight className="size-3" aria-hidden="true" />
              ) : (
                <ArrowDownRight className="size-3" aria-hidden="true" />
              )}
              {positive ? "+" : ""}
              {delta}
            </span>
          ) : null}
          {hint ? <span>{hint}</span> : null}
        </p>
      )}
    </Card>
  );
}

export { StatCard };

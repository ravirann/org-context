import { cn } from "@/lib/utils";

interface ScoreBadgeProps {
  /** A 0–1 score (confidence, freshness, authority, eval, ...). */
  score: number | null | undefined;
  className?: string;
}

function scoreBadgeClasses(score: number): string {
  if (score >= 0.8)
    return "bg-emerald-500/12 text-emerald-700 dark:text-emerald-400";
  if (score >= 0.5) return "bg-amber-500/15 text-amber-700 dark:text-amber-400";
  return "bg-red-500/12 text-red-700 dark:text-red-400";
}

/** Colored badge for a 0–1 score: green >= 0.8, amber >= 0.5, red below. */
function ScoreBadge({ score, className }: ScoreBadgeProps) {
  const base =
    "inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium tabular-nums leading-4";
  if (score === null || score === undefined || Number.isNaN(score)) {
    return (
      <span className={cn(base, "bg-muted text-muted-foreground", className)}>
        —
      </span>
    );
  }
  return (
    <span className={cn(base, scoreBadgeClasses(score), className)}>
      {score.toFixed(2)}
    </span>
  );
}

export { ScoreBadge };

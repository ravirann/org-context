import { AlertTriangle } from "lucide-react";

import { Badge } from "@/components/ui/badge";

/** Destructive alert banner listing tasks that regressed vs the baseline. */
function RegressionBanner({ taskNames }: { taskNames: string[] }) {
  return (
    <div
      role="alert"
      data-testid="regression-banner"
      className="mb-3 flex items-start gap-2.5 rounded-lg border border-destructive/40 bg-destructive/8 px-3 py-2.5"
    >
      <AlertTriangle
        className="mt-0.5 size-4 shrink-0 text-destructive"
        aria-hidden="true"
      />
      <div className="min-w-0">
        <p className="text-sm font-medium text-destructive">
          Regression detected
        </p>
        <p className="mt-0.5 text-xs text-muted-foreground">
          {taskNames.length > 0
            ? "The following golden tasks scored below the baseline:"
            : "This run scored below the baseline."}
        </p>
        {taskNames.length > 0 ? (
          <div className="mt-1.5 flex flex-wrap gap-1">
            {taskNames.map((name) => (
              <Badge key={name} variant="destructive">
                {name}
              </Badge>
            ))}
          </div>
        ) : null}
      </div>
    </div>
  );
}

export { RegressionBanner };

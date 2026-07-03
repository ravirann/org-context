import { CheckCircle2 } from "lucide-react";
import type { ReactNode } from "react";

import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { cn } from "@/lib/utils";

interface DebtCardProps {
  /** Anchor id — the card is linkable as `#<id>`. */
  id: string;
  title: string;
  description?: string;
  /** Item count shown as a small badge next to the title. */
  count?: number;
  /** Render the sober "None found" mini-state instead of children. */
  isEmpty: boolean;
  emptyLabel?: string;
  /** Right-aligned header slot (e.g. chart/table toggle). */
  actions?: ReactNode;
  className?: string;
  children: ReactNode;
}

/** Dashboard card for one context-debt signal, with anchor + empty state. */
function DebtCard({
  id,
  title,
  description,
  count,
  isEmpty,
  emptyLabel = "None found",
  actions,
  className,
  children,
}: DebtCardProps) {
  return (
    <Card id={id} className={cn("scroll-mt-20", className)}>
      <CardHeader className="flex-row items-start justify-between gap-2 space-y-0">
        <div className="min-w-0">
          <CardTitle className="flex items-center gap-1.5">
            <a href={`#${id}`} className="hover:underline">
              {title}
            </a>
            {count !== undefined && count > 0 ? (
              <Badge variant="muted" className="tabular-nums">
                {count}
              </Badge>
            ) : null}
          </CardTitle>
          {description ? (
            <CardDescription className="mt-1">{description}</CardDescription>
          ) : null}
        </div>
        {actions ? <div className="flex shrink-0 items-center gap-1">{actions}</div> : null}
      </CardHeader>
      <CardContent>
        {isEmpty ? (
          <p className="flex items-center gap-1.5 rounded-md border border-dashed px-3 py-4 text-xs text-muted-foreground">
            <CheckCircle2
              className="size-3.5 text-emerald-600 dark:text-emerald-400"
              aria-hidden="true"
            />
            {emptyLabel}
          </p>
        ) : (
          children
        )}
      </CardContent>
    </Card>
  );
}

export { DebtCard };

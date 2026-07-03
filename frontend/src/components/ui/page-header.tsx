import type { ReactNode } from "react";

import { Breadcrumbs } from "@/components/layout/breadcrumbs";
import { cn } from "@/lib/utils";

interface PageHeaderProps {
  title: string;
  description?: string;
  /**
   * Breadcrumbs slot. Defaults to auto-generated <Breadcrumbs /> derived from
   * the current route. Pass `null` to hide entirely.
   */
  breadcrumbs?: ReactNode;
  /** Right-aligned actions slot (buttons, filters, ...). */
  actions?: ReactNode;
  className?: string;
}

/** Standard page heading — every page starts with one of these. */
function PageHeader({
  title,
  description,
  breadcrumbs,
  actions,
  className,
}: PageHeaderProps) {
  return (
    <header className={cn("mb-4 flex flex-col gap-1.5", className)}>
      {breadcrumbs === undefined ? <Breadcrumbs /> : breadcrumbs}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="min-w-0">
          <h1 className="truncate text-lg font-semibold tracking-tight">
            {title}
          </h1>
          {description ? (
            <p className="mt-0.5 text-xs text-muted-foreground">{description}</p>
          ) : null}
        </div>
        {actions ? (
          <div className="flex shrink-0 items-center gap-2">{actions}</div>
        ) : null}
      </div>
    </header>
  );
}

export { PageHeader };

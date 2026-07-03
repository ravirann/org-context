import { Compass, LayoutDashboard, Search } from "lucide-react";
import { Link } from "react-router-dom";

import { buttonVariants } from "@/components/ui/button";
import { PageHeader } from "@/components/ui/page-header";
import { usePageTitle } from "@/hooks/use-page-title";

export default function NotFoundPage() {
  usePageTitle("Not Found");
  return (
    <>
      <PageHeader title="Page not found" breadcrumbs={null} />
      <div data-testid="page-not-found">
        <div className="flex flex-col items-center justify-center gap-3 rounded-lg border border-dashed px-6 py-16 text-center">
          <Compass className="size-10 text-muted-foreground/50" aria-hidden="true" />
          <p className="font-mono text-3xl font-semibold tracking-tight text-muted-foreground">
            404
          </p>
          <p className="text-sm font-medium">This page does not exist</p>
          <p className="max-w-sm text-xs text-muted-foreground">
            The link may be stale, or the resource may have been removed. If a document
            vanished, its source may have been disconnected.
          </p>
          <div className="mt-2 flex flex-wrap items-center justify-center gap-2">
            <Link to="/" className={buttonVariants({ size: "sm" })}>
              <LayoutDashboard aria-hidden="true" />
              Back to dashboard
            </Link>
            <Link
              to="/explorer"
              className={buttonVariants({ variant: "outline", size: "sm" })}
            >
              <Search aria-hidden="true" />
              Search the explorer
            </Link>
          </div>
        </div>
      </div>
    </>
  );
}

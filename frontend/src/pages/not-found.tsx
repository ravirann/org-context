// PLACEHOLDER — replaced by a page-group agent. Keep the PageHeader +
// data-testid contract documented in components/layout/app-shell.tsx.
import { Link } from "react-router-dom";

import { buttonVariants } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";
import { usePageTitle } from "@/hooks/use-page-title";

export default function NotFoundPage() {
  usePageTitle("Not Found");
  return (
    <>
      <PageHeader title="Page not found" breadcrumbs={null} />
      <div data-testid="page-not-found">
        <EmptyState
          title="404 — this page does not exist"
          description="The link may be stale, or the resource may have been removed."
          action={
            <Link to="/" className={buttonVariants({ variant: "outline", size: "sm" })}>
              Back to dashboard
            </Link>
          }
        />
      </div>
    </>
  );
}

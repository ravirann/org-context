// PLACEHOLDER — replaced by a page-group agent. Keep the PageHeader +
// data-testid contract documented in components/layout/app-shell.tsx.
import { PageHeader } from "@/components/ui/page-header";
import { usePageTitle } from "@/hooks/use-page-title";

export default function SourcesPage() {
  usePageTitle("Sources");
  return (
    <>
      <PageHeader title="Sources" />
      <div data-testid="page-sources" />
    </>
  );
}

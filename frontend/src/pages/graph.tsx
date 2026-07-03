// PLACEHOLDER — replaced by a page-group agent. Keep the PageHeader +
// data-testid contract documented in components/layout/app-shell.tsx.
import { PageHeader } from "@/components/ui/page-header";
import { usePageTitle } from "@/hooks/use-page-title";

export default function GraphPage() {
  usePageTitle("Relationship Graph");
  return (
    <>
      <PageHeader title="Relationship Graph" />
      <div data-testid="page-graph" />
    </>
  );
}

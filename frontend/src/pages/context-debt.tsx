// PLACEHOLDER — replaced by a page-group agent. Keep the PageHeader +
// data-testid contract documented in components/layout/app-shell.tsx.
import { PageHeader } from "@/components/ui/page-header";
import { usePageTitle } from "@/hooks/use-page-title";

export default function ContextDebtPage() {
  usePageTitle("Context Debt");
  return (
    <>
      <PageHeader title="Context Debt" />
      <div data-testid="page-context-debt" />
    </>
  );
}

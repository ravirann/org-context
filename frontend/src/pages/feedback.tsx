// PLACEHOLDER — replaced by a page-group agent. Keep the PageHeader +
// data-testid contract documented in components/layout/app-shell.tsx.
import { PageHeader } from "@/components/ui/page-header";
import { usePageTitle } from "@/hooks/use-page-title";

export default function FeedbackPage() {
  usePageTitle("Feedback");
  return (
    <>
      <PageHeader title="Feedback" />
      <div data-testid="page-feedback" />
    </>
  );
}

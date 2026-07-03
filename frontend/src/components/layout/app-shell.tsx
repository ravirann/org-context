/**
 * AppShell — the application layout every page renders inside (via <Outlet/>).
 *
 * ============================================================================
 * CONTRACT FOR PAGE AGENTS (src/pages/**) — rely ONLY on the APIs below.
 * ============================================================================
 *
 * Layout guarantees
 * -----------------
 * - Pages render inside <main> which already provides `p-4 md:p-6`, vertical
 *   scrolling and `min-w-0`. Do NOT add your own outer page padding.
 * - The left sidebar collapses to an icon rail below 1024px and becomes a
 *   slide-over sheet below 768px — pages never manage the sidebar.
 * - Default export a component from each page file; routes are wired in
 *   src/App.tsx (AppRoutes). Detail pages read params via useParams().
 *
 * Page skeleton every page should follow
 * --------------------------------------
 *   import { PageHeader } from "@/components/ui/page-header";
 *
 *   export default function MyPage() {
 *     return (
 *       <>
 *         <PageHeader title="My Page" description="..." actions={<Button/>} />
 *         <div data-testid="page-my-page">...content...</div>
 *       </>
 *     );
 *   }
 *
 * PageHeader props: { title: string; description?: string;
 *   breadcrumbs?: ReactNode (default: auto <Breadcrumbs/>, pass null to hide);
 *   actions?: ReactNode; className?: string }
 *
 * Data fetching
 * -------------
 * - import { api, ApiError, isApiError } from "@/lib/api";
 *     api.get<T>(path, params?) · api.post<T>(path, body?, params?)
 *     api.patch<T>(path, body?) · api.delete(path)
 *   ApiError has { status: number, detail: string }.
 * - import { queryKeys } from "@/lib/queryKeys";  (always use the factory)
 * - import type { ... } from "@/lib/types";       (mirrors API_CONTRACT.md)
 * - React Query defaults: retry 1, staleTime 30s (set in App.tsx).
 *
 * Required page states (CONVENTIONS.md)
 * -------------------------------------
 * - loading  → <Skeleton/> (or StatCard loading / your own skeleton grid)
 * - error    → <ErrorState message={...} onRetry={() => refetch()} />
 * - empty    → <EmptyState title="..." description="..." action={...} />
 * - 403      → <PermissionDenied role={me?.role} /> (isApiError(e) && e.status === 403)
 * All in "@/components/ui/...".
 *
 * UI kit ("@/components/ui/*")
 * ----------------------------
 * button (Button, buttonVariants) · card (Card, CardHeader, CardTitle,
 * CardDescription, CardContent, CardFooter) · badge (Badge: default|secondary|
 * outline|destructive|success|warning|muted) · input · textarea · select
 * (styled native <select>) · dialog (controlled: open/onOpenChange; Escape and
 * overlay click close) · dropdown-menu · tabs · tooltip (content prop) · table
 * (Table, TableHeader, TableBody, TableRow, TableHead, TableCell, ...) ·
 * skeleton · spinner · separator · scroll-area · kbd · empty-state ·
 * error-state · permission-denied · page-header · stat-card (label, value,
 * delta?, hint?, icon?, loading?) · score-badge (score: 0..1 | null).
 *
 * Toasts: import { useToast } from "@/components/ui/toast";
 *   const { toast } = useToast();
 *   toast({ title, description?, variant: "success" | "error" | "info" });
 *
 * Hooks: useMe() (@/hooks/use-me) · useDebounce(value, ms?) ·
 * usePageTitle(title) (@/hooks/use-page-title — call it in every page).
 * Utils (@/lib/utils): cn, formatDate, formatDateTime, formatNumber,
 * timeAgo(iso, now?), scoreColor(score).
 *
 * Tests (frontend/tests/utils.tsx)
 * --------------------------------
 *   renderWithProviders(<MyPage/>, { route: "/packets/abc" , path: "/packets/:id" })
 *   mockFetchRoutes({ "GET /v1/context-packets": paginated, ... })
 *   mockFetchOnce(data, { status: 200 })  ·  mockResponse(body, status)
 * ============================================================================
 */
import { useEffect, useState } from "react";
import { Outlet, useLocation } from "react-router-dom";

import { Sidebar } from "@/components/layout/sidebar";
import { Topbar } from "@/components/layout/topbar";

function AppShell() {
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const { pathname } = useLocation();

  // Close the mobile sheet on navigation and on Escape.
  useEffect(() => {
    setMobileNavOpen(false);
  }, [pathname]);

  useEffect(() => {
    if (!mobileNavOpen) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setMobileNavOpen(false);
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [mobileNavOpen]);

  return (
    <div className="flex h-screen w-full overflow-hidden bg-background text-foreground">
      {/* Desktop / tablet sidebar: icon rail below lg, full at lg+ */}
      <aside className="hidden w-14 shrink-0 border-r border-sidebar-border md:block lg:w-56">
        <Sidebar variant="responsive" />
      </aside>

      {/* Mobile slide-over sheet */}
      {mobileNavOpen ? (
        <div className="fixed inset-0 z-50 md:hidden">
          <div
            className="fixed inset-0 bg-black/50"
            aria-hidden="true"
            data-testid="mobile-nav-overlay"
            onClick={() => setMobileNavOpen(false)}
          />
          <aside className="fixed inset-y-0 left-0 w-64 border-r border-sidebar-border bg-sidebar shadow-lg">
            <Sidebar variant="full" onNavigate={() => setMobileNavOpen(false)} />
          </aside>
        </div>
      ) : null}

      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar onMenuClick={() => setMobileNavOpen(true)} />
        <main className="scroll-area min-w-0 flex-1 overflow-y-auto p-4 md:p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

export { AppShell };

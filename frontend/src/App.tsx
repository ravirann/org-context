import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";
import { Route, Routes } from "react-router-dom";

import { AppShell } from "@/components/layout/app-shell";
import { Spinner } from "@/components/ui/spinner";
import { Toaster } from "@/components/ui/toast";
import { useAuthSession } from "@/hooks/use-auth-session";
import AdminPage from "@/pages/admin";
import AgentRunDetailPage from "@/pages/agent-run-detail";
import AgentRunsPage from "@/pages/agent-runs";
import ConflictDetailPage from "@/pages/conflict-detail";
import ConflictsPage from "@/pages/conflicts";
import ContextDebtPage from "@/pages/context-debt";
import DashboardPage from "@/pages/dashboard";
import DocumentDetailPage from "@/pages/document-detail";
import EvalDetailPage from "@/pages/eval-detail";
import EvalsPage from "@/pages/evals";
import ExplorerPage from "@/pages/explorer";
import FeedbackPage from "@/pages/feedback";
import GraphPage from "@/pages/graph";
import HeatmapsPage from "@/pages/heatmaps";
import LoginPage from "@/pages/login";
import NotFoundPage from "@/pages/not-found";
import PacketDetailPage from "@/pages/packet-detail";
import PacketsPage from "@/pages/packets";
import SourcesPage from "@/pages/sources";

export function AppProviders({ children }: { children: ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            retry: 1,
            staleTime: 30_000,
            refetchOnWindowFocus: false,
          },
        },
      }),
  );
  return (
    <QueryClientProvider client={queryClient}>
      {children}
      <Toaster />
    </QueryClientProvider>
  );
}

/**
 * Auth gate: bootstraps from GET /v1/auth/session (see useAuthSession).
 * - loading  → centered spinner (no route content mounts yet)
 * - oidc mode, unauthenticated → LoginPage for every path (mirrors /login)
 * - otherwise (demo mode, or oidc mode authenticated) → normal shell + routes
 */
export function AppRoutes() {
  const sessionQuery = useAuthSession();

  if (sessionQuery.isPending) {
    return (
      <div
        className="flex min-h-screen w-full items-center justify-center"
        data-testid="auth-bootstrap-loading"
      >
        <Spinner label="Loading session" />
      </div>
    );
  }

  const session = sessionQuery.data;
  const gateToLogin =
    !sessionQuery.isError && session?.auth_mode === "oidc" && !session.authenticated;

  if (gateToLogin) {
    return (
      <Routes>
        <Route path="*" element={<LoginPage />} />
      </Routes>
    );
  }

  return (
    <Routes>
      <Route path="login" element={<LoginPage />} />
      <Route element={<AppShell />}>
        <Route index element={<DashboardPage />} />
        <Route path="explorer" element={<ExplorerPage />} />
        <Route path="explorer/documents/:id" element={<DocumentDetailPage />} />
        <Route path="graph" element={<GraphPage />} />
        <Route path="heatmaps" element={<HeatmapsPage />} />
        <Route path="packets" element={<PacketsPage />} />
        <Route path="packets/:id" element={<PacketDetailPage />} />
        <Route path="agent-runs" element={<AgentRunsPage />} />
        <Route path="agent-runs/:id" element={<AgentRunDetailPage />} />
        <Route path="evals" element={<EvalsPage />} />
        <Route path="evals/:id" element={<EvalDetailPage />} />
        <Route path="sources" element={<SourcesPage />} />
        <Route path="conflicts" element={<ConflictsPage />} />
        <Route path="conflicts/:id" element={<ConflictDetailPage />} />
        <Route path="context-debt" element={<ContextDebtPage />} />
        <Route path="feedback" element={<FeedbackPage />} />
        <Route path="admin" element={<AdminPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}

export default function App() {
  return (
    <AppProviders>
      <AppRoutes />
    </AppProviders>
  );
}

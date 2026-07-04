import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import { queryKeys } from "@/lib/queryKeys";
import type { AuthSession } from "@/lib/types";

/**
 * Bootstraps auth mode + session state from GET /v1/auth/session. Never
 * stale (staleTime Infinity) — invalidate this query explicitly after
 * login/logout. App.tsx gates routing on the result.
 */
export function useAuthSession() {
  return useQuery({
    queryKey: queryKeys.authSession(),
    queryFn: () => api.get<AuthSession>("/v1/auth/session"),
    staleTime: Infinity,
    retry: 1,
    // App.tsx is the sole place that should drive (re)fetching this query;
    // other consumers (e.g. Topbar) just read the cached result. Without
    // these two flags, a fresh observer mounting while the query is in an
    // error state (e.g. Topbar mounting inside the shell branch after the
    // gate gives up on retries) retries the fetch from scratch, which can
    // bounce the gate between the loading and shell branches forever.
    refetchOnMount: false,
    retryOnMount: false,
  });
}

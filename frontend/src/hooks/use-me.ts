import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import { queryKeys } from "@/lib/queryKeys";
import type { Me } from "@/lib/types";
import { useAuthStore } from "@/stores/auth";

/**
 * Current user (GET /v1/me) — drives RBAC states in the UI. The query key
 * includes the active API key so switching keys refetches automatically.
 */
export function useMe() {
  const apiKey = useAuthStore((s) => s.apiKey);
  return useQuery({
    queryKey: queryKeys.me(apiKey),
    queryFn: () => api.get<Me>("/v1/me"),
    staleTime: 5 * 60 * 1000,
  });
}

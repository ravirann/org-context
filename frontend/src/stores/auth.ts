import { create } from "zustand";
import { persist } from "zustand/middleware";

/**
 * API key auth store. The key is sent as `Authorization: Bearer <key>` by
 * src/lib/api.ts. Default is the seeded demo admin key; the topbar switcher
 * lets you swap keys (and therefore roles) at runtime.
 */
export const DEFAULT_API_KEY = "demo-admin-key";

interface AuthState {
  apiKey: string;
  setApiKey: (apiKey: string) => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      apiKey: DEFAULT_API_KEY,
      setApiKey: (apiKey) => set({ apiKey: apiKey.trim() || DEFAULT_API_KEY }),
    }),
    { name: "org-context-auth" },
  ),
);

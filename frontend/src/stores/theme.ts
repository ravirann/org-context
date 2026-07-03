import { create } from "zustand";
import { persist } from "zustand/middleware";

export type Theme = "light" | "dark" | "system";
export type ResolvedTheme = "light" | "dark";

function systemPrefersDark(): boolean {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
    return false;
  }
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

function resolve(theme: Theme): ResolvedTheme {
  if (theme === "system") return systemPrefersDark() ? "dark" : "light";
  return theme;
}

function applyToDocument(resolved: ResolvedTheme): void {
  if (typeof document === "undefined") return;
  document.documentElement.classList.toggle("dark", resolved === "dark");
}

interface ThemeState {
  theme: Theme;
  resolvedTheme: ResolvedTheme;
  setTheme: (theme: Theme) => void;
  /** Cycles light <-> dark based on the currently resolved theme. */
  toggleTheme: () => void;
}

export const useThemeStore = create<ThemeState>()(
  persist(
    (set, get) => ({
      theme: "system",
      resolvedTheme: resolve("system"),
      setTheme: (theme) => {
        const resolvedTheme = resolve(theme);
        applyToDocument(resolvedTheme);
        set({ theme, resolvedTheme });
      },
      toggleTheme: () => {
        get().setTheme(get().resolvedTheme === "dark" ? "light" : "dark");
      },
    }),
    {
      name: "org-context-theme",
      partialize: (state) => ({ theme: state.theme }),
      onRehydrateStorage: () => (state) => {
        if (state) state.setTheme(state.theme);
      },
    },
  ),
);

// Track OS-level scheme changes while in "system" mode.
if (typeof window !== "undefined" && typeof window.matchMedia === "function") {
  const media = window.matchMedia("(prefers-color-scheme: dark)");
  const listener = () => {
    const { theme, setTheme } = useThemeStore.getState();
    if (theme === "system") setTheme("system");
  };
  if (typeof media.addEventListener === "function") {
    media.addEventListener("change", listener);
  }
}

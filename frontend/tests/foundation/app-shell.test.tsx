import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";

import { AppRoutes } from "@/App";
import { useThemeStore } from "@/stores/theme";
import type { AuthSession, Me } from "@/lib/types";

import { mockFetchRoutes, renderWithProviders } from "../utils";

const ME: Me = {
  id: "u1",
  email: "admin@demo.org",
  name: "Demo Admin",
  role: "admin",
  team_name: "Platform",
};

const DEMO_SESSION: AuthSession = { auth_mode: "demo", authenticated: true, user: ME };

describe("AppShell", () => {
  beforeEach(() => {
    useThemeStore.setState({ theme: "light", resolvedTheme: "light" });
    document.documentElement.classList.remove("dark");
    mockFetchRoutes({ "GET /v1/me": ME, "GET /v1/auth/session": DEMO_SESSION });
  });

  it("renders all sidebar navigation sections and links", async () => {
    renderWithProviders(<AppRoutes />, { route: "/" });

    const nav = await screen.findByRole("navigation", { name: "Primary" });
    for (const label of [
      "Dashboard",
      "Context Explorer",
      "Relationship Graph",
      "Heatmaps",
      "Packets",
      "Agent Runs",
      "Evals",
      "Conflicts",
      "Context Debt",
      "Feedback",
      "Sources",
      "Settings",
    ]) {
      expect(within(nav).getByRole("link", { name: label })).toBeInTheDocument();
    }
    // Dashboard page placeholder mounted in <main>
    expect(screen.getByTestId("page-dashboard")).toBeInTheDocument();
  });

  it("navigates between pages via sidebar links", async () => {
    const user = userEvent.setup();
    renderWithProviders(<AppRoutes />, { route: "/" });

    await user.click(await screen.findByRole("link", { name: "Packets" }));
    expect(screen.getByTestId("page-packets")).toBeInTheDocument();

    await user.click(screen.getByRole("link", { name: "Settings" }));
    expect(screen.getByTestId("page-admin")).toBeInTheDocument();
  });

  it("renders the not-found page for unknown routes", async () => {
    renderWithProviders(<AppRoutes />, { route: "/nope/does-not-exist" });
    expect(await screen.findByTestId("page-not-found")).toBeInTheDocument();
  });

  it("toggles the dark theme class on <html>", async () => {
    const user = userEvent.setup();
    renderWithProviders(<AppRoutes />, { route: "/" });

    expect(document.documentElement.classList.contains("dark")).toBe(false);
    await user.click(await screen.findByRole("button", { name: "Toggle theme" }));
    expect(document.documentElement.classList.contains("dark")).toBe(true);
    expect(useThemeStore.getState().resolvedTheme).toBe("dark");

    await user.click(screen.getByRole("button", { name: "Toggle theme" }));
    expect(document.documentElement.classList.contains("dark")).toBe(false);
  });

  it("shows the current user and role from /v1/me in the topbar", async () => {
    renderWithProviders(<AppRoutes />, { route: "/" });
    expect(await screen.findByText("Demo Admin")).toBeInTheDocument();
    expect(screen.getByText("admin")).toBeInTheDocument();
  });

  it("global search navigates to /explorer?q=…", async () => {
    const user = userEvent.setup();
    renderWithProviders(<AppRoutes />, { route: "/" });

    const input = await screen.findByRole("searchbox", { name: "Global search" });
    await user.type(input, "auth flow{Enter}");
    expect(screen.getByTestId("page-explorer")).toBeInTheDocument();
  });
});

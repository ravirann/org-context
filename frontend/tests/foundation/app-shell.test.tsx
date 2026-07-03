import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";

import { AppRoutes } from "@/App";
import { useThemeStore } from "@/stores/theme";
import type { Me } from "@/lib/types";

import { mockFetchRoutes, renderWithProviders } from "../utils";

const ME: Me = {
  id: "u1",
  email: "admin@demo.org",
  name: "Demo Admin",
  role: "admin",
  team_name: "Platform",
};

describe("AppShell", () => {
  beforeEach(() => {
    useThemeStore.setState({ theme: "light", resolvedTheme: "light" });
    document.documentElement.classList.remove("dark");
    mockFetchRoutes({ "GET /v1/me": ME });
  });

  it("renders all sidebar navigation sections and links", () => {
    renderWithProviders(<AppRoutes />, { route: "/" });

    const nav = screen.getByRole("navigation", { name: "Primary" });
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

    await user.click(screen.getByRole("link", { name: "Packets" }));
    expect(screen.getByTestId("page-packets")).toBeInTheDocument();

    await user.click(screen.getByRole("link", { name: "Settings" }));
    expect(screen.getByTestId("page-admin")).toBeInTheDocument();
  });

  it("renders the not-found page for unknown routes", () => {
    renderWithProviders(<AppRoutes />, { route: "/nope/does-not-exist" });
    expect(screen.getByTestId("page-not-found")).toBeInTheDocument();
  });

  it("toggles the dark theme class on <html>", async () => {
    const user = userEvent.setup();
    renderWithProviders(<AppRoutes />, { route: "/" });

    expect(document.documentElement.classList.contains("dark")).toBe(false);
    await user.click(screen.getByRole("button", { name: "Toggle theme" }));
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

    const input = screen.getByRole("searchbox", { name: "Global search" });
    await user.type(input, "auth flow{Enter}");
    expect(screen.getByTestId("page-explorer")).toBeInTheDocument();
  });
});

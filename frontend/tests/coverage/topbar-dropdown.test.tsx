/**
 * Behavioral coverage for Topbar (src/components/layout/topbar.tsx) and the
 * hand-rolled DropdownMenu it uses (src/components/ui/dropdown-menu.tsx):
 * open/close, outside click, Escape, arrow-key navigation, item selection,
 * search submit, Cmd+K focus, theme toggle and the custom-key form.
 */
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { AppRoutes } from "@/App";
import type { AuthSession, Me } from "@/lib/types";
import { DEFAULT_API_KEY, useAuthStore } from "@/stores/auth";
import { useThemeStore } from "@/stores/theme";

import { mockFetchRoutes, renderWithProviders } from "../utils";

const ME: Me = {
  id: "u1",
  email: "admin@demo.org",
  name: "Demo Admin",
  role: "admin",
  team_name: "Platform",
};

const DEMO_SESSION: AuthSession = { auth_mode: "demo", authenticated: true, user: ME };

describe("Topbar + DropdownMenu", () => {
  it("opens the API key dropdown, navigates with arrow keys, and Escape closes it", async () => {
    useAuthStore.setState({ apiKey: DEFAULT_API_KEY });
    mockFetchRoutes({ "GET /v1/me": ME, "GET /v1/auth/session": DEMO_SESSION });
    const user = userEvent.setup();
    renderWithProviders(<AppRoutes />, { route: "/" });

    const trigger = await screen.findByRole("button", { name: "Switch API key" });
    expect(trigger).toHaveAttribute("aria-expanded", "false");

    await user.click(trigger);
    expect(trigger).toHaveAttribute("aria-expanded", "true");
    const menu = screen.getByRole("menu");
    expect(menu).toBeInTheDocument();

    const items = screen.getAllByRole("menuitem");
    expect(items.length).toBeGreaterThanOrEqual(4);

    items[0].focus();
    await user.keyboard("{ArrowDown}");
    expect(document.activeElement).toBe(items[1]);
    await user.keyboard("{ArrowUp}");
    expect(document.activeElement).toBe(items[0]);
    // Wraps around from the first item.
    await user.keyboard("{ArrowUp}");
    expect(document.activeElement).toBe(items[items.length - 1]);

    await user.keyboard("{Escape}");
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
  });

  it("selects a demo key from the dropdown and marks it active", async () => {
    useAuthStore.setState({ apiKey: DEFAULT_API_KEY });
    mockFetchRoutes({ "GET /v1/me": ME, "GET /v1/auth/session": DEMO_SESSION });
    const user = userEvent.setup();
    renderWithProviders(<AppRoutes />, { route: "/" });

    await screen.findByRole("button", { name: "Switch API key" });
    await user.click(screen.getByRole("button", { name: "Switch API key" }));

    await user.click(screen.getByRole("menuitem", { name: /Lead/ }));

    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
    expect(useAuthStore.getState().apiKey).toBe("demo-lead-key");
  });

  it("submits a custom API key via the dropdown form", async () => {
    useAuthStore.setState({ apiKey: DEFAULT_API_KEY });
    mockFetchRoutes({ "GET /v1/me": ME, "GET /v1/auth/session": DEMO_SESSION });
    const user = userEvent.setup();
    renderWithProviders(<AppRoutes />, { route: "/" });

    await user.click(await screen.findByRole("button", { name: "Switch API key" }));
    const customInput = screen.getByLabelText("Custom API key");
    await user.type(customInput, "my-custom-key{Enter}");

    expect(useAuthStore.getState().apiKey).toBe("my-custom-key");
  });

  it("closes the dropdown on outside click", async () => {
    useAuthStore.setState({ apiKey: DEFAULT_API_KEY });
    mockFetchRoutes({ "GET /v1/me": ME, "GET /v1/auth/session": DEMO_SESSION });
    const user = userEvent.setup();
    renderWithProviders(<AppRoutes />, { route: "/" });

    await user.click(await screen.findByRole("button", { name: "Switch API key" }));
    expect(screen.getByRole("menu")).toBeInTheDocument();

    await user.click(document.body);
    await waitFor(() => {
      expect(screen.queryByRole("menu")).not.toBeInTheDocument();
    });
  });

  it("submits the global search and navigates to /explorer", async () => {
    mockFetchRoutes({ "GET /v1/me": ME, "GET /v1/auth/session": DEMO_SESSION });
    const user = userEvent.setup();
    renderWithProviders(<AppRoutes />, { route: "/" });

    const input = await screen.findByRole("searchbox", { name: "Global search" });
    await user.type(input, "retry backoff{Enter}");
    expect(screen.getByTestId("page-explorer")).toBeInTheDocument();
  });

  it("does not navigate when submitting an empty search", async () => {
    mockFetchRoutes({ "GET /v1/me": ME, "GET /v1/auth/session": DEMO_SESSION });
    const user = userEvent.setup();
    renderWithProviders(<AppRoutes />, { route: "/" });

    const input = await screen.findByRole("searchbox", { name: "Global search" });
    await user.type(input, "   {Enter}");
    expect(screen.getByTestId("page-dashboard")).toBeInTheDocument();
  });

  it("focuses global search on Cmd+K", async () => {
    mockFetchRoutes({ "GET /v1/me": ME, "GET /v1/auth/session": DEMO_SESSION });
    const user = userEvent.setup();
    renderWithProviders(<AppRoutes />, { route: "/" });

    const input = await screen.findByRole("searchbox", { name: "Global search" });
    input.blur();
    expect(input).not.toHaveFocus();

    await user.keyboard("{Meta>}k{/Meta}");
    expect(input).toHaveFocus();
  });

  it("toggles the theme via the topbar button", async () => {
    useThemeStore.setState({ theme: "light", resolvedTheme: "light" });
    document.documentElement.classList.remove("dark");
    mockFetchRoutes({ "GET /v1/me": ME, "GET /v1/auth/session": DEMO_SESSION });
    const user = userEvent.setup();
    renderWithProviders(<AppRoutes />, { route: "/" });

    const toggle = await screen.findByRole("button", { name: "Toggle theme" });
    await user.click(toggle);
    expect(document.documentElement.classList.contains("dark")).toBe(true);
    await user.click(toggle);
    expect(document.documentElement.classList.contains("dark")).toBe(false);
  });

  it("shows 'Unknown user' when /v1/me has no name yet (mid-load)", async () => {
    mockFetchRoutes({
      "GET /v1/me": () => new Promise(() => {}),
      "GET /v1/auth/session": DEMO_SESSION,
    });
    renderWithProviders(<AppRoutes />, { route: "/" });
    expect(await screen.findByText("Unknown user")).toBeInTheDocument();
  });
});

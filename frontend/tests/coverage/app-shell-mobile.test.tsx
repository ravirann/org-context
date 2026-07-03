/**
 * Coverage for the mobile slide-over sheet paths in AppShell
 * (src/components/layout/app-shell.tsx): opening via the topbar menu button,
 * closing via overlay click, closing via Escape, and auto-closing on
 * navigation.
 */
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { AppRoutes } from "@/App";
import type { Me } from "@/lib/types";

import { mockFetchRoutes, renderWithProviders } from "../utils";

const ME: Me = {
  id: "u1",
  email: "admin@demo.org",
  name: "Demo Admin",
  role: "admin",
  team_name: "Platform",
};

describe("AppShell mobile sheet", () => {
  it("opens the mobile nav sheet from the topbar menu button", async () => {
    mockFetchRoutes({ "GET /v1/me": ME });
    const user = userEvent.setup();
    renderWithProviders(<AppRoutes />, { route: "/" });

    expect(screen.queryByTestId("mobile-nav-overlay")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Open navigation" }));
    expect(screen.getByTestId("mobile-nav-overlay")).toBeInTheDocument();
  });

  it("closes the mobile nav sheet on overlay click", async () => {
    mockFetchRoutes({ "GET /v1/me": ME });
    const user = userEvent.setup();
    renderWithProviders(<AppRoutes />, { route: "/" });

    await user.click(screen.getByRole("button", { name: "Open navigation" }));
    expect(screen.getByTestId("mobile-nav-overlay")).toBeInTheDocument();

    await user.click(screen.getByTestId("mobile-nav-overlay"));
    expect(screen.queryByTestId("mobile-nav-overlay")).not.toBeInTheDocument();
  });

  it("closes the mobile nav sheet on Escape", async () => {
    mockFetchRoutes({ "GET /v1/me": ME });
    const user = userEvent.setup();
    renderWithProviders(<AppRoutes />, { route: "/" });

    await user.click(screen.getByRole("button", { name: "Open navigation" }));
    expect(screen.getByTestId("mobile-nav-overlay")).toBeInTheDocument();

    await user.keyboard("{Escape}");
    expect(screen.queryByTestId("mobile-nav-overlay")).not.toBeInTheDocument();
  });

  it("closes the mobile nav sheet when a nav link is clicked (route change)", async () => {
    mockFetchRoutes({ "GET /v1/me": ME });
    const user = userEvent.setup();
    renderWithProviders(<AppRoutes />, { route: "/" });

    await user.click(screen.getByRole("button", { name: "Open navigation" }));
    expect(screen.getByTestId("mobile-nav-overlay")).toBeInTheDocument();

    // The mobile sheet renders its own full nav; use it to navigate away.
    const overlayNav = screen.getAllByRole("link", { name: "Packets" });
    await user.click(overlayNav[overlayNav.length - 1]);

    expect(screen.getByTestId("page-packets")).toBeInTheDocument();
    expect(screen.queryByTestId("mobile-nav-overlay")).not.toBeInTheDocument();
  });
});

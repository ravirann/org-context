import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AppRoutes } from "@/App";
import type { AuthSession, Me } from "@/lib/types";

import { mockFetchRoutes, mockResponse, renderWithProviders } from "../utils";

const ME: Me = {
  id: "u1",
  email: "admin@demo.org",
  name: "Demo Admin",
  role: "admin",
  team_name: "Platform",
};

describe("App auth gating (useAuthSession)", () => {
  it("shows a centered spinner while the session is loading", () => {
    mockFetchRoutes({ "GET /v1/auth/session": () => new Promise(() => {}) });
    renderWithProviders(<AppRoutes />, { route: "/" });

    expect(screen.getByTestId("auth-bootstrap-loading")).toBeInTheDocument();
    expect(screen.queryByTestId("page-dashboard")).not.toBeInTheDocument();
  });

  it("oidc mode + unauthenticated renders the login page for any path", async () => {
    const session: AuthSession = { auth_mode: "oidc", authenticated: false, user: null };
    mockFetchRoutes({ "GET /v1/auth/session": session });
    renderWithProviders(<AppRoutes />, { route: "/packets" });

    expect(await screen.findByTestId("page-login")).toBeInTheDocument();
    expect(screen.queryByTestId("page-packets")).not.toBeInTheDocument();
  });

  it("oidc mode + authenticated renders the normal shell", async () => {
    const session: AuthSession = { auth_mode: "oidc", authenticated: true, user: ME };
    mockFetchRoutes({ "GET /v1/auth/session": session, "GET /v1/me": ME });
    renderWithProviders(<AppRoutes />, { route: "/" });

    expect(await screen.findByTestId("page-dashboard")).toBeInTheDocument();
    expect(await screen.findByText("Demo Admin")).toBeInTheDocument();
    // oidc mode shows the user menu, not the demo key switcher.
    expect(screen.getByRole("button", { name: "User menu" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Switch API key" })).not.toBeInTheDocument();
  });

  it("demo mode renders the normal shell with the key switcher regardless of authenticated flag", async () => {
    const session: AuthSession = { auth_mode: "demo", authenticated: true, user: ME };
    mockFetchRoutes({ "GET /v1/auth/session": session, "GET /v1/me": ME });
    renderWithProviders(<AppRoutes />, { route: "/" });

    expect(await screen.findByTestId("page-dashboard")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Switch API key" })).toBeInTheDocument();
  });

  it("falls back to the normal shell if the session request errors", async () => {
    mockFetchRoutes({
      "GET /v1/auth/session": mockResponse({ detail: "unavailable" }, 500),
      "GET /v1/me": ME,
    });
    renderWithProviders(<AppRoutes />, { route: "/" });

    expect(
      await screen.findByTestId("page-dashboard", {}, { timeout: 5000 }),
    ).toBeInTheDocument();
  }, 10_000);
});

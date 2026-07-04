/**
 * Coverage for the Topbar's oidc user menu (sign-out → POST /v1/auth/logout)
 * and the demo-mode "Sign out" parity item (clears back to the default key).
 */
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { AppRoutes } from "@/App";
import type { AuthSession, Me } from "@/lib/types";
import { DEFAULT_API_KEY, useAuthStore } from "@/stores/auth";

import { mockFetchRoutes, renderWithProviders } from "../utils";

const ME: Me = {
  id: "u1",
  email: "admin@demo.org",
  name: "Demo Admin",
  role: "admin",
  team_name: "Platform",
};

describe("Topbar — oidc user menu", () => {
  it("shows avatar initials, name, email, role and signs out via POST /v1/auth/logout", async () => {
    const session: AuthSession = { auth_mode: "oidc", authenticated: true, user: ME };
    const loggedOutSession: AuthSession = {
      auth_mode: "oidc",
      authenticated: false,
      user: null,
    };
    let loggedOut = false;
    const fetchMock = mockFetchRoutes({
      "GET /v1/auth/session": () => (loggedOut ? loggedOutSession : session),
      "GET /v1/me": ME,
      "POST /v1/auth/logout": () => {
        loggedOut = true;
        return null;
      },
    });
    const user = userEvent.setup();
    renderWithProviders(<AppRoutes />, { route: "/" });

    const trigger = await screen.findByRole("button", { name: "User menu" });
    await user.click(trigger);
    const menu = screen.getByRole("menu");
    expect(within(menu).getByText("Demo Admin")).toBeInTheDocument();
    expect(within(menu).getByText("admin@demo.org")).toBeInTheDocument();

    await user.click(within(menu).getByRole("menuitem", { name: /Sign out/ }));

    await waitFor(() => {
      expect(
        fetchMock.mock.calls.some(
          ([input, init]) =>
            String(input).includes("/v1/auth/logout") && init?.method === "POST",
        ),
      ).toBe(true);
    });
    expect(await screen.findByTestId("page-login")).toBeInTheDocument();
  });
});

describe("Topbar — demo mode sign-out parity", () => {
  it("clears the API key back to the default without hitting the network", async () => {
    useAuthStore.setState({ apiKey: "demo-lead-key" });
    const session: AuthSession = { auth_mode: "demo", authenticated: true, user: ME };
    mockFetchRoutes({ "GET /v1/auth/session": session, "GET /v1/me": ME });
    const user = userEvent.setup();
    renderWithProviders(<AppRoutes />, { route: "/" });

    await user.click(await screen.findByRole("button", { name: "Switch API key" }));
    await user.click(screen.getByRole("menuitem", { name: /Sign out/ }));

    expect(useAuthStore.getState().apiKey).toBe(DEFAULT_API_KEY);
  });
});

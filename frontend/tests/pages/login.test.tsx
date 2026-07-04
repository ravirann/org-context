import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { useToastStore } from "@/components/ui/toast";
import LoginPage from "@/pages/login";

import { mockFetchRoutes, mockResponse, renderWithProviders } from "../utils";

function toastTitles(): string[] {
  return useToastStore.getState().toasts.map((t) => t.title);
}

describe("LoginPage", () => {
  let originalLocation: Location;

  beforeEach(() => {
    useToastStore.setState({ toasts: [] });
    originalLocation = window.location;
    Object.defineProperty(window, "location", {
      configurable: true,
      value: { ...originalLocation, href: "" },
    });
  });

  afterEach(() => {
    Object.defineProperty(window, "location", {
      configurable: true,
      value: originalLocation,
    });
  });

  it("renders the sign-in card", () => {
    mockFetchRoutes({});
    renderWithProviders(<LoginPage />, { route: "/login" });

    expect(screen.getByTestId("page-login")).toBeInTheDocument();
    expect(screen.getByText("Org Context Platform")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sign in with SSO" })).toBeInTheDocument();
  });

  it("fetches /v1/auth/login and redirects on click", async () => {
    const fetchMock = mockFetchRoutes({
      "GET /v1/auth/login": { authorization_url: "https://idp.example.com/authorize?x=1" },
    });
    const user = userEvent.setup();
    renderWithProviders(<LoginPage />, { route: "/login" });

    await user.click(screen.getByRole("button", { name: "Sign in with SSO" }));

    await waitFor(() => {
      expect(
        fetchMock.mock.calls.some(([input]) => String(input).includes("/v1/auth/login")),
      ).toBe(true);
    });
    await waitFor(() => {
      expect(window.location.href).toBe("https://idp.example.com/authorize?x=1");
    });
  });

  it("shows an error toast when the login endpoint fails", async () => {
    mockFetchRoutes({
      "GET /v1/auth/login": mockResponse({ detail: "auth_mode is demo" }, 409),
    });
    const user = userEvent.setup();
    renderWithProviders(<LoginPage />, { route: "/login" });

    await user.click(screen.getByRole("button", { name: "Sign in with SSO" }));

    await waitFor(() => {
      expect(toastTitles()).toContain("Sign-in failed");
    });
    expect(window.location.href).toBe("");
  });
});

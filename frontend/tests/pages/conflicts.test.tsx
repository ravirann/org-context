import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import ConflictsPage from "@/pages/conflicts";

import {
  conflictOpen,
  conflictResolved,
  conflictsPage,
  paginated,
} from "../fixtures-admin";
import { mockFetchRoutes, mockResponse, renderWithProviders } from "../utils";

describe("ConflictsPage", () => {
  it("renders the conflict table with topic chips, counts and status badges", async () => {
    mockFetchRoutes({ "GET /v1/conflicts": conflictsPage });
    renderWithProviders(<ConflictsPage />, { route: "/conflicts" });

    expect(await screen.findByText(conflictOpen.title)).toBeInTheDocument();
    expect(screen.getByText(conflictResolved.title)).toBeInTheDocument();
    expect(screen.getByText("payments.webhook-retry-policy")).toBeInTheDocument();
    expect(screen.getByText("open")).toBeInTheDocument();
    expect(screen.getByText("resolved")).toBeInTheDocument();
    // 2 repos + 3 services with max 3 chips → "+2" overflow badge.
    expect(screen.getByText("+2")).toBeInTheDocument();
    expect(screen.getByTestId("page-conflicts")).toBeInTheDocument();
  });

  it("shows loading skeletons while fetching", async () => {
    mockFetchRoutes({ "GET /v1/conflicts": conflictsPage });
    renderWithProviders(<ConflictsPage />, { route: "/conflicts" });

    expect(screen.getByTestId("conflicts-loading")).toBeInTheDocument();
    expect(await screen.findByTestId("conflicts-table")).toBeInTheDocument();
    expect(screen.queryByTestId("conflicts-loading")).not.toBeInTheDocument();
  });

  it("defaults to the open tab and refetches with status=resolved on tab switch", async () => {
    const fetchMock = mockFetchRoutes({
      "GET /v1/conflicts": (url: URL) =>
        url.searchParams.get("status") === "resolved"
          ? paginated([conflictResolved])
          : paginated([conflictOpen]),
    });
    renderWithProviders(<ConflictsPage />, { route: "/conflicts" });

    expect(await screen.findByText(conflictOpen.title)).toBeInTheDocument();
    const firstUrl = String(fetchMock.mock.calls[0][0]);
    expect(firstUrl).toContain("status=open");

    await userEvent.click(screen.getByRole("tab", { name: "Resolved" }));

    expect(await screen.findByText(conflictResolved.title)).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.queryByText(conflictOpen.title)).not.toBeInTheDocument();
    });
    const urls = fetchMock.mock.calls.map((call) => String(call[0]));
    expect(urls.some((u) => u.includes("status=resolved"))).toBe(true);
  });

  it("omits the status param on the All tab", async () => {
    const fetchMock = mockFetchRoutes({
      "GET /v1/conflicts": conflictsPage,
    });
    renderWithProviders(<ConflictsPage />, { route: "/conflicts?status=all" });

    expect(await screen.findByText(conflictOpen.title)).toBeInTheDocument();
    const firstUrl = String(fetchMock.mock.calls[0][0]);
    expect(firstUrl).not.toContain("status=");
  });

  it("shows a tab-specific empty state", async () => {
    mockFetchRoutes({ "GET /v1/conflicts": paginated([]) });
    renderWithProviders(<ConflictsPage />, { route: "/conflicts?status=resolved" });

    expect(await screen.findByText("No resolved conflicts yet")).toBeInTheDocument();
  });

  it("shows an error state and retries successfully", async () => {
    let calls = 0;
    mockFetchRoutes({
      "GET /v1/conflicts": () => {
        calls += 1;
        return calls === 1
          ? mockResponse({ detail: "kaboom" }, 500)
          : conflictsPage;
      },
    });
    renderWithProviders(<ConflictsPage />, { route: "/conflicts" });

    expect(await screen.findByText("kaboom")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByText(conflictOpen.title)).toBeInTheDocument();
  });

  it("renders PermissionDenied on 403", async () => {
    mockFetchRoutes({
      "GET /v1/conflicts": mockResponse({ detail: "Forbidden" }, 403),
    });
    renderWithProviders(<ConflictsPage />, { route: "/conflicts" });

    expect(await screen.findByText("Permission denied")).toBeInTheDocument();
  });
});

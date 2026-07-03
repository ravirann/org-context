import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, type Mock } from "vitest";

import DashboardPage from "@/pages/dashboard";

import {
  baseRoutes,
  dashboardSummaryFixture,
  dashboardTrendsFixture,
  emptyTrendsFixture,
} from "../fixtures";
import { mockFetchRoutes, mockResponse, renderWithProviders } from "../utils";

const happyRoutes = {
  ...baseRoutes,
  "GET /v1/dashboard/summary": dashboardSummaryFixture,
  "GET /v1/dashboard/trends": dashboardTrendsFixture,
};

function trendsCalls(fetchMock: Mock): string[] {
  return fetchMock.mock.calls
    .map((call) => String(call[0]))
    .filter((url) => url.includes("/v1/dashboard/trends"));
}

describe("DashboardPage", () => {
  it("renders all summary stats from the API", async () => {
    mockFetchRoutes(happyRoutes);
    renderWithProviders(<DashboardPage />);

    expect(await screen.findByText("12.8K")).toBeInTheDocument(); // total documents
    expect(screen.getByText("Indexed documents")).toBeInTheDocument();
    expect(screen.getByText("Connected sources")).toBeInTheDocument();
    expect(screen.getByText("7")).toBeInTheDocument();
    expect(screen.getByText("Active repos")).toBeInTheDocument();
    expect(screen.getByText("24")).toBeInTheDocument();
    expect(screen.getByText("Active services")).toBeInTheDocument();
    expect(screen.getByText("Active users")).toBeInTheDocument();
    expect(screen.getByText("86")).toBeInTheDocument();
    expect(screen.getByText("Context packets")).toBeInTheDocument();
    expect(screen.getByText("1,439")).toBeInTheDocument();
    expect(screen.getByText("Agent runs")).toBeInTheDocument();
    expect(screen.getByText("512")).toBeInTheDocument();
    expect(screen.getByText("Failed agent runs")).toBeInTheDocument();
    expect(screen.getByText("37")).toBeInTheDocument();
    expect(screen.getByText("Stale documents")).toBeInTheDocument();
    expect(screen.getByText("214")).toBeInTheDocument();
    expect(screen.getByText("Conflicting documents")).toBeInTheDocument();
    expect(screen.getByText("ACL violations blocked")).toBeInTheDocument();
    expect(screen.getByText("93")).toBeInTheDocument();
    expect(screen.getByText("Latest eval score")).toBeInTheDocument();
    expect(screen.getByText("0.87")).toBeInTheDocument();

    // Chart cards render.
    expect(screen.getByText("Eval score trend")).toBeInTheDocument();
    expect(screen.getByText("Source freshness")).toBeInTheDocument();
    expect(screen.getByText("Review rework")).toBeInTheDocument();
    expect(screen.getByText("Packets per day")).toBeInTheDocument();
  });

  it("links stale/conflict/failed-run cards to their pages", async () => {
    mockFetchRoutes(happyRoutes);
    renderWithProviders(<DashboardPage />);
    await screen.findByText("Stale documents");

    expect(
      screen.getByRole("link", { name: /stale documents/i }),
    ).toHaveAttribute("href", "/context-debt");
    expect(
      screen.getByRole("link", { name: /conflicting documents/i }),
    ).toHaveAttribute("href", "/conflicts");
    expect(
      screen.getByRole("link", { name: /failed agent runs/i }),
    ).toHaveAttribute("href", "/agent-runs?status=failed");
  });

  it("refetches trends when the days selector changes", async () => {
    const fetchMock = mockFetchRoutes(happyRoutes);
    const user = userEvent.setup();
    renderWithProviders(<DashboardPage />);
    await screen.findByText("Eval score trend");

    expect(trendsCalls(fetchMock).at(-1)).toContain("days=30");

    await user.click(screen.getByRole("button", { name: "7d" }));
    await waitFor(() => {
      expect(trendsCalls(fetchMock).at(-1)).toContain("days=7");
    });

    await user.click(screen.getByRole("button", { name: "90d" }));
    await waitFor(() => {
      expect(trendsCalls(fetchMock).at(-1)).toContain("days=90");
    });
  });

  it("shows skeletons while loading", () => {
    mockFetchRoutes({
      ...baseRoutes,
      "GET /v1/dashboard/summary": () => new Promise(() => {}),
      "GET /v1/dashboard/trends": () => new Promise(() => {}),
    });
    const { container } = renderWithProviders(<DashboardPage />);
    expect(container.querySelectorAll(".animate-pulse").length).toBeGreaterThan(0);
  });

  it("shows an error state and retries on click", async () => {
    let summaryCalls = 0;
    mockFetchRoutes({
      ...baseRoutes,
      "GET /v1/dashboard/summary": () => {
        summaryCalls += 1;
        return summaryCalls === 1
          ? mockResponse({ detail: "boom" }, 500)
          : dashboardSummaryFixture;
      },
      "GET /v1/dashboard/trends": dashboardTrendsFixture,
    });
    const user = userEvent.setup();
    renderWithProviders(<DashboardPage />);

    expect(await screen.findByRole("alert")).toHaveTextContent("boom");
    await user.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByText("12.8K")).toBeInTheDocument();
    expect(summaryCalls).toBe(2);
  });

  it("renders PermissionDenied on 403", async () => {
    mockFetchRoutes({
      ...baseRoutes,
      "GET /v1/dashboard/summary": mockResponse({ detail: "Forbidden" }, 403),
      "GET /v1/dashboard/trends": mockResponse({ detail: "Forbidden" }, 403),
    });
    renderWithProviders(<DashboardPage />);
    expect(await screen.findByText("Permission denied")).toBeInTheDocument();
  });

  it("shows an empty state when there is no trend data", async () => {
    mockFetchRoutes({
      ...baseRoutes,
      "GET /v1/dashboard/summary": dashboardSummaryFixture,
      "GET /v1/dashboard/trends": emptyTrendsFixture,
    });
    renderWithProviders(<DashboardPage />);
    expect(await screen.findByText("No trend data yet")).toBeInTheDocument();
  });
});

import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useLocation } from "react-router-dom";
import { describe, expect, it, type Mock } from "vitest";

import AgentRunsPage from "@/pages/agent-runs";

import { agentRuns, agentRunsPage, meAdmin, paginate } from "../fixtures-runs";
import { mockFetchRoutes, mockResponse, renderWithProviders } from "../utils";

function LocationProbe() {
  const location = useLocation();
  return <div data-testid="location">{location.pathname + location.search}</div>;
}

function runsRequests(fetchMock: Mock): string[] {
  return fetchMock.mock.calls
    .map(([input]) => String(input instanceof Request ? input.url : input))
    .filter((url) => url.includes("/v1/agent-runs"));
}

describe("AgentRunsPage", () => {
  it("renders runs with status badges, durations and packet links", async () => {
    mockFetchRoutes({
      "GET /v1/me": meAdmin,
      "GET /v1/agent-runs": agentRunsPage,
    });
    renderWithProviders(<AgentRunsPage />, { route: "/agent-runs" });

    expect(await screen.findByTestId("runs-table")).toBeInTheDocument();
    expect(screen.getAllByText("claude-code")).toHaveLength(2);
    expect(screen.getByText("cursor")).toBeInTheDocument();

    // Status badges.
    const table = screen.getByTestId("runs-table");
    expect(within(table).getByText("succeeded")).toBeInTheDocument();
    expect(within(table).getByText("running")).toBeInTheDocument();
    expect(within(table).getByText("failed")).toBeInTheDocument();
    expect(screen.getByTestId("run-status-running")).toBeInTheDocument();

    // Duration humanized; em dash while running.
    expect(screen.getByText("2m 14s")).toBeInTheDocument();
    const runningRow = screen.getByTestId("run-row-run-2");
    expect(within(runningRow).getAllByText("—").length).toBeGreaterThan(0);

    // Packet link icons only where context_packet_id is set.
    const packetLinks = screen.getAllByLabelText("Open context packet");
    expect(packetLinks).toHaveLength(2);
    expect(packetLinks[0]).toHaveAttribute("href", "/packets/packet-1");

    // Repo/service chips and users.
    expect(screen.getByText("org/payments")).toBeInTheDocument();
    expect(screen.getByText("ingestion-worker")).toBeInTheDocument();
    expect(screen.getByText("Priya Lead")).toBeInTheDocument();

    // Pagination footer reflects the server total.
    expect(screen.getByTestId("pagination")).toHaveTextContent("of 42");
  });

  it("shows loading skeletons while the query is pending", () => {
    mockFetchRoutes({
      "GET /v1/me": meAdmin,
      "GET /v1/agent-runs": () => new Promise(() => {}),
    });
    renderWithProviders(<AgentRunsPage />, { route: "/agent-runs" });
    expect(screen.getByTestId("runs-loading")).toBeInTheDocument();
  });

  it("shows an error state and recovers on retry", async () => {
    let calls = 0;
    mockFetchRoutes({
      "GET /v1/me": meAdmin,
      "GET /v1/agent-runs": () => {
        calls += 1;
        return calls === 1
          ? mockResponse({ detail: "boom" }, 500)
          : agentRunsPage;
      },
    });
    const user = userEvent.setup();
    renderWithProviders(<AgentRunsPage />, { route: "/agent-runs" });

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Something went wrong",
    );
    expect(screen.getByText("boom")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByTestId("runs-table")).toBeInTheDocument();
  });

  it("shows an empty state when no runs match", async () => {
    mockFetchRoutes({
      "GET /v1/me": meAdmin,
      "GET /v1/agent-runs": paginate([]),
    });
    renderWithProviders(<AgentRunsPage />, { route: "/agent-runs" });
    expect(await screen.findByText("No agent runs found")).toBeInTheDocument();
  });

  it("renders PermissionDenied on 403", async () => {
    mockFetchRoutes({
      "GET /v1/me": meAdmin,
      "GET /v1/agent-runs": mockResponse({ detail: "Forbidden" }, 403),
    });
    renderWithProviders(<AgentRunsPage />, { route: "/agent-runs" });
    expect(await screen.findByText("Permission denied")).toBeInTheDocument();
  });

  it("respects incoming URL params like ?status=failed", async () => {
    const fetchMock = mockFetchRoutes({
      "GET /v1/me": meAdmin,
      "GET /v1/agent-runs": paginate([agentRuns[2]]),
    });
    renderWithProviders(<AgentRunsPage />, {
      route: "/agent-runs?status=failed",
    });

    await screen.findByTestId("runs-table");
    expect(runsRequests(fetchMock)[0]).toContain("status=failed");

    // The failed toggle reflects the URL.
    const filterBar = screen.getByTestId("runs-filter-bar");
    expect(
      within(filterBar).getByRole("button", { name: "failed" }),
    ).toHaveAttribute("aria-pressed", "true");
  });

  it("updates the URL and refetches when filters change", async () => {
    const fetchMock = mockFetchRoutes({
      "GET /v1/me": meAdmin,
      "GET /v1/agent-runs": agentRunsPage,
    });
    const user = userEvent.setup();
    renderWithProviders(
      <>
        <AgentRunsPage />
        <LocationProbe />
      </>,
      { route: "/agent-runs?page=2" },
    );
    await screen.findByTestId("runs-table");

    const filterBar = screen.getByTestId("runs-filter-bar");
    await user.click(within(filterBar).getByRole("button", { name: "failed" }));

    await waitFor(() => {
      expect(screen.getByTestId("location")).toHaveTextContent("status=failed");
    });
    await waitFor(() => {
      const urls = runsRequests(fetchMock);
      expect(urls[urls.length - 1]).toContain("status=failed");
    });
    // Filter changes reset pagination.
    expect(screen.getByTestId("location")).not.toHaveTextContent("page=2");

    // Toggling the active status off clears the param.
    await user.click(within(filterBar).getByRole("button", { name: "failed" }));
    await waitFor(() => {
      expect(screen.getByTestId("location")).not.toHaveTextContent(
        "status=failed",
      );
    });

    // Text filters land in the URL and the query string too.
    await user.type(screen.getByLabelText("Filter by repo"), "org");
    await waitFor(() => {
      expect(screen.getByTestId("location")).toHaveTextContent("repo=org");
    });
    await waitFor(() => {
      const urls = runsRequests(fetchMock);
      expect(urls[urls.length - 1]).toContain("repo=org");
    });

    // Clear removes every filter.
    await user.click(screen.getByRole("button", { name: /Clear/ }));
    await waitFor(() => {
      expect(screen.getByTestId("location")).toHaveTextContent("/agent-runs");
      expect(screen.getByTestId("location")).not.toHaveTextContent("repo=org");
    });
  });

  it("navigates to the run detail on row click", async () => {
    mockFetchRoutes({
      "GET /v1/me": meAdmin,
      "GET /v1/agent-runs": agentRunsPage,
    });
    const user = userEvent.setup();
    renderWithProviders(
      <>
        <AgentRunsPage />
        <LocationProbe />
      </>,
      { route: "/agent-runs" },
    );

    await user.click(await screen.findByTestId("run-row-run-1"));
    expect(screen.getByTestId("location")).toHaveTextContent(
      "/agent-runs/run-1",
    );
  });

  it("paginates via the next button", async () => {
    const fetchMock = mockFetchRoutes({
      "GET /v1/me": meAdmin,
      "GET /v1/agent-runs": agentRunsPage,
    });
    const user = userEvent.setup();
    renderWithProviders(
      <>
        <AgentRunsPage />
        <LocationProbe />
      </>,
      { route: "/agent-runs" },
    );
    await screen.findByTestId("runs-table");

    await user.click(screen.getByRole("button", { name: "Next page" }));
    await waitFor(() => {
      expect(screen.getByTestId("location")).toHaveTextContent("page=2");
    });
    await waitFor(() => {
      const urls = runsRequests(fetchMock);
      expect(urls[urls.length - 1]).toContain("page=2");
    });
  });
});

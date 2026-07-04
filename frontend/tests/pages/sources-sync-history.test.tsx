import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";

import { useToastStore } from "@/components/ui/toast";
import SourcesPage from "@/pages/sources";

import {
  meAdmin,
  sourcesWithLastRunResponse,
  syncRunRunning,
  syncRunsResponse,
} from "../fixtures-runs";
import { mockFetchRoutes, mockResponse, renderWithProviders } from "../utils";

const baseRoutes = {
  "GET /v1/me": meAdmin,
  "GET /v1/sources": sourcesWithLastRunResponse,
};

beforeEach(() => {
  useToastStore.setState({ toasts: [] });
});

describe("Sources page — last-run summary", () => {
  it("renders the ok last-run summary with doc count for src-1", async () => {
    mockFetchRoutes(baseRoutes);
    renderWithProviders(<SourcesPage />, { route: "/sources" });
    await screen.findByTestId("sources-table");

    const row = screen.getByTestId("source-row-src-1");
    const summary = within(row).getByTestId("last-sync-run-summary");
    expect(within(summary).getByTestId("sync-run-dot-ok")).toBeInTheDocument();
    expect(summary).toHaveTextContent("+42 docs");
  });

  it("renders the error last-run summary with a warning icon for src-2", async () => {
    mockFetchRoutes(baseRoutes);
    renderWithProviders(<SourcesPage />, { route: "/sources" });
    await screen.findByTestId("sources-table");

    const row = screen.getByTestId("source-row-src-2");
    const summary = within(row).getByTestId("last-sync-run-summary");
    expect(within(summary).getByTestId("sync-run-dot-error")).toBeInTheDocument();
    expect(within(summary).getByLabelText("Last run had errors")).toBeInTheDocument();
  });

  it("shows 'no runs yet' when last_sync_run is null for src-3", async () => {
    mockFetchRoutes(baseRoutes);
    renderWithProviders(<SourcesPage />, { route: "/sources" });
    await screen.findByTestId("sources-table");

    const row = screen.getByTestId("source-row-src-3");
    expect(within(row).getByText("no runs yet")).toBeInTheDocument();
  });
});

describe("Sources page — sync history panel", () => {
  it("fetches and renders sync runs on expand, including trigger badges and error expansion", async () => {
    const fetchMock = mockFetchRoutes({
      ...baseRoutes,
      "GET /v1/sources/src-1/sync-runs": syncRunsResponse,
    });
    const user = userEvent.setup();
    renderWithProviders(<SourcesPage />, { route: "/sources" });
    await screen.findByTestId("sources-table");

    expect(screen.queryByTestId("sync-history-table-src-1")).not.toBeInTheDocument();

    await user.click(screen.getByLabelText("Toggle sync history for backend monorepo"));

    const table = await screen.findByTestId("sync-history-table-src-1");
    expect(fetchMock.mock.calls.some((c) => String(c[0]).includes("/v1/sources/src-1/sync-runs"))).toBe(
      true,
    );

    const errorRow = within(table).getByTestId("sync-run-row-run-a2");
    expect(within(errorRow).getByText("error")).toBeInTheDocument();
    expect(within(errorRow).getByText("manual")).toBeInTheDocument();

    const okRow = within(table).getByTestId("sync-run-row-run-a1");
    expect(within(okRow).getByText("ok")).toBeInTheDocument();
    expect(within(okRow).getByText("scheduled")).toBeInTheDocument();
    expect(within(okRow).getByText("42")).toBeInTheDocument();
    expect(within(okRow).getByText("118")).toBeInTheDocument();
    expect(within(okRow).getByText("2")).toBeInTheDocument();
    expect(within(okRow).getByText("340")).toBeInTheDocument();
    // finished_at - started_at = 3m12s
    expect(within(okRow).getByText("3m 12s")).toBeInTheDocument();

    // Expand the errors list on the error run.
    expect(
      within(errorRow).queryByText(/401 Unauthorized: token expired/),
    ).not.toBeInTheDocument();
    await user.click(within(errorRow).getByLabelText("Toggle 2 errors"));
    expect(within(errorRow).getByText(/issue-441: 401 Unauthorized: token expired/)).toBeInTheDocument();
    expect(within(errorRow).getByText(/\(unknown\): Timed out fetching page 3/)).toBeInTheDocument();
  });

  it("renders a running run with a duration dash and running badge", async () => {
    mockFetchRoutes({
      ...baseRoutes,
      "GET /v1/sources/src-1/sync-runs": { items: [syncRunRunning] },
    });
    const user = userEvent.setup();
    renderWithProviders(<SourcesPage />, { route: "/sources" });
    await screen.findByTestId("sources-table");
    await user.click(screen.getByLabelText("Toggle sync history for backend monorepo"));

    const table = await screen.findByTestId("sync-history-table-src-1");
    const row = within(table).getByTestId("sync-run-row-run-a3");
    expect(within(row).getByText("running")).toBeInTheDocument();
    // Duration and errors cells both render an em dash while running/error-free.
    expect(within(row).getAllByText("—")).toHaveLength(2);
  });

  it("shows the empty state when a source has no sync runs", async () => {
    const user = userEvent.setup();
    mockFetchRoutes({
      ...baseRoutes,
      "GET /v1/sources/src-1/sync-runs": { items: [] },
    });
    renderWithProviders(<SourcesPage />, { route: "/sources" });
    await screen.findByTestId("sources-table");

    await user.click(screen.getByLabelText("Toggle sync history for backend monorepo"));
    expect(await screen.findByText("No sync runs yet")).toBeInTheDocument();
  });

  it("shows an error state with retry when the history fetch fails", async () => {
    let calls = 0;
    const user = userEvent.setup();
    mockFetchRoutes({
      ...baseRoutes,
      "GET /v1/sources/src-1/sync-runs": () => {
        calls += 1;
        return calls === 1
          ? mockResponse({ detail: "history boom" }, 500)
          : syncRunsResponse;
      },
    });
    renderWithProviders(<SourcesPage />, { route: "/sources" });
    await screen.findByTestId("sources-table");

    await user.click(screen.getByLabelText("Toggle sync history for backend monorepo"));
    expect(await screen.findByText("history boom")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Retry" }));
    await waitFor(() => {
      expect(screen.getByTestId("sync-history-table-src-1")).toBeInTheDocument();
    });
  });

  it("collapses the history panel when toggled again", async () => {
    const user = userEvent.setup();
    mockFetchRoutes({
      ...baseRoutes,
      "GET /v1/sources/src-1/sync-runs": syncRunsResponse,
    });
    renderWithProviders(<SourcesPage />, { route: "/sources" });
    await screen.findByTestId("sources-table");

    const toggle = screen.getByLabelText("Toggle sync history for backend monorepo");
    await user.click(toggle);
    await screen.findByTestId("sync-history-table-src-1");

    await user.click(toggle);
    expect(screen.queryByTestId("sync-history-table-src-1")).not.toBeInTheDocument();
  });
});

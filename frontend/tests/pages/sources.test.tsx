import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, type Mock } from "vitest";

import { useToastStore } from "@/components/ui/toast";
import SourcesPage from "@/pages/sources";

import { meAdmin, meEngineer, sources, sourcesResponse } from "../fixtures-runs";
import { mockFetchRoutes, mockResponse, renderWithProviders } from "../utils";

function callsFor(fetchMock: Mock, method: string, urlPart: string) {
  return fetchMock.mock.calls.filter(([input, init]) => {
    const url = String(input instanceof Request ? input.url : input);
    return url.includes(urlPart) && (init?.method ?? "GET") === method;
  });
}

function bodyOf(call: unknown[]): unknown {
  const init = call[1] as RequestInit | undefined;
  return init?.body ? JSON.parse(String(init.body)) : undefined;
}

const baseRoutes = {
  "GET /v1/me": meAdmin,
  "GET /v1/sources": sourcesResponse,
};

beforeEach(() => {
  useToastStore.setState({ toasts: [] });
});

describe("SourcesPage", () => {
  it("renders the source table with type, sync, ACL and count columns", async () => {
    mockFetchRoutes(baseRoutes);
    renderWithProviders(<SourcesPage />, { route: "/sources" });

    expect(await screen.findByTestId("sources-table")).toBeInTheDocument();
    expect(screen.getByTestId("source-type-github")).toBeInTheDocument();
    expect(screen.getByTestId("source-type-jira")).toBeInTheDocument();
    expect(screen.getByTestId("source-type-slack")).toBeInTheDocument();

    const github = screen.getByTestId("source-row-src-1");
    expect(within(github).getByText("backend monorepo")).toBeInTheDocument();
    expect(within(github).getAllByText("ok")).toHaveLength(2); // sync + acl badges
    expect(within(github).getByText("12.5K")).toBeInTheDocument();
    expect(within(github).getByRole("switch")).toBeChecked();

    const jira = screen.getByTestId("source-row-src-2");
    // Both the sync-status and ACL-status badges can read "error".
    expect(within(jira).getAllByText("error").length).toBeGreaterThan(0);
    const slack = screen.getByTestId("source-row-src-3");
    expect(within(slack).getByText("idle")).toBeInTheDocument();
    expect(within(slack).getByRole("switch")).not.toBeChecked();
    expect(within(slack).getAllByText("—").length).toBeGreaterThan(0); // never synced

    // Inline editors show current values.
    expect(
      screen.getByLabelText("Authority rank for backend monorepo"),
    ).toHaveValue(90);
    expect(
      screen.getByLabelText("Freshness window days for backend monorepo"),
    ).toHaveValue(30);
  });

  it("expands the last_error details for failing sources", async () => {
    mockFetchRoutes(baseRoutes);
    const user = userEvent.setup();
    renderWithProviders(<SourcesPage />, { route: "/sources" });
    await screen.findByTestId("sources-table");

    expect(screen.queryByTestId("source-error-src-2")).not.toBeInTheDocument();
    await user.click(
      screen.getByLabelText("Toggle last error for payments board"),
    );
    expect(screen.getByTestId("source-error-src-2")).toHaveTextContent(
      "401 Unauthorized: token expired",
    );
  });

  it("PATCHes {enabled} when the switch is toggled", async () => {
    const fetchMock = mockFetchRoutes({
      ...baseRoutes,
      "PATCH /v1/sources/src-1": { ...sources[0], enabled: false },
    });
    const user = userEvent.setup();
    renderWithProviders(<SourcesPage />, { route: "/sources" });
    await screen.findByTestId("sources-table");

    await user.click(
      within(screen.getByTestId("source-row-src-1")).getByRole("switch"),
    );
    await waitFor(() => {
      expect(callsFor(fetchMock, "PATCH", "/v1/sources/src-1")).toHaveLength(1);
    });
    expect(bodyOf(callsFor(fetchMock, "PATCH", "/v1/sources/src-1")[0])).toEqual({
      enabled: false,
    });
  });

  it("PATCHes authority_rank and freshness_window_days from the inline editors", async () => {
    const fetchMock = mockFetchRoutes({
      ...baseRoutes,
      "PATCH /v1/sources/src-1": sources[0],
    });
    const user = userEvent.setup();
    renderWithProviders(<SourcesPage />, { route: "/sources" });
    await screen.findByTestId("sources-table");

    const rank = screen.getByLabelText("Authority rank for backend monorepo");
    await user.clear(rank);
    await user.type(rank, "95{Enter}");
    await waitFor(() => {
      expect(callsFor(fetchMock, "PATCH", "/v1/sources/src-1")).toHaveLength(1);
    });
    expect(bodyOf(callsFor(fetchMock, "PATCH", "/v1/sources/src-1")[0])).toEqual({
      authority_rank: 95,
    });

    // Freshness window commits on blur.
    const freshness = screen.getByLabelText(
      "Freshness window days for backend monorepo",
    );
    await user.clear(freshness);
    await user.type(freshness, "45");
    await user.tab();
    await waitFor(() => {
      expect(callsFor(fetchMock, "PATCH", "/v1/sources/src-1")).toHaveLength(2);
    });
    expect(bodyOf(callsFor(fetchMock, "PATCH", "/v1/sources/src-1")[1])).toEqual({
      freshness_window_days: 45,
    });
  });

  it("queues a sync with optimistic syncing status and a toast", async () => {
    const fetchMock = mockFetchRoutes({
      ...baseRoutes,
      "POST /v1/sources/src-1/sync": { status: "queued" },
    });
    const user = userEvent.setup();
    renderWithProviders(<SourcesPage />, { route: "/sources" });
    await screen.findByTestId("sources-table");

    await user.click(screen.getByLabelText("Sync backend monorepo now"));

    // Optimistic flip to syncing (spinner badge) inside the row.
    const row = screen.getByTestId("source-row-src-1");
    expect(
      await within(row).findByTestId("sync-status-syncing"),
    ).toBeInTheDocument();

    await waitFor(() => {
      expect(callsFor(fetchMock, "POST", "/v1/sources/src-1/sync")).toHaveLength(1);
    });
    await waitFor(() => {
      expect(
        useToastStore.getState().toasts.some((t) => t.title === "Sync queued"),
      ).toBe(true);
    });
  });

  it("rolls back the optimistic sync and toasts 'Requires admin' on 403", async () => {
    mockFetchRoutes({
      ...baseRoutes,
      "POST /v1/sources/src-1/sync": mockResponse({ detail: "Forbidden" }, 403),
    });
    const user = userEvent.setup();
    renderWithProviders(<SourcesPage />, { route: "/sources" });
    await screen.findByTestId("sources-table");

    await user.click(screen.getByLabelText("Sync backend monorepo now"));
    await waitFor(() => {
      expect(
        useToastStore.getState().toasts.some((t) => t.title === "Requires admin"),
      ).toBe(true);
    });
    // Rolled back — no syncing badge remains.
    expect(
      within(screen.getByTestId("source-row-src-1")).queryByTestId(
        "sync-status-syncing",
      ),
    ).not.toBeInTheDocument();
  });

  it("creates a source through the add-source dialog", async () => {
    const fetchMock = mockFetchRoutes({
      ...baseRoutes,
      "POST /v1/sources": {
        ...sources[0],
        id: "src-9",
        type: "confluence",
        name: "Team wiki",
      },
    });
    const user = userEvent.setup();
    renderWithProviders(<SourcesPage />, { route: "/sources" });
    await screen.findByTestId("sources-table");

    await user.click(screen.getByRole("button", { name: /Add source/ }));
    expect(screen.getByRole("dialog")).toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText("Source type"), "confluence");
    await user.type(screen.getByLabelText("Source name"), "Team wiki");
    await user.click(screen.getByRole("button", { name: "Create source" }));

    await waitFor(() => {
      expect(callsFor(fetchMock, "POST", "/v1/sources")).toHaveLength(1);
    });
    expect(bodyOf(callsFor(fetchMock, "POST", "/v1/sources")[0])).toEqual({
      type: "confluence",
      name: "Team wiki",
    });
    await waitFor(() => {
      expect(
        useToastStore.getState().toasts.some((t) => t.title === "Source added"),
      ).toBe(true);
    });
    // Dialog closes and the list refetches.
    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });
    expect(callsFor(fetchMock, "GET", "/v1/sources").length).toBeGreaterThan(1);
  });

  it("deletes a source after dialog confirmation", async () => {
    const fetchMock = mockFetchRoutes({
      ...baseRoutes,
      // jsdom Response cannot carry a body with 204 — a JSON null works the same.
      "DELETE /v1/sources/src-3": null,
    });
    const user = userEvent.setup();
    renderWithProviders(<SourcesPage />, { route: "/sources" });
    await screen.findByTestId("sources-table");

    await user.click(screen.getByLabelText("Delete #incidents archive"));
    const dialog = screen.getByRole("dialog");
    expect(dialog).toHaveTextContent("Delete source");
    expect(dialog).toHaveTextContent("#incidents archive");

    await user.click(within(dialog).getByRole("button", { name: "Delete source" }));
    await waitFor(() => {
      expect(callsFor(fetchMock, "DELETE", "/v1/sources/src-3")).toHaveLength(1);
    });
    await waitFor(() => {
      expect(
        useToastStore.getState().toasts.some((t) => t.title === "Source deleted"),
      ).toBe(true);
    });
  });

  it("disables admin-only controls for engineers", async () => {
    mockFetchRoutes({
      "GET /v1/me": meEngineer,
      "GET /v1/sources": sourcesResponse,
    });
    renderWithProviders(<SourcesPage />, { route: "/sources" });
    await screen.findByTestId("sources-table");

    expect(screen.getByRole("button", { name: /Add source/ })).toBeDisabled();
    const row = screen.getByTestId("source-row-src-1");
    expect(within(row).getByRole("switch")).toBeDisabled();
    expect(screen.getByLabelText("Sync backend monorepo now")).toBeDisabled();
    expect(screen.getByLabelText("Delete backend monorepo")).toBeDisabled();
    expect(
      screen.getByLabelText("Authority rank for backend monorepo"),
    ).toBeDisabled();
    expect(
      screen.getByLabelText("Freshness window days for backend monorepo"),
    ).toBeDisabled();
  });

  it("shows loading skeletons while pending", () => {
    mockFetchRoutes({
      "GET /v1/me": meAdmin,
      "GET /v1/sources": () => new Promise(() => {}),
    });
    renderWithProviders(<SourcesPage />, { route: "/sources" });
    expect(screen.getByTestId("sources-loading")).toBeInTheDocument();
  });

  it("shows an error state and recovers on retry", async () => {
    let calls = 0;
    mockFetchRoutes({
      "GET /v1/me": meAdmin,
      "GET /v1/sources": () => {
        calls += 1;
        return calls === 1
          ? mockResponse({ detail: "boom" }, 500)
          : sourcesResponse;
      },
    });
    const user = userEvent.setup();
    renderWithProviders(<SourcesPage />, { route: "/sources" });

    expect(await screen.findByText("boom")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByTestId("sources-table")).toBeInTheDocument();
  });

  it("shows an empty state when no sources are connected", async () => {
    mockFetchRoutes({
      "GET /v1/me": meAdmin,
      "GET /v1/sources": { items: [] },
    });
    renderWithProviders(<SourcesPage />, { route: "/sources" });
    expect(
      await screen.findByText("No sources connected"),
    ).toBeInTheDocument();
  });

  it("renders PermissionDenied when listing is forbidden", async () => {
    mockFetchRoutes({
      "GET /v1/me": meEngineer,
      "GET /v1/sources": mockResponse({ detail: "Forbidden" }, 403),
    });
    renderWithProviders(<SourcesPage />, { route: "/sources" });
    expect(await screen.findByText("Permission denied")).toBeInTheDocument();
  });
});

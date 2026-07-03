import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { aggregateByTeam } from "@/components/heatmaps/aggregate";
import {
  debtCsv,
  ownershipCsv,
  teamHeatmapCsv,
  toCsv,
  userHeatmapCsv,
} from "@/components/heatmaps/csv";
import { dateRange, isoDaysAgo } from "@/components/heatmaps/date-range";
import { intensityStep } from "@/components/heatmaps/heatmap-grid";
import HeatmapsPage from "@/pages/heatmaps";

import {
  contextDebtFixture,
  heatmapDays,
  heatmapUsersFixture,
  meFixture,
  ownershipFixture,
} from "../fixtures-graph";
import { mockFetchRoutes, mockResponse, renderWithProviders } from "../utils";

/* ------------------------------- pure functions ------------------------------- */

describe("aggregateByTeam", () => {
  it("sums cells per team and sorts by total desc", () => {
    const teams = aggregateByTeam(heatmapUsersFixture.rows);
    expect(teams.map((t) => t.team_name)).toEqual([
      "Payments Squad",
      "Platform",
    ]);
    const payments = teams[0];
    expect(payments.total).toBe(48);
    expect(payments.user_count).toBe(2);
    // day index 3: Priya 9 + Marco 2
    expect(payments.cells[3]).toEqual({ day: heatmapDays[3], value: 11 });
    expect(payments.cells).toHaveLength(heatmapDays.length);
  });

  it("groups users without a team under 'No team'", () => {
    const teams = aggregateByTeam([
      {
        user_id: "u-x",
        user_name: "Sol O'Loner",
        team_name: null,
        cells: [{ day: "2026-07-01", value: 5 }],
        total: 5,
      },
    ]);
    expect(teams).toHaveLength(1);
    expect(teams[0].team_name).toBe("No team");
    expect(teams[0].total).toBe(5);
  });

  it("returns an empty list for no rows", () => {
    expect(aggregateByTeam([])).toEqual([]);
  });
});

describe("csv helpers", () => {
  it("toCsv escapes commas, quotes and newlines", () => {
    const csv = toCsv(
      ["a", "b"],
      [
        ["x,y", 'he said "hi"'],
        [null, "line\nbreak"],
      ],
    );
    expect(csv).toBe('a,b\n"x,y","he said ""hi"""\n,"line\nbreak"\n');
  });

  it("userHeatmapCsv includes one column per day plus total", () => {
    const csv = userHeatmapCsv(heatmapUsersFixture.rows, heatmapDays);
    const lines = csv.trimEnd().split("\n");
    expect(lines[0]).toBe(`user,team,${heatmapDays.join(",")},total`);
    expect(lines[1]).toBe(
      `Priya Nair,Payments Squad,2,0,3,9,1,0,0,4,2,5,1,0,2,3,32`,
    );
    expect(lines).toHaveLength(1 + heatmapUsersFixture.rows.length);
  });

  it("teamHeatmapCsv aggregates and formats team rows", () => {
    const csv = teamHeatmapCsv(
      aggregateByTeam(heatmapUsersFixture.rows),
      heatmapDays,
    );
    const lines = csv.trimEnd().split("\n");
    expect(lines[0]).toBe(`team,users,${heatmapDays.join(",")},total`);
    expect(lines[1].startsWith("Payments Squad,2,")).toBe(true);
    expect(lines[1].endsWith(",48")).toBe(true);
  });

  it("ownershipCsv and debtCsv serialize all rows", () => {
    const own = ownershipCsv(ownershipFixture.rows).trimEnd().split("\n");
    expect(own[0]).toBe(
      "key,owner_team,doc_count,owners,coverage_score,last_activity_at",
    );
    expect(own[1]).toContain("payments-api,Payments Squad,42");
    expect(own[2]).toContain("billing-svc,,7"); // null team → empty field

    const debt = debtCsv(contextDebtFixture.rows).trimEnd().split("\n");
    expect(debt).toHaveLength(1 + contextDebtFixture.rows.length);
    expect(debt[1]).toContain("payments-api");
    expect(debt[1]).toContain("0.91");
  });
});

describe("intensityStep", () => {
  it("maps values to a 0-4 scale", () => {
    expect(intensityStep(0, 9)).toBe(0);
    expect(intensityStep(1, 9)).toBe(1);
    expect(intensityStep(5, 9)).toBe(3);
    expect(intensityStep(9, 9)).toBe(4);
    expect(intensityStep(5, 0)).toBe(0);
  });
});

describe("dateRange", () => {
  it("computes from/to ISO dates for a preset", () => {
    const now = new Date("2026-07-03T12:00:00Z");
    expect(dateRange(14, now)).toEqual({ from: "2026-06-19", to: "2026-07-03" });
    expect(isoDaysAgo(0, now)).toBe("2026-07-03");
  });
});

/* --------------------------------- page tests --------------------------------- */

function setup(overrides: Record<string, unknown> = {}) {
  const fetchMock = mockFetchRoutes({
    "GET /v1/me": meFixture,
    "GET /v1/heatmaps/users": heatmapUsersFixture,
    "GET /v1/heatmaps/ownership": ownershipFixture,
    "GET /v1/heatmaps/context-debt": contextDebtFixture,
    ...overrides,
  });
  const utils = renderWithProviders(<HeatmapsPage />, { route: "/heatmaps" });
  return { fetchMock, ...utils };
}

function usersCalls(fetchMock: ReturnType<typeof mockFetchRoutes>): string[] {
  return fetchMock.mock.calls
    .map((call) => String(call[0]))
    .filter((url) => url.includes("/v1/heatmaps/users"));
}

describe("HeatmapsPage", () => {
  it("renders the user grid with intensity-scaled cells sorted by total", async () => {
    setup();
    await screen.findByTestId("user-heatmap");
    // max value cell (Priya, day 4 of the range → value 9)
    expect(
      screen.getByTestId(`hm-cell-u-1-${heatmapDays[3]}`),
    ).toHaveAttribute("data-intensity", "4");
    // zero cell
    expect(
      screen.getByTestId(`hm-cell-u-3-${heatmapDays[0]}`),
    ).toHaveAttribute("data-intensity", "0");
    // sorted by total desc → Priya first
    const rowHeaders = screen.getAllByRole("rowheader");
    expect(rowHeaders[0]).toHaveTextContent("Priya Nair");
    expect(rowHeaders[0]).toHaveTextContent("Payments Squad");
    // tooltip title
    expect(
      screen.getByTestId(`hm-cell-u-1-${heatmapDays[3]}`),
    ).toHaveAttribute("title", `Priya Nair · ${heatmapDays[3]}: 9`);
  });

  it("requests the API with from/to and metric params", async () => {
    const { fetchMock } = setup();
    await screen.findByTestId("user-heatmap");
    const range = dateRange(30);
    const url = usersCalls(fetchMock)[0];
    expect(url).toContain(`from=${range.from}`);
    expect(url).toContain(`to=${range.to}`);
    expect(url).toContain("metric=all");
  });

  it("refetches when the metric and range change", async () => {
    const { fetchMock } = setup();
    await screen.findByTestId("user-heatmap");
    fireEvent.change(screen.getByLabelText("Metric"), {
      target: { value: "pr" },
    });
    await waitFor(() =>
      expect(usersCalls(fetchMock).some((u) => u.includes("metric=pr"))).toBe(
        true,
      ),
    );
    fireEvent.change(screen.getByLabelText("Date range"), {
      target: { value: "14" },
    });
    const range = dateRange(14);
    await waitFor(() =>
      expect(
        usersCalls(fetchMock).some((u) => u.includes(`from=${range.from}`)),
      ).toBe(true),
    );
  });

  it("refetches with repo/service/team filters", async () => {
    const { fetchMock } = setup();
    await screen.findByTestId("user-heatmap");
    fireEvent.change(screen.getByLabelText("Filter by repo"), {
      target: { value: "payments-api" },
    });
    await waitFor(() =>
      expect(
        usersCalls(fetchMock).some((u) => u.includes("repo=payments-api")),
      ).toBe(true),
    );
  });

  it("opens the drilldown dialog on cell click with a graph link", async () => {
    setup();
    await screen.findByTestId("user-heatmap");
    fireEvent.click(screen.getByTestId(`hm-cell-u-1-${heatmapDays[3]}`));
    const dialog = await screen.findByTestId("cell-drilldown");
    expect(dialog).toHaveTextContent("Priya Nair");
    expect(dialog).toHaveTextContent("9");
    expect(dialog).toHaveTextContent("All metrics");
    const link = within(dialog).getByRole("link", {
      name: "View user in graph",
    });
    expect(link).toHaveAttribute("href", "/graph?q=Priya%20Nair");
  });

  it("aggregates by team on the team tab", async () => {
    setup();
    await screen.findByTestId("user-heatmap");
    fireEvent.click(screen.getByRole("tab", { name: "Team activity" }));
    await screen.findByTestId("team-heatmap");
    const rowHeaders = screen.getAllByRole("rowheader");
    expect(rowHeaders[0]).toHaveTextContent("Payments Squad");
    expect(rowHeaders[0]).toHaveTextContent("2 users");
    expect(rowHeaders[1]).toHaveTextContent("Platform");
    // summed cell: 9 + 2 = 11 (Payments Squad on day 4)
    expect(
      screen.getByTestId(`hm-cell-Payments Squad-${heatmapDays[3]}`),
    ).toHaveAttribute("title", `Payments Squad · ${heatmapDays[3]}: 11`);
  });

  it("fetches ownership on tab switch and renders sortable rows", async () => {
    const { fetchMock } = setup();
    await screen.findByTestId("user-heatmap");
    fireEvent.click(screen.getByRole("tab", { name: "Ownership" }));
    await screen.findByTestId("ownership-table");
    expect(
      fetchMock.mock.calls.some((call) =>
        String(call[0]).includes("/v1/heatmaps/ownership"),
      ),
    ).toBe(true);
    // default sort: coverage desc → payments-api first
    let rows = screen.getAllByTestId(/ownership-row-/);
    expect(rows[0]).toHaveTextContent("payments-api");
    // missing owner badge for billing-svc
    expect(
      within(screen.getByTestId("ownership-row-billing-svc")).getByText(
        "Missing owner",
      ),
    ).toBeInTheDocument();
    // owner initials chips
    expect(
      within(screen.getByTestId("ownership-row-payments-api")).getByTitle(
        "Priya Nair",
      ),
    ).toHaveTextContent("PN");
    // flip coverage sort → billing-svc (0.31) first
    fireEvent.click(screen.getByRole("button", { name: /Coverage/ }));
    rows = screen.getAllByTestId(/ownership-row-/);
    expect(rows[0]).toHaveTextContent("billing-svc");
    // sort by docs desc → payments-api (42) first
    fireEvent.click(screen.getByRole("button", { name: /Docs/ }));
    rows = screen.getAllByTestId(/ownership-row-/);
    expect(rows[0]).toHaveTextContent("payments-api");
  });

  it("fetches context debt on tab switch and opens the row drilldown", async () => {
    const { fetchMock } = setup();
    await screen.findByTestId("user-heatmap");
    fireEvent.click(screen.getByRole("tab", { name: "Context debt" }));
    await screen.findByTestId("debt-table");
    expect(
      fetchMock.mock.calls.some((call) =>
        String(call[0]).includes("/v1/heatmaps/context-debt"),
      ),
    ).toBe(true);
    const hotRow = screen.getByTestId("debt-row-payments-api");
    // stale_count 12 is the column max → intensity 4
    const staleCell = within(hotRow).getByText("12");
    expect(staleCell).toHaveAttribute("data-intensity", "4");
    // missing owner badge on billing-svc row
    expect(
      within(screen.getByTestId("debt-row-billing-svc")).getByText(
        "Missing owner",
      ),
    ).toBeInTheDocument();
    // inverted debt score badge: high score renders red classes
    expect(within(hotRow).getByText("0.91").className).toContain("text-red");
    // row click → drilldown dialog with links
    fireEvent.click(hotRow);
    const dialog = await screen.findByTestId("debt-drilldown");
    expect(dialog).toHaveTextContent("payments-api");
    expect(
      within(dialog).getByRole("link", { name: "Open context debt" }),
    ).toHaveAttribute("href", "/context-debt");
    expect(
      within(dialog).getByRole("link", { name: "Open conflicts" }),
    ).toHaveAttribute("href", "/conflicts");
  });

  it("exports the current tab as CSV", async () => {
    setup();
    await screen.findByTestId("user-heatmap");
    const blobs: Blob[] = [];
    const createObjectURL = vi.fn((blob: Blob) => {
      blobs.push(blob);
      return "blob:mock";
    });
    vi.stubGlobal(
      "URL",
      Object.assign(URL, {
        createObjectURL,
        revokeObjectURL: vi.fn(),
      }),
    );
    const clickSpy = vi
      .spyOn(HTMLAnchorElement.prototype, "click")
      .mockImplementation(() => {});
    fireEvent.click(screen.getByRole("button", { name: /Export CSV/ }));
    expect(createObjectURL).toHaveBeenCalledTimes(1);
    expect(clickSpy).toHaveBeenCalledTimes(1);
    const text = await blobs[0].text();
    expect(text.startsWith("user,team,")).toBe(true);
    expect(text).toContain("Priya Nair");
    clickSpy.mockRestore();
  });

  it("shows a loading skeleton while pending", async () => {
    setup({ "GET /v1/heatmaps/users": () => new Promise(() => {}) });
    expect(await screen.findByTestId("heatmap-skeleton")).toBeInTheDocument();
  });

  it("shows an empty state when there are no rows", async () => {
    setup({ "GET /v1/heatmaps/users": { rows: [], days: [] } });
    expect(await screen.findByText("No activity")).toBeInTheDocument();
  });

  it("shows PermissionDenied on 403", async () => {
    setup({
      "GET /v1/heatmaps/users": mockResponse({ detail: "Forbidden" }, 403),
    });
    expect(await screen.findByText("Permission denied")).toBeInTheDocument();
  });

  it("shows an error state with retry on failure", async () => {
    const { fetchMock } = setup({
      "GET /v1/heatmaps/users": mockResponse({ detail: "boom" }, 500),
    });
    expect(await screen.findByText("boom")).toBeInTheDocument();
    const before = usersCalls(fetchMock).length;
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    await waitFor(() =>
      expect(usersCalls(fetchMock).length).toBeGreaterThan(before),
    );
  });

  it("shows error state on ownership failure too", async () => {
    setup({
      "GET /v1/heatmaps/ownership": mockResponse({ detail: "nope" }, 500),
    });
    await screen.findByTestId("user-heatmap");
    fireEvent.click(screen.getByRole("tab", { name: "Ownership" }));
    expect(await screen.findByText("nope")).toBeInTheDocument();
  });

  it("shows empty states for ownership and debt", async () => {
    setup({
      "GET /v1/heatmaps/ownership": { rows: [] },
      "GET /v1/heatmaps/context-debt": { rows: [] },
    });
    await screen.findByTestId("user-heatmap");
    fireEvent.click(screen.getByRole("tab", { name: "Ownership" }));
    expect(await screen.findByText("No ownership data")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("tab", { name: "Context debt" }));
    expect(await screen.findByText("No context debt")).toBeInTheDocument();
  });
});

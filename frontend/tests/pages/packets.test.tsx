import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useLocation } from "react-router-dom";
import { describe, expect, it, type Mock } from "vitest";

import PacketsPage from "@/pages/packets";

import {
  baseRoutes,
  compiledPacketFixture,
  packetSummariesFixture,
} from "../fixtures";
import { mockFetchRoutes, mockResponse, renderWithProviders } from "../utils";

function LocationProbe() {
  const location = useLocation();
  return <div data-testid="location">{location.pathname + location.search}</div>;
}

const happyRoutes = {
  ...baseRoutes,
  "GET /v1/context-packets": packetSummariesFixture,
  "POST /v1/context/compile": compiledPacketFixture,
};

function listCalls(fetchMock: Mock): string[] {
  return fetchMock.mock.calls
    .map((call) => String(call[0]))
    .filter((url) => url.includes("/v1/context-packets"));
}

describe("PacketsPage", () => {
  it("renders the packets table from the API", async () => {
    mockFetchRoutes(happyRoutes);
    renderWithProviders(<PacketsPage />, { route: "/packets" });

    // Task text appears in both the cell and its tooltip — expect both.
    expect(
      (await screen.findAllByText("Fix webhook retry storm in payment-service")).length,
    ).toBeGreaterThan(0);
    expect(screen.getAllByText("Add payment reconciliation job").length).toBeGreaterThan(0);
    // Intent labels also exist as <option>s in the filter select.
    expect(screen.getAllByText("bugfix").length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByText("feature").length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText("acme/payments")).toBeInTheDocument();
    expect(screen.getByText("billing-service")).toBeInTheDocument();
    expect(screen.getByText("5,120")).toBeInTheDocument(); // token_estimate
    expect(screen.getByText("15.3K")).toBeInTheDocument(); // compact tokens
    expect(screen.getByText("0.88")).toBeInTheDocument(); // confidence
    expect(screen.getByText("succeeded")).toBeInTheDocument();
    expect(screen.getByText("pending")).toBeInTheDocument();
    expect(screen.getByText("Asha Rao")).toBeInTheDocument();
    expect(screen.getByText(/Page 1 of 1 · 2 packets/)).toBeInTheDocument();
  });

  it("applies the intent filter to the request", async () => {
    const fetchMock = mockFetchRoutes(happyRoutes);
    const user = userEvent.setup();
    renderWithProviders(<PacketsPage />, { route: "/packets" });
    await screen.findAllByText("Add payment reconciliation job");

    await user.selectOptions(
      screen.getByRole("combobox", { name: "Filter by intent" }),
      "bugfix",
    );
    await waitFor(() => {
      expect(listCalls(fetchMock).at(-1)).toContain("intent=bugfix");
    });

    await user.type(screen.getByRole("textbox", { name: "Filter by repo" }), "acme/payments");
    await waitFor(() => {
      expect(listCalls(fetchMock).at(-1)).toContain("repo=acme%2Fpayments");
    });
  });

  it("navigates to the packet on row click", async () => {
    mockFetchRoutes(happyRoutes);
    const user = userEvent.setup();
    renderWithProviders(
      <>
        <PacketsPage />
        <LocationProbe />
      </>,
      { route: "/packets" },
    );

    const [taskCell] = await screen.findAllByText("Fix webhook retry storm in payment-service");
    await user.click(taskCell);
    expect(screen.getByTestId("location")).toHaveTextContent("/packets/pkt-1");
  });

  it("compiles a packet from the dialog and navigates to it", async () => {
    const fetchMock = mockFetchRoutes(happyRoutes);
    const user = userEvent.setup();
    renderWithProviders(
      <>
        <PacketsPage />
        <LocationProbe />
      </>,
      { route: "/packets" },
    );
    await screen.findAllByText("Add payment reconciliation job");

    await user.click(screen.getByRole("button", { name: /Compile context/ }));
    expect(screen.getByRole("dialog")).toBeInTheDocument();

    await user.type(
      screen.getByRole("textbox", { name: "Task" }),
      "Investigate flaky payment e2e test",
    );
    await user.type(screen.getByRole("textbox", { name: "Repo" }), "acme/payments");
    await user.type(screen.getByRole("spinbutton", { name: "Max tokens" }), "4000");
    await user.click(screen.getByRole("button", { name: "Compile" }));

    await waitFor(() => {
      expect(screen.getByTestId("location")).toHaveTextContent("/packets/pkt-new");
    });
    const compileCall = fetchMock.mock.calls.find(([url]) =>
      String(url).includes("/v1/context/compile"),
    )!;
    expect(JSON.parse(String((compileCall[1] as RequestInit).body))).toEqual({
      task: "Investigate flaky payment e2e test",
      repo: "acme/payments",
      max_tokens: 4000,
    });
  });

  it("shows an empty state when there are no packets", async () => {
    mockFetchRoutes({
      ...baseRoutes,
      "GET /v1/context-packets": { items: [], total: 0, page: 1, page_size: 20 },
    });
    renderWithProviders(<PacketsPage />, { route: "/packets" });
    expect(await screen.findByText("No context packets")).toBeInTheDocument();
  });

  it("shows loading skeletons while fetching", () => {
    mockFetchRoutes({
      ...baseRoutes,
      "GET /v1/context-packets": () => new Promise(() => {}),
    });
    renderWithProviders(<PacketsPage />, { route: "/packets" });
    expect(screen.getByTestId("packets-skeleton")).toBeInTheDocument();
  });

  it("shows an error state with retry that refetches", async () => {
    let calls = 0;
    mockFetchRoutes({
      ...baseRoutes,
      "GET /v1/context-packets": () => {
        calls += 1;
        return calls === 1
          ? mockResponse({ detail: "packets exploded" }, 500)
          : packetSummariesFixture;
      },
    });
    const user = userEvent.setup();
    renderWithProviders(<PacketsPage />, { route: "/packets" });

    expect(await screen.findByRole("alert")).toHaveTextContent("packets exploded");
    await user.click(screen.getByRole("button", { name: "Retry" }));
    expect(
      (await screen.findAllByText("Fix webhook retry storm in payment-service")).length,
    ).toBeGreaterThan(0);
    expect(calls).toBe(2);
  });

  it("renders PermissionDenied on 403", async () => {
    mockFetchRoutes({
      ...baseRoutes,
      "GET /v1/context-packets": mockResponse({ detail: "Forbidden" }, 403),
    });
    renderWithProviders(<PacketsPage />, { route: "/packets" });
    expect(await screen.findByText("Permission denied")).toBeInTheDocument();
  });
});

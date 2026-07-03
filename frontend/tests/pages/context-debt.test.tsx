import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import ContextDebtPage from "@/pages/context-debt";

import { debtReport, emptyDebtReport } from "../fixtures-admin";
import { mockFetchRoutes, mockResponse, renderWithProviders } from "../utils";

describe("ContextDebtPage", () => {
  it("renders all eight debt cards with fixture data", async () => {
    mockFetchRoutes({ "GET /v1/context-debt": debtReport });
    renderWithProviders(<ContextDebtPage />, { route: "/context-debt" });

    expect(
      await screen.findByText("Stale docs by repo / service / team"),
    ).toBeInTheDocument();
    expect(screen.getByText("Missing owners")).toBeInTheDocument();
    expect(screen.getByText("Undocumented APIs")).toBeInTheDocument();
    expect(screen.getByText("Repeated context misses")).toBeInTheDocument();
    expect(screen.getByText("Failed-agent areas")).toBeInTheDocument();
    expect(screen.getByText("Docs never used")).toBeInTheDocument();
    expect(screen.getByText("Docs frequently rejected")).toBeInTheDocument();
    expect(screen.getByText("Conflicts by source type")).toBeInTheDocument();

    // Missing owners (destructive list).
    expect(screen.getByText("legacy-billing")).toBeInTheDocument();
    expect(screen.getByText("9 docs")).toBeInTheDocument();
    // Undocumented API chips.
    expect(screen.getByText("POST /v2/refunds")).toBeInTheDocument();
    // Repeated misses table.
    expect(screen.getByText("refund idempotency key rules")).toBeInTheDocument();
    expect(screen.getByText("14")).toBeInTheDocument();
    // Failed agent areas ratio.
    expect(screen.getByText("8 / 20")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "40% failure rate" })).toBeInTheDocument();
    // Never-used / rejected docs link to the explorer.
    expect(screen.getByRole("link", { name: "2019 on-call handbook" })).toHaveAttribute(
      "href",
      "/explorer/documents/d0000000-0000-4000-8000-0000000000c1",
    );
    expect(screen.getByText("21")).toBeInTheDocument();
    expect(screen.getByTestId("page-context-debt")).toBeInTheDocument();
  });

  it("renders both chart containers and the section anchor nav", async () => {
    mockFetchRoutes({ "GET /v1/context-debt": debtReport });
    renderWithProviders(<ContextDebtPage />, { route: "/context-debt" });

    expect(await screen.findByTestId("stale-docs-chart")).toBeInTheDocument();
    expect(screen.getByTestId("conflicts-by-source-chart")).toBeInTheDocument();

    const nav = screen.getByRole("navigation", { name: "Report sections" });
    expect(nav).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Owners" })).toHaveAttribute(
      "href",
      "#missing-owners",
    );
  });

  it("toggles the stale docs card between chart and table", async () => {
    mockFetchRoutes({ "GET /v1/context-debt": debtReport });
    renderWithProviders(<ContextDebtPage />, { route: "/context-debt" });

    await screen.findByTestId("stale-docs-chart");
    await userEvent.click(screen.getByRole("button", { name: "Table" }));

    expect(screen.getByTestId("stale-docs-table")).toBeInTheDocument();
    expect(screen.queryByTestId("stale-docs-chart")).not.toBeInTheDocument();
    expect(screen.getByText("payments-api")).toBeInTheDocument();
    expect(screen.getByText("12")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Chart" }));
    expect(screen.getByTestId("stale-docs-chart")).toBeInTheDocument();
  });

  it("shows a sober per-card empty state when the report is clean", async () => {
    mockFetchRoutes({ "GET /v1/context-debt": emptyDebtReport });
    renderWithProviders(<ContextDebtPage />, { route: "/context-debt" });

    await screen.findByText("Missing owners");
    expect(screen.getAllByText(/None found/)).toHaveLength(8);
  });

  it("shows loading skeletons while fetching", async () => {
    mockFetchRoutes({ "GET /v1/context-debt": debtReport });
    renderWithProviders(<ContextDebtPage />, { route: "/context-debt" });

    expect(screen.getByTestId("context-debt-loading")).toBeInTheDocument();
    expect(await screen.findByText("Missing owners")).toBeInTheDocument();
  });

  it("shows an error state with retry", async () => {
    let calls = 0;
    mockFetchRoutes({
      "GET /v1/context-debt": () => {
        calls += 1;
        return calls === 1 ? mockResponse({ detail: "debt broke" }, 500) : debtReport;
      },
    });
    renderWithProviders(<ContextDebtPage />, { route: "/context-debt" });

    expect(await screen.findByText("debt broke")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByText("Missing owners")).toBeInTheDocument();
  });

  it("renders PermissionDenied on 403", async () => {
    mockFetchRoutes({
      "GET /v1/context-debt": mockResponse({ detail: "Forbidden" }, 403),
    });
    renderWithProviders(<ContextDebtPage />, { route: "/context-debt" });

    expect(await screen.findByText("Permission denied")).toBeInTheDocument();
  });
});

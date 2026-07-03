import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useLocation } from "react-router-dom";
import { describe, expect, it, type Mock } from "vitest";

import ExplorerPage from "@/pages/explorer";

import {
  baseRoutes,
  emptySearchResponseFixture,
  searchResponseFixture,
} from "../fixtures";
import { mockFetchRoutes, mockResponse, renderWithProviders } from "../utils";

function LocationProbe() {
  const location = useLocation();
  return <div data-testid="location">{location.pathname + location.search}</div>;
}

function searchBodies(fetchMock: Mock): Array<Record<string, unknown>> {
  return fetchMock.mock.calls
    .filter(([url]) => String(url).includes("/v1/search"))
    .map(([, init]) => JSON.parse(String((init as RequestInit).body)));
}

const happyRoutes = {
  ...baseRoutes,
  "POST /v1/search": searchResponseFixture,
};

describe("ExplorerPage", () => {
  it("runs the search from ?q= and renders results", async () => {
    const fetchMock = mockFetchRoutes(happyRoutes);
    renderWithProviders(<ExplorerPage />, { route: "/explorer?q=webhook" });

    expect(await screen.findByText("Payment webhook retry runbook")).toBeInTheDocument();
    expect(screen.getByText("ADR-042: Payment idempotency keys")).toBeInTheDocument();
    expect(screen.getByText("42 results")).toBeInTheDocument();
    expect(screen.getByText("Confluence")).toBeInTheDocument();
    expect(screen.getByText("0.92")).toBeInTheDocument();
    expect(screen.getByText("Page 1 of 3")).toBeInTheDocument();

    // Result links to the document detail page.
    expect(
      screen.getByRole("link", { name: /Payment webhook retry runbook/ }),
    ).toHaveAttribute("href", "/explorer/documents/doc-1");

    // Snippet terms are highlighted client-side with <mark>.
    const marks = document.querySelectorAll("mark");
    expect(marks.length).toBeGreaterThan(0);
    expect(marks[0]).toHaveTextContent(/webhook/i);

    const body = searchBodies(fetchMock).at(-1)!;
    expect(body.query).toBe("webhook");
    expect(body.page).toBe(1);
    expect(body.page_size).toBe(20);
  });

  it("shows the ACL blocked notice when results were hidden", async () => {
    mockFetchRoutes(happyRoutes);
    renderWithProviders(<ExplorerPage />, { route: "/explorer?q=webhook" });
    expect(
      await screen.findByText("3 results hidden by access control"),
    ).toBeInTheDocument();
  });

  it("debounces typing, updates the URL and fetches results", async () => {
    const fetchMock = mockFetchRoutes(happyRoutes);
    const user = userEvent.setup();
    renderWithProviders(
      <>
        <ExplorerPage />
        <LocationProbe />
      </>,
      { route: "/explorer" },
    );

    // No query yet — invite to search, no fetch to /v1/search.
    expect(screen.getByText("Search your organization's context")).toBeInTheDocument();

    await user.type(screen.getByRole("searchbox", { name: "Search query" }), "idempotency");

    await waitFor(() => {
      expect(screen.getByTestId("location")).toHaveTextContent("/explorer?q=idempotency");
    });
    expect(await screen.findByText("Payment webhook retry runbook")).toBeInTheDocument();
    expect(searchBodies(fetchMock).at(-1)!.query).toBe("idempotency");
  });

  it("applies filters (doc type toggle, status, page size) to the request", async () => {
    const fetchMock = mockFetchRoutes(happyRoutes);
    const user = userEvent.setup();
    renderWithProviders(<ExplorerPage />, { route: "/explorer?q=webhook" });
    await screen.findByText("Payment webhook retry runbook");

    // Toggle the runbook doc type chip (options derived from results).
    await user.click(screen.getByRole("button", { name: "runbook" }));
    await waitFor(() => {
      expect(searchBodies(fetchMock).at(-1)!.doc_types).toEqual(["runbook"]);
    });

    await user.selectOptions(screen.getByRole("combobox", { name: "Filter by status" }), "stale");
    await waitFor(() => {
      expect(searchBodies(fetchMock).at(-1)!.status).toBe("stale");
    });

    await user.selectOptions(screen.getByRole("combobox", { name: "Results per page" }), "50");
    await waitFor(() => {
      expect(searchBodies(fetchMock).at(-1)!.page_size).toBe(50);
    });
  });

  it("paginates with the next button", async () => {
    const fetchMock = mockFetchRoutes(happyRoutes);
    const user = userEvent.setup();
    renderWithProviders(<ExplorerPage />, { route: "/explorer?q=webhook" });
    await screen.findByText("Page 1 of 3");

    expect(screen.getByRole("button", { name: "Previous page" })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Next page" }));
    await waitFor(() => {
      expect(searchBodies(fetchMock).at(-1)!.page).toBe(2);
    });
  });

  it("shows an empty state when nothing matches", async () => {
    mockFetchRoutes({ ...baseRoutes, "POST /v1/search": emptySearchResponseFixture });
    renderWithProviders(<ExplorerPage />, { route: "/explorer?q=zzz" });
    expect(await screen.findByText("No results")).toBeInTheDocument();
  });

  it("shows loading skeletons while searching", () => {
    mockFetchRoutes({ ...baseRoutes, "POST /v1/search": () => new Promise(() => {}) });
    renderWithProviders(<ExplorerPage />, { route: "/explorer?q=webhook" });
    expect(screen.getByTestId("explorer-skeleton")).toBeInTheDocument();
  });

  it("shows an error state with retry that refetches", async () => {
    let calls = 0;
    mockFetchRoutes({
      ...baseRoutes,
      "POST /v1/search": () => {
        calls += 1;
        return calls === 1 ? mockResponse({ detail: "search broke" }, 500) : searchResponseFixture;
      },
    });
    const user = userEvent.setup();
    renderWithProviders(<ExplorerPage />, { route: "/explorer?q=webhook" });

    expect(await screen.findByRole("alert")).toHaveTextContent("search broke");
    await user.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByText("Payment webhook retry runbook")).toBeInTheDocument();
    expect(calls).toBe(2);
  });

  it("renders PermissionDenied on 403", async () => {
    mockFetchRoutes({
      ...baseRoutes,
      "POST /v1/search": mockResponse({ detail: "Forbidden" }, 403),
    });
    renderWithProviders(<ExplorerPage />, { route: "/explorer?q=webhook" });
    expect(await screen.findByText("Permission denied")).toBeInTheDocument();
  });
});

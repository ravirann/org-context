/**
 * Coverage for the pagination button handlers on PacketsPage
 * (src/pages/packets.tsx) and ConflictsPage (src/pages/conflicts.tsx), which
 * aren't exercised by the existing single-page fixtures in
 * tests/pages/packets.test.tsx / conflicts.test.tsx.
 */
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, type Mock } from "vitest";

import ConflictsPage from "@/pages/conflicts";
import PacketsPage from "@/pages/packets";

import { baseRoutes } from "../fixtures";
import { conflictOpen, conflictResolved, paginated } from "../fixtures-admin";
import { mockFetchRoutes, renderWithProviders } from "../utils";

function urlsFor(fetchMock: Mock, path: string): string[] {
  return fetchMock.mock.calls.map((c) => String(c[0])).filter((u) => u.includes(path));
}

describe("PacketsPage pagination", () => {
  const page1 = {
    items: [
      {
        id: "pkt-1",
        task: "Page one task",
        intent: "bugfix" as const,
        repo: "acme/payments",
        service: "payment-service",
        token_estimate: 100,
        confidence_score: 0.5,
        agent_outcome: "succeeded" as const,
        requested_by_name: "Asha Rao",
        created_at: "2026-07-01T10:00:00Z",
        source_count: 1,
      },
    ],
    total: 45,
    page: 1,
    page_size: 20,
  };
  const page2 = { ...page1, items: [{ ...page1.items[0], id: "pkt-2", task: "Page two task" }], page: 2 };

  it("navigates to the next and previous page", async () => {
    const fetchMock = mockFetchRoutes({
      ...baseRoutes,
      "GET /v1/context-packets": (url: URL) =>
        url.searchParams.get("page") === "2" ? page2 : page1,
    });
    const user = userEvent.setup();
    renderWithProviders(<PacketsPage />, { route: "/packets" });

    await screen.findAllByText("Page one task");
    expect(screen.getByRole("button", { name: "Previous page" })).toBeDisabled();
    expect(screen.getByText(/Page 1 of 3/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Next page" }));
    await waitFor(() => {
      expect(urlsFor(fetchMock, "/v1/context-packets").at(-1)).toContain("page=2");
    });
    await screen.findAllByText("Page two task");
    expect(screen.getByText(/Page 2 of 3/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Previous page" })).toBeEnabled();

    await user.click(screen.getByRole("button", { name: "Previous page" }));
    await screen.findAllByText("Page one task");
  });
});

describe("ConflictsPage pagination", () => {
  it("navigates to the next and previous page and preserves the status tab", async () => {
    const fetchMock = mockFetchRoutes({
      "GET /v1/conflicts": (url: URL) =>
        url.searchParams.get("page") === "2"
          ? paginated([conflictResolved], { page: 2, total: 25 })
          : paginated([conflictOpen], { page: 1, total: 25 }),
    });
    const user = userEvent.setup();
    renderWithProviders(<ConflictsPage />, { route: "/conflicts" });

    await screen.findByText(conflictOpen.title);
    expect(screen.getByText(/Page 1 of 2/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Previous" })).toBeDisabled();

    await user.click(screen.getByRole("button", { name: "Next" }));
    await waitFor(() => {
      expect(urlsFor(fetchMock, "/v1/conflicts").at(-1)).toContain("page=2");
    });
    await screen.findByText(conflictResolved.title);
    expect(screen.getByText(/Page 2 of 2/)).toBeInTheDocument();
    expect(urlsFor(fetchMock, "/v1/conflicts").at(-1)).toContain("status=open");

    await user.click(screen.getByRole("button", { name: "Previous" }));
    await screen.findByText(conflictOpen.title);
  });
});

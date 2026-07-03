import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, type Mock } from "vitest";

import DocumentDetailPage from "@/pages/document-detail";

import { useToastStore } from "@/components/ui/toast";

import { baseRoutes, documentDetailFixture, feedbackFixture } from "../fixtures";
import { mockFetchRoutes, mockResponse, renderWithProviders } from "../utils";

const ROUTE = { route: "/explorer/documents/doc-1", path: "/explorer/documents/:id" };

const happyRoutes = {
  ...baseRoutes,
  "GET /v1/documents/doc-1": documentDetailFixture,
  "POST /v1/feedback": { ...feedbackFixture, type: "stale_context", document_id: "doc-1" },
};

function feedbackBodies(fetchMock: Mock): Array<Record<string, unknown>> {
  return fetchMock.mock.calls
    .filter(([url]) => String(url).includes("/v1/feedback"))
    .map(([, init]) => JSON.parse(String((init as RequestInit).body)));
}

describe("DocumentDetailPage", () => {
  it("renders header metadata, scores and the conflict banner", async () => {
    mockFetchRoutes(happyRoutes);
    renderWithProviders(<DocumentDetailPage />, ROUTE);

    expect(
      await screen.findByRole("heading", { name: "Payment webhook retry runbook" }),
    ).toBeInTheDocument();
    expect(screen.getByText("runbook")).toBeInTheDocument();
    expect(screen.getByText("active")).toBeInTheDocument();
    expect(screen.getByText("Confluence (confluence)")).toBeInTheDocument();
    expect(screen.getByText("by Maya Chen")).toBeInTheDocument();
    expect(screen.getByText("payments.webhook.retry")).toBeInTheDocument();
    expect(screen.getByText("0.90")).toBeInTheDocument(); // freshness
    expect(screen.getByText("0.85")).toBeInTheDocument(); // authority
    expect(screen.getByText("used in 12 packets")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Open source/ })).toHaveAttribute(
      "href",
      "https://wiki.acme.dev/runbooks/payment-webhook",
    );

    // Conflict warning banner links to the conflict.
    const banner = screen.getByRole("alert");
    expect(banner).toHaveTextContent("This document conflicts with other sources");
    expect(
      screen.getByRole("link", { name: "Retry limits disagree between runbook and ADR" }),
    ).toHaveAttribute("href", "/conflicts/conf-1");

    // Content tab is default.
    expect(screen.getByText(/Page the payments on-call/)).toBeInTheDocument();
  });

  it("switches tabs: chunks (expandable), permissions, related and usage", async () => {
    mockFetchRoutes(happyRoutes);
    const user = userEvent.setup();
    renderWithProviders(<DocumentDetailPage />, ROUTE);
    await screen.findByRole("heading", { name: "Payment webhook retry runbook" });

    // Chunks tab with expandable long chunk.
    await user.click(screen.getByRole("tab", { name: "Chunks (2)" }));
    expect(screen.getByText("120")).toBeInTheDocument();
    expect(screen.getByText("180")).toBeInTheDocument();
    const expandButton = screen.getByRole("button", { name: "Expand chunk 1" });
    await user.click(expandButton);
    expect(screen.getByText(/replay the event from the dashboard/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Collapse chunk 1" }));

    // Permissions tab explains the ACL.
    await user.click(screen.getByRole("tab", { name: "Permissions" }));
    expect(screen.getByText("Access control")).toBeInTheDocument();
    expect(screen.getByText(/Visible to 2 teams and 14 users/)).toBeInTheDocument();
    // "Payments" also appears in the header team chip — expect both occurrences.
    expect(screen.getAllByText("Payments").length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText("SRE")).toBeInTheDocument();

    // Related tab lists related docs with relation badges.
    await user.click(screen.getByRole("tab", { name: "Related (1)" }));
    expect(
      screen.getByRole("link", { name: /ADR-042: Payment idempotency keys/ }),
    ).toHaveAttribute("href", "/explorer/documents/doc-2");
    expect(screen.getByText("mentions")).toBeInTheDocument();

    // Usage tab shows packet usage with selected/rejected badges.
    await user.click(screen.getByRole("tab", { name: "Usage (2)" }));
    expect(screen.getByRole("link", { name: "Fix webhook retry storm" })).toHaveAttribute(
      "href",
      "/packets/pkt-1",
    );
    expect(screen.getByText("selected")).toBeInTheDocument();
    expect(screen.getByText("rejected")).toBeInTheDocument();
  });

  it("posts stale and permission feedback from the header actions", async () => {
    const fetchMock = mockFetchRoutes(happyRoutes);
    const user = userEvent.setup();
    renderWithProviders(<DocumentDetailPage />, ROUTE);
    await screen.findByRole("heading", { name: "Payment webhook retry runbook" });

    await user.click(screen.getByRole("button", { name: /Report stale/ }));
    await waitFor(() => {
      expect(feedbackBodies(fetchMock).at(-1)).toEqual({
        type: "stale_context",
        document_id: "doc-1",
      });
    });
    // Toaster lives in App.tsx, so assert on the toast store instead.
    expect(
      useToastStore.getState().toasts.some((t) => t.title === "Reported as stale"),
    ).toBe(true);

    await user.click(screen.getByRole("button", { name: /Report permission issue/ }));
    await waitFor(() => {
      expect(feedbackBodies(fetchMock).at(-1)).toEqual({
        type: "permission_issue",
        document_id: "doc-1",
      });
    });
  });

  it("shows a 404-specific error state", async () => {
    mockFetchRoutes({
      ...baseRoutes,
      "GET /v1/documents/doc-1": mockResponse({ detail: "Not found" }, 404),
    });
    renderWithProviders(<DocumentDetailPage />, ROUTE);
    expect(
      await screen.findByText("Document not found or not accessible."),
    ).toBeInTheDocument();
  });

  it("renders PermissionDenied on 403", async () => {
    mockFetchRoutes({
      ...baseRoutes,
      "GET /v1/documents/doc-1": mockResponse({ detail: "Forbidden" }, 403),
    });
    renderWithProviders(<DocumentDetailPage />, ROUTE);
    expect(await screen.findByText("Permission denied")).toBeInTheDocument();
  });

  it("shows an error state with retry that refetches", async () => {
    let calls = 0;
    mockFetchRoutes({
      ...baseRoutes,
      "GET /v1/documents/doc-1": () => {
        calls += 1;
        return calls === 1 ? mockResponse({ detail: "db down" }, 500) : documentDetailFixture;
      },
    });
    const user = userEvent.setup();
    renderWithProviders(<DocumentDetailPage />, ROUTE);

    expect(await screen.findByRole("alert")).toHaveTextContent("db down");
    await user.click(screen.getByRole("button", { name: "Retry" }));
    expect(
      await screen.findByRole("heading", { name: "Payment webhook retry runbook" }),
    ).toBeInTheDocument();
    expect(calls).toBe(2);
  });

  it("shows skeletons while loading", () => {
    mockFetchRoutes({
      ...baseRoutes,
      "GET /v1/documents/doc-1": () => new Promise(() => {}),
    });
    const { container } = renderWithProviders(<DocumentDetailPage />, ROUTE);
    expect(container.querySelectorAll(".animate-pulse").length).toBeGreaterThan(0);
  });

  it("shows empty states for related and usage when absent, and public ACL copy", async () => {
    mockFetchRoutes({
      ...baseRoutes,
      "GET /v1/documents/doc-1": {
        ...documentDetailFixture,
        acl: { public: true, team_names: [], user_count: 0 },
        related: [],
        conflicts: [],
        packet_usage: [],
      },
    });
    const user = userEvent.setup();
    renderWithProviders(<DocumentDetailPage />, ROUTE);
    await screen.findByRole("heading", { name: "Payment webhook retry runbook" });

    expect(screen.queryByRole("alert")).not.toBeInTheDocument(); // no conflict banner

    await user.click(screen.getByRole("tab", { name: "Permissions" }));
    expect(screen.getByText(/This document is public/)).toBeInTheDocument();

    await user.click(screen.getByRole("tab", { name: "Related (0)" }));
    expect(screen.getByText("No related documents")).toBeInTheDocument();

    await user.click(screen.getByRole("tab", { name: "Usage (0)" }));
    expect(screen.getByText("Not used in any packets")).toBeInTheDocument();
  });
});

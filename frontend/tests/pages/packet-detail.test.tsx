import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, type Mock } from "vitest";

import PacketDetailPage from "@/pages/packet-detail";

import { baseRoutes, feedbackFixture, packetDetailFixture } from "../fixtures";
import { mockFetchRoutes, mockResponse, renderWithProviders } from "../utils";

const ROUTE = { route: "/packets/pkt-1", path: "/packets/:id" };

const happyRoutes = {
  ...baseRoutes,
  "GET /v1/context-packets/pkt-1": packetDetailFixture,
  "POST /v1/feedback": feedbackFixture,
};

function feedbackBodies(fetchMock: Mock): Array<Record<string, unknown>> {
  return fetchMock.mock.calls
    .filter(([url]) => String(url).includes("/v1/feedback"))
    .map(([, init]) => JSON.parse(String((init as RequestInit).body)));
}

describe("PacketDetailPage", () => {
  it("renders the summary header, scores and compiled context", async () => {
    mockFetchRoutes(happyRoutes);
    renderWithProviders(<PacketDetailPage />, ROUTE);

    expect(
      await screen.findByText("Fix webhook retry storm in payment-service"),
    ).toBeInTheDocument();
    expect(screen.getByText("bugfix")).toBeInTheDocument();
    expect(screen.getByText("acme/payments")).toBeInTheDocument();
    expect(screen.getByText("payment-service")).toBeInTheDocument();
    expect(screen.getByText("requested by Asha Rao")).toBeInTheDocument();
    expect(screen.getAllByText("succeeded").length).toBeGreaterThan(0); // outcome + agent run
    expect(screen.getByText("0.88")).toBeInTheDocument(); // confidence
    expect(screen.getAllByText("0.90").length).toBeGreaterThan(0); // freshness
    expect(screen.getByText("0.84")).toBeInTheDocument(); // authority
    expect(screen.getByText(/~5,120 tokens/)).toBeInTheDocument();

    // Compiled context preserved as pre-wrap block with citation markers.
    expect(screen.getByText(/exponential backoff \[S1\]/)).toBeInTheDocument();
  });

  it("renders selected sources with reasons and links", async () => {
    mockFetchRoutes(happyRoutes);
    renderWithProviders(<PacketDetailPage />, ROUTE);
    await screen.findByText("Selected sources (2)");

    // The title appears both as a selected-source link and a citation link.
    const links = screen.getAllByRole("link", { name: "Payment webhook retry runbook" });
    expect(links.length).toBeGreaterThan(0);
    for (const link of links) {
      expect(link).toHaveAttribute("href", "/explorer/documents/doc-1");
    }
    expect(screen.getByText("vector match")).toBeInTheDocument();
    expect(screen.getByText("fresh")).toBeInTheDocument();
    expect(screen.getByText("authoritative")).toBeInTheDocument();
  });

  it("expands the collapsed rejected sources with per-row reasons", async () => {
    mockFetchRoutes(happyRoutes);
    const user = userEvent.setup();
    renderWithProviders(<PacketDetailPage />, ROUTE);
    await screen.findByText("Selected sources (2)");

    // Collapsed by default.
    expect(screen.queryByText("Legacy payments FAQ")).not.toBeInTheDocument();

    const toggle = screen.getByRole("button", { name: /Rejected sources \(2\)/ });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    await user.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText("Legacy payments FAQ")).toBeInTheDocument();
    expect(screen.getByText("superseded by newer runbook")).toBeInTheDocument();
    expect(screen.getByText("stale beyond freshness window")).toBeInTheDocument();
  });

  it("renders citations, conflict notes, ACL note, risks and recommended tests", async () => {
    mockFetchRoutes(happyRoutes);
    renderWithProviders(<PacketDetailPage />, ROUTE);
    await screen.findByText("Citations (2)");

    expect(screen.getByText("S1")).toBeInTheDocument();
    expect(screen.getByText("S2")).toBeInTheDocument();
    expect(
      screen.getByText("retries use exponential backoff up to 5 attempts"),
    ).toBeInTheDocument();

    expect(screen.getByText("Conflict resolution notes")).toBeInTheDocument();
    expect(screen.getByText("payments.webhook.retry")).toBeInTheDocument();
    expect(
      screen.getByText("Runbook chosen over ADR draft — higher freshness and authority."),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "chosen document" })).toHaveAttribute(
      "href",
      "/explorer/documents/doc-1",
    );

    expect(screen.getByRole("note")).toHaveTextContent(
      "2 sources filtered by access control. Two finance documents were excluded by team ACLs.",
    );

    expect(
      screen.getByText("Retry limit change may impact reconciliation jobs"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Replay a failed webhook and assert 5 retries"),
    ).toBeInTheDocument();
    expect(screen.getByText("Idempotency key uniqueness test")).toBeInTheDocument();
  });

  it("shows the linked agent run and existing feedback", async () => {
    mockFetchRoutes(happyRoutes);
    renderWithProviders(<PacketDetailPage />, ROUTE);
    await screen.findByText("Agent run");

    expect(screen.getByText("claude-code")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "View run details" })).toHaveAttribute(
      "href",
      "/agent-runs/run-1",
    );

    expect(screen.getByText("Human feedback (1)")).toBeInTheDocument();
    expect(screen.getByText("useful")).toBeInTheDocument();
    expect(screen.getByText("Nailed the retry context.")).toBeInTheDocument();
    expect(screen.getByText(/Maya Chen/)).toBeInTheDocument();
  });

  it("submits feedback with a comment via the dialog and refetches", async () => {
    let packetFetches = 0;
    const fetchMock = mockFetchRoutes({
      ...happyRoutes,
      "GET /v1/context-packets/pkt-1": () => {
        packetFetches += 1;
        return packetDetailFixture;
      },
    });
    const user = userEvent.setup();
    renderWithProviders(<PacketDetailPage />, ROUTE);
    await screen.findByText("Selected sources (2)");

    await user.click(screen.getByRole("button", { name: /Missing context/ }));
    const dialog = screen.getByRole("dialog");
    expect(dialog).toHaveTextContent("Mark packet as missing context");

    await user.type(
      screen.getByRole("textbox", { name: "Feedback comment" }),
      "No billing docs included",
    );
    await user.click(screen.getByRole("button", { name: "Submit feedback" }));

    await waitFor(() => {
      expect(feedbackBodies(fetchMock).at(-1)).toEqual({
        context_packet_id: "pkt-1",
        type: "missing_context",
        comment: "No billing docs included",
      });
    });
    await waitFor(() => {
      expect(packetFetches).toBeGreaterThanOrEqual(2); // refetched after feedback
    });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("submits Useful feedback without a comment", async () => {
    const fetchMock = mockFetchRoutes(happyRoutes);
    const user = userEvent.setup();
    renderWithProviders(<PacketDetailPage />, ROUTE);
    await screen.findByText("Selected sources (2)");

    await user.click(screen.getByRole("button", { name: /^Useful$/ }));
    await user.click(screen.getByRole("button", { name: "Submit feedback" }));

    await waitFor(() => {
      expect(feedbackBodies(fetchMock).at(-1)).toEqual({
        context_packet_id: "pkt-1",
        type: "useful",
      });
    });
  });

  it("shows skeletons while loading", () => {
    mockFetchRoutes({
      ...baseRoutes,
      "GET /v1/context-packets/pkt-1": () => new Promise(() => {}),
    });
    const { container } = renderWithProviders(<PacketDetailPage />, ROUTE);
    expect(container.querySelectorAll(".animate-pulse").length).toBeGreaterThan(0);
  });

  it("shows an error state with retry that refetches", async () => {
    let calls = 0;
    mockFetchRoutes({
      ...baseRoutes,
      "GET /v1/context-packets/pkt-1": () => {
        calls += 1;
        return calls === 1 ? mockResponse({ detail: "kaput" }, 500) : packetDetailFixture;
      },
    });
    const user = userEvent.setup();
    renderWithProviders(<PacketDetailPage />, ROUTE);

    expect(await screen.findByRole("alert")).toHaveTextContent("kaput");
    await user.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByText("Selected sources (2)")).toBeInTheDocument();
    expect(calls).toBe(2);
  });

  it("shows a 404-specific error state", async () => {
    mockFetchRoutes({
      ...baseRoutes,
      "GET /v1/context-packets/pkt-1": mockResponse({ detail: "Not found" }, 404),
    });
    renderWithProviders(<PacketDetailPage />, ROUTE);
    expect(
      await screen.findByText("Context packet not found or not accessible."),
    ).toBeInTheDocument();
  });

  it("renders PermissionDenied on 403", async () => {
    mockFetchRoutes({
      ...baseRoutes,
      "GET /v1/context-packets/pkt-1": mockResponse({ detail: "Forbidden" }, 403),
    });
    renderWithProviders(<PacketDetailPage />, ROUTE);
    expect(await screen.findByText("Permission denied")).toBeInTheDocument();
  });

  it("handles a sparse packet (no citations, notes, risks, agent run or sources)", async () => {
    mockFetchRoutes({
      ...baseRoutes,
      "GET /v1/context-packets/pkt-1": {
        ...packetDetailFixture,
        selected_sources: [],
        rejected_sources: [],
        citations: [],
        conflict_notes: [],
        acl_notes: { blocked_count: 0, note: "" },
        risks: [],
        recommended_tests: [],
        agent_run: null,
        feedback: [],
      },
    });
    const user = userEvent.setup();
    renderWithProviders(<PacketDetailPage />, ROUTE);
    await screen.findByText("Selected sources (0)");

    expect(screen.getByText("No sources selected")).toBeInTheDocument();
    expect(screen.queryByText("Citations (0)")).not.toBeInTheDocument();
    expect(screen.queryByText("Conflict resolution notes")).not.toBeInTheDocument();
    expect(screen.queryByRole("note")).not.toBeInTheDocument();
    expect(screen.queryByText("Agent run")).not.toBeInTheDocument();
    expect(screen.getByText(/No feedback yet/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Rejected sources \(0\)/ }));
    expect(screen.getByText("Nothing was rejected.")).toBeInTheDocument();
  });
});

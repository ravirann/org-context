import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import AgentRunDetailPage from "@/pages/agent-run-detail";

import { agentRunDetail, agentRunDetailMinimal, meAdmin } from "../fixtures-runs";
import { mockFetchRoutes, mockResponse, renderWithProviders } from "../utils";

function renderDetail(id: string) {
  return renderWithProviders(<AgentRunDetailPage />, {
    route: `/agent-runs/${id}`,
    path: "/agent-runs/:id",
  });
}

describe("AgentRunDetailPage", () => {
  it("renders every section of a finished run", async () => {
    mockFetchRoutes({
      "GET /v1/me": meAdmin,
      "GET /v1/agent-runs/run-1": agentRunDetail,
    });
    renderDetail("run-1");

    // Header: agent name (page h1 + card title) + status + scope + meta.
    const headings = await screen.findAllByRole("heading", {
      name: "claude-code",
    });
    expect(headings.length).toBeGreaterThan(0);
    expect(screen.getByText("succeeded")).toBeInTheDocument();
    expect(screen.getByText("org/payments")).toBeInTheDocument();
    expect(screen.getByText("payments-api")).toBeInTheDocument();
    expect(screen.getByText("Evan Engineer")).toBeInTheDocument();
    expect(screen.getByText("2m 14s")).toBeInTheDocument();

    // Original task prose.
    expect(screen.getByText("Original task")).toBeInTheDocument();

    // Agent plan block.
    expect(
      screen.getByText(/Reproduce the duplicate-event bug/),
    ).toBeInTheDocument();

    // Changed files with count badge.
    const filesBadge = screen.getByLabelText("3 changed files");
    expect(filesBadge).toHaveTextContent("3");
    expect(
      screen.getByText("src/payments/webhooks/handler.py"),
    ).toBeInTheDocument();

    // PR + Langfuse links.
    expect(
      screen.getByRole("link", { name: /View pull request/ }),
    ).toHaveAttribute("href", "https://github.com/org/payments/pull/321");
    expect(screen.getByRole("link", { name: /Langfuse trace/ })).toHaveAttribute(
      "href",
      "https://langfuse.example.com/trace/abc123",
    );

    // Reviewer comments.
    expect(screen.getByText("Priya Lead")).toBeInTheDocument();
    expect(
      screen.getByText("LGTM after the dedupe TTL tweak."),
    ).toBeInTheDocument();
  });

  it("highlights FAIL/Error lines in the terminal-styled test output", async () => {
    mockFetchRoutes({
      "GET /v1/me": meAdmin,
      "GET /v1/agent-runs/run-1": agentRunDetail,
    });
    renderDetail("run-1");

    const terminal = await screen.findByTestId("terminal-output");
    const errorLines = terminal.querySelectorAll("[data-line-error]");
    expect(errorLines).toHaveLength(2);
    expect(errorLines[0]).toHaveTextContent("test_duplicate_event FAILED");
    expect(errorLines[1]).toHaveTextContent(
      "AssertionError: Error processing duplicate event",
    );
    // Passing lines are not highlighted.
    expect(
      within(terminal).getByText(/test_single_event PASSED/),
    ).not.toHaveAttribute("data-line-error");
  });

  it("renders the context packet summary with a full-packet link", async () => {
    mockFetchRoutes({
      "GET /v1/me": meAdmin,
      "GET /v1/agent-runs/run-1": agentRunDetail,
    });
    renderDetail("run-1");

    const packet = await screen.findByTestId("packet-summary");
    expect(within(packet).getByText("bugfix")).toBeInTheDocument();
    expect(within(packet).getByText("5,482")).toBeInTheDocument();
    expect(within(packet).getByText("0.87")).toBeInTheDocument();
    expect(
      within(packet).getByText("ADR-014: Webhook idempotency keys"),
    ).toBeInTheDocument();
    expect(
      within(packet).getByRole("link", { name: /Open full packet/ }),
    ).toHaveAttribute("href", "/packets/packet-1");
  });

  it("falls back gracefully for a running run without packet/trace/output", async () => {
    mockFetchRoutes({
      "GET /v1/me": meAdmin,
      "GET /v1/agent-runs/run-2": agentRunDetailMinimal,
    });
    renderDetail("run-2");

    expect(await screen.findByText("No trace recorded")).toBeInTheDocument();
    expect(
      screen.getByText("No context packet was attached to this run."),
    ).toBeInTheDocument();
    expect(screen.getByText("No plan recorded.")).toBeInTheDocument();
    expect(screen.getByText("No test output captured.")).toBeInTheDocument();
    expect(screen.getByText("No files changed.")).toBeInTheDocument();
    expect(screen.getByText("No reviewer comments yet.")).toBeInTheDocument();
    expect(screen.queryByTestId("terminal-output")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: /View pull request/ }),
    ).not.toBeInTheDocument();
  });

  it("shows a loading skeleton while fetching", () => {
    mockFetchRoutes({
      "GET /v1/me": meAdmin,
      "GET /v1/agent-runs/run-1": () => new Promise(() => {}),
    });
    renderDetail("run-1");
    expect(screen.getByTestId("run-detail-loading")).toBeInTheDocument();
  });

  it("shows a not-found error state on 404", async () => {
    mockFetchRoutes({
      "GET /v1/me": meAdmin,
      "GET /v1/agent-runs/missing": mockResponse({ detail: "Not found" }, 404),
    });
    renderDetail("missing");
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Agent run not found",
    );
    // 404 is terminal — no retry offered.
    expect(
      screen.queryByRole("button", { name: "Retry" }),
    ).not.toBeInTheDocument();
  });

  it("shows a retryable error state on server errors", async () => {
    mockFetchRoutes({
      "GET /v1/me": meAdmin,
      "GET /v1/agent-runs/run-1": mockResponse({ detail: "kaput" }, 500),
    });
    renderDetail("run-1");
    expect(await screen.findByText("kaput")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });

  it("renders PermissionDenied on 403", async () => {
    mockFetchRoutes({
      "GET /v1/me": meAdmin,
      "GET /v1/agent-runs/run-1": mockResponse({ detail: "Forbidden" }, 403),
    });
    renderDetail("run-1");
    expect(await screen.findByText("Permission denied")).toBeInTheDocument();
  });
});

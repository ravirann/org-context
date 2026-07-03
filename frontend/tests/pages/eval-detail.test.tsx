import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import EvalDetailPage from "@/pages/eval-detail";

import { evalRunDetail, evalRuns, meAdmin } from "../fixtures-runs";
import { mockFetchRoutes, mockResponse, renderWithProviders } from "../utils";

function renderDetail(id: string) {
  return renderWithProviders(<EvalDetailPage />, {
    route: `/evals/${id}`,
    path: "/evals/:id",
  });
}

describe("EvalDetailPage", () => {
  it("renders header stats with baseline deltas for comparison runs", async () => {
    mockFetchRoutes({
      "GET /v1/me": meAdmin,
      "GET /v1/evals/eval-1": evalRunDetail,
    });
    renderDetail("eval-1");

    const cards = await screen.findByTestId("eval-summary-cards");
    expect(within(cards).getByText("0.86")).toBeInTheDocument();
    expect(within(cards).getByText("baseline 0.71")).toBeInTheDocument();
    // Score delta arrow: +0.15 vs baseline.
    expect(within(cards).getByText("+0.15")).toBeInTheDocument();
    expect(within(cards).getByText("90%")).toBeInTheDocument();
    expect(within(cards).getByText("48.2K")).toBeInTheDocument();
    expect(within(cards).getByText("baseline 90.5K")).toBeInTheDocument();

    // Mode + status badges in the header actions.
    expect(screen.getByText("comparison")).toBeInTheDocument();
    expect(screen.getByText("completed")).toBeInTheDocument();
  });

  it("shows the regression banner listing regressed tasks", async () => {
    mockFetchRoutes({
      "GET /v1/me": meAdmin,
      "GET /v1/evals/eval-1": evalRunDetail,
    });
    renderDetail("eval-1");

    const banner = await screen.findByTestId("regression-banner");
    expect(banner).toHaveTextContent("Regression detected");
    expect(within(banner).getByText("golden-payments-refund")).toBeInTheDocument();
  });

  it("groups results per golden task with paired baseline/context_engine rows", async () => {
    mockFetchRoutes({
      "GET /v1/me": meAdmin,
      "GET /v1/evals/eval-1": evalRunDetail,
    });
    renderDetail("eval-1");

    expect(await screen.findByTestId("eval-results-table")).toBeInTheDocument();
    expect(
      screen.getByTestId("result-row-golden-webhook-dedupe:baseline"),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId("result-row-golden-webhook-dedupe:context_engine"),
    ).toBeInTheDocument();

    // Scores + pass icons per row.
    const ceRow = screen.getByTestId(
      "result-row-golden-webhook-dedupe:context_engine",
    );
    expect(within(ceRow).getByText("0.91")).toBeInTheDocument();
    expect(within(ceRow).getByLabelText("passed")).toBeInTheDocument();

    const failedRow = screen.getByTestId(
      "result-row-golden-payments-refund:context_engine",
    );
    expect(within(failedRow).getByText("0.41")).toBeInTheDocument();
    expect(within(failedRow).getByLabelText("failed")).toBeInTheDocument();

    // Details mini-chips.
    expect(within(failedRow).getByText("P 0.40")).toBeInTheDocument();
    expect(within(failedRow).getByText("R 0.30")).toBeInTheDocument();
    expect(within(failedRow).getByText("kw 1")).toBeInTheDocument();
    expect(within(failedRow).getByText("citations bad")).toBeInTheDocument();
    const passedRow = screen.getByTestId(
      "result-row-golden-webhook-dedupe:baseline",
    );
    expect(within(passedRow).getByText("citations ok")).toBeInTheDocument();
  });

  it("expands failed rows to reveal the explanation panel", async () => {
    mockFetchRoutes({
      "GET /v1/me": meAdmin,
      "GET /v1/evals/eval-1": evalRunDetail,
    });
    const user = userEvent.setup();
    renderDetail("eval-1");
    await screen.findByTestId("eval-results-table");

    // Only failed rows are expandable — a single toggle in this fixture.
    expect(
      screen.queryByTestId(
        "result-explanation-golden-payments-refund:context_engine",
      ),
    ).not.toBeInTheDocument();

    const toggle = screen.getByLabelText(
      "Toggle explanation for golden-payments-refund (context_engine)",
    );
    await user.click(toggle);
    expect(
      screen.getByTestId(
        "result-explanation-golden-payments-refund:context_engine",
      ),
    ).toHaveTextContent("Missed the refund-ledger ADR entirely");

    // Collapses again.
    await user.click(toggle);
    expect(
      screen.queryByTestId(
        "result-explanation-golden-payments-refund:context_engine",
      ),
    ).not.toBeInTheDocument();
  });

  it("omits baseline deltas for single-mode runs", async () => {
    mockFetchRoutes({
      "GET /v1/me": meAdmin,
      "GET /v1/evals/eval-2": { ...evalRuns[1], results: [], golden_tasks_total: 2 },
    });
    renderDetail("eval-2");

    const cards = await screen.findByTestId("eval-summary-cards");
    expect(within(cards).getByText("0.82")).toBeInTheDocument();
    expect(within(cards).queryByText(/baseline/)).not.toBeInTheDocument();
    expect(screen.getByText("No results")).toBeInTheDocument();
    expect(screen.queryByTestId("regression-banner")).not.toBeInTheDocument();
  });

  it("shows a loading skeleton while fetching", () => {
    mockFetchRoutes({
      "GET /v1/me": meAdmin,
      "GET /v1/evals/eval-1": () => new Promise(() => {}),
    });
    renderDetail("eval-1");
    expect(screen.getByTestId("eval-detail-loading")).toBeInTheDocument();
  });

  it("shows a not-found error state on 404", async () => {
    mockFetchRoutes({
      "GET /v1/me": meAdmin,
      "GET /v1/evals/missing": mockResponse({ detail: "Not found" }, 404),
    });
    renderDetail("missing");
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Eval run not found",
    );
  });

  it("shows a retryable error state on server errors and recovers", async () => {
    let calls = 0;
    mockFetchRoutes({
      "GET /v1/me": meAdmin,
      "GET /v1/evals/eval-1": () => {
        calls += 1;
        return calls === 1
          ? mockResponse({ detail: "boom" }, 500)
          : evalRunDetail;
      },
    });
    const user = userEvent.setup();
    renderDetail("eval-1");

    expect(await screen.findByText("boom")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByTestId("eval-results-table")).toBeInTheDocument();
  });

  it("renders PermissionDenied on 403", async () => {
    mockFetchRoutes({
      "GET /v1/me": meAdmin,
      "GET /v1/evals/eval-1": mockResponse({ detail: "Forbidden" }, 403),
    });
    renderDetail("eval-1");
    expect(await screen.findByText("Permission denied")).toBeInTheDocument();
  });
});

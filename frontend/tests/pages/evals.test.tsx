import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useLocation } from "react-router-dom";
import { beforeEach, describe, expect, it, type Mock } from "vitest";

import { useToastStore } from "@/components/ui/toast";
import EvalsPage from "@/pages/evals";

import { evalRuns, evalRunsPage, goldenTasks, meAdmin, paginate } from "../fixtures-runs";
import { mockFetchRoutes, mockResponse, renderWithProviders } from "../utils";

function LocationProbe() {
  const location = useLocation();
  return <div data-testid="location">{location.pathname + location.search}</div>;
}

function postRunCalls(fetchMock: Mock) {
  return fetchMock.mock.calls.filter(([input, init]) => {
    const url = String(input instanceof Request ? input.url : input);
    return url.includes("/v1/evals/run") && init?.method === "POST";
  });
}

const baseRoutes = {
  "GET /v1/me": meAdmin,
  "GET /v1/evals": evalRunsPage,
  "GET /v1/evals/golden-tasks": goldenTasks,
};

beforeEach(() => {
  useToastStore.setState({ toasts: [] });
});

describe("EvalsPage", () => {
  it("renders the latest-run summary, history and golden tasks", async () => {
    mockFetchRoutes(baseRoutes);
    renderWithProviders(<EvalsPage />, { route: "/evals" });

    // Latest run summary cards.
    const summary = await screen.findByTestId("latest-run-summary");
    expect(within(summary).getByText("0.86")).toBeInTheDocument();
    expect(within(summary).getByText("90%")).toBeInTheDocument();
    expect(screen.getByTestId("regression-badge")).toBeInTheDocument();
    // Regressed task names live in the tooltip.
    expect(
      within(summary).getByText("golden-payments-refund", { exact: false }),
    ).toBeInTheDocument();
    // Token comparison is formatted.
    expect(
      within(summary).getByText(/baseline 90.5K vs context engine 48.2K/),
    ).toBeInTheDocument();

    // History table rows with mode/status/score/regression indicator.
    const history = screen.getByTestId("eval-history-table");
    expect(screen.getByTestId("eval-row-eval-1")).toBeInTheDocument();
    expect(screen.getByTestId("eval-row-eval-2")).toBeInTheDocument();
    expect(screen.getByTestId("eval-row-eval-3")).toBeInTheDocument();
    expect(within(history).getByText("comparison")).toBeInTheDocument();
    expect(within(history).getByText("baseline")).toBeInTheDocument();
    expect(within(history).getByText("running")).toBeInTheDocument();
    expect(within(history).getByLabelText("regression")).toBeInTheDocument();

    // Score trend chart container renders.
    expect(screen.getByTestId("score-trend-chart")).toBeInTheDocument();

    // Golden tasks table.
    const golden = screen.getByTestId("golden-tasks-table");
    expect(within(golden).getByText("golden-webhook-dedupe")).toBeInTheDocument();
    expect(within(golden).getByText("idempotency")).toBeInTheDocument();
    expect(within(golden).getByText("active")).toBeInTheDocument();
    expect(within(golden).getByText("inactive")).toBeInTheDocument();
  });

  it("queues an eval run with the selected mode and toasts", async () => {
    const fetchMock = mockFetchRoutes({
      ...baseRoutes,
      "POST /v1/evals/run": { eval_run_id: "eval-9", status: "queued" },
    });
    const user = userEvent.setup();
    renderWithProviders(<EvalsPage />, { route: "/evals" });
    await screen.findByTestId("eval-history-table");

    // Default mode is comparison.
    expect(screen.getByLabelText("Eval mode")).toHaveValue("comparison");
    await user.click(screen.getByRole("button", { name: /Run eval/ }));

    await waitFor(() => {
      expect(postRunCalls(fetchMock)).toHaveLength(1);
    });
    const [, init] = postRunCalls(fetchMock)[0];
    expect(JSON.parse(String(init?.body))).toEqual({ mode: "comparison" });
    await waitFor(() => {
      expect(
        useToastStore.getState().toasts.some((t) => t.title === "Eval queued"),
      ).toBe(true);
    });

    // Switching mode changes the POST body.
    await user.selectOptions(screen.getByLabelText("Eval mode"), "baseline");
    await user.click(screen.getByRole("button", { name: /Run eval/ }));
    await waitFor(() => {
      expect(postRunCalls(fetchMock)).toHaveLength(2);
    });
    const [, second] = postRunCalls(fetchMock)[1];
    expect(JSON.parse(String(second?.body))).toEqual({ mode: "baseline" });
  });

  it("disables the run button while the request is pending", async () => {
    mockFetchRoutes({
      ...baseRoutes,
      "POST /v1/evals/run": () =>
        new Promise((resolve) =>
          setTimeout(() => resolve({ eval_run_id: "e", status: "queued" }), 40),
        ),
    });
    const user = userEvent.setup();
    renderWithProviders(<EvalsPage />, { route: "/evals" });
    await screen.findByTestId("eval-history-table");

    const button = screen.getByRole("button", { name: /Run eval/ });
    await user.click(button);
    expect(button).toBeDisabled();
    await waitFor(() => {
      expect(button).toBeEnabled();
    });
  });

  it("toasts an error when queueing is forbidden", async () => {
    mockFetchRoutes({
      ...baseRoutes,
      "POST /v1/evals/run": mockResponse({ detail: "Forbidden" }, 403),
    });
    const user = userEvent.setup();
    renderWithProviders(<EvalsPage />, { route: "/evals" });
    await screen.findByTestId("eval-history-table");

    await user.click(screen.getByRole("button", { name: /Run eval/ }));
    await waitFor(() => {
      expect(
        useToastStore.getState().toasts.some((t) => t.title === "Requires admin"),
      ).toBe(true);
    });
  });

  it("navigates to the run detail on history row click", async () => {
    mockFetchRoutes(baseRoutes);
    const user = userEvent.setup();
    renderWithProviders(
      <>
        <EvalsPage />
        <LocationProbe />
      </>,
      { route: "/evals" },
    );

    await user.click(await screen.findByTestId("eval-row-eval-1"));
    expect(screen.getByTestId("location")).toHaveTextContent("/evals/eval-1");
  });

  it("shows loading skeletons while pending", () => {
    mockFetchRoutes({
      "GET /v1/me": meAdmin,
      "GET /v1/evals": () => new Promise(() => {}),
      "GET /v1/evals/golden-tasks": () => new Promise(() => {}),
    });
    renderWithProviders(<EvalsPage />, { route: "/evals" });
    expect(screen.getByTestId("evals-loading")).toBeInTheDocument();
    expect(screen.getByTestId("golden-tasks-loading")).toBeInTheDocument();
  });

  it("shows an error state and recovers on retry", async () => {
    let calls = 0;
    mockFetchRoutes({
      ...baseRoutes,
      "GET /v1/evals": () => {
        calls += 1;
        return calls === 1 ? mockResponse({ detail: "boom" }, 500) : evalRunsPage;
      },
    });
    const user = userEvent.setup();
    renderWithProviders(<EvalsPage />, { route: "/evals" });

    expect(await screen.findByText("boom")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByTestId("eval-history-table")).toBeInTheDocument();
  });

  it("shows an empty state when there are no runs", async () => {
    mockFetchRoutes({
      ...baseRoutes,
      "GET /v1/evals": paginate<(typeof evalRuns)[number]>([]),
    });
    renderWithProviders(<EvalsPage />, { route: "/evals" });
    expect(await screen.findByText("No eval runs yet")).toBeInTheDocument();
  });

  it("renders PermissionDenied on 403", async () => {
    mockFetchRoutes({
      ...baseRoutes,
      "GET /v1/evals": mockResponse({ detail: "Forbidden" }, 403),
    });
    renderWithProviders(<EvalsPage />, { route: "/evals" });
    expect(await screen.findByText("Permission denied")).toBeInTheDocument();
  });
});

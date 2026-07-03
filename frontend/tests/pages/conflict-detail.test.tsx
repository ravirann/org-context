import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";

import { useToastStore } from "@/components/ui/toast";
import ConflictDetailPage from "@/pages/conflict-detail";

import {
  conflictDetailNoRecommendation,
  conflictDetailOpen,
  conflictDetailResolved,
  conflictDocA,
  conflictDocB,
  meAdmin,
  meViewer,
} from "../fixtures-admin";
import { mockFetchRoutes, mockResponse, renderWithProviders } from "../utils";

const ROUTE = { route: `/conflicts/${conflictDetailOpen.id}`, path: "/conflicts/:id" };
const GET_KEY = `GET /v1/conflicts/${conflictDetailOpen.id}`;

function toastTitles(): string[] {
  return useToastStore.getState().toasts.map((t) => t.title);
}

beforeEach(() => {
  useToastStore.setState({ toasts: [] });
});

describe("ConflictDetailPage", () => {
  it("renders the comparison grid and highlights the API-recommended document", async () => {
    mockFetchRoutes({
      "GET /v1/me": meAdmin,
      [GET_KEY]: conflictDetailOpen,
    });
    renderWithProviders(<ConflictDetailPage />, ROUTE);

    expect(await screen.findByText(conflictDetailOpen.title)).toBeInTheDocument();
    expect(screen.getByText(conflictDetailOpen.topic_key)).toBeInTheDocument();
    expect(screen.getByText("open")).toBeInTheDocument();

    const cardA = screen.getByTestId(`conflict-doc-${conflictDocA.id}`);
    const cardB = screen.getByTestId(`conflict-doc-${conflictDocB.id}`);
    expect(within(cardA).getByText("Recommended source of truth")).toBeInTheDocument();
    expect(
      within(cardB).queryByText("Recommended source of truth"),
    ).not.toBeInTheDocument();
    expect(within(cardB).getByText("GitHub")).toBeInTheDocument();

    const openLinks = screen.getAllByRole("link", { name: /Open document/ });
    expect(openLinks[0]).toHaveAttribute(
      "href",
      `/explorer/documents/${conflictDocA.id}`,
    );
  });

  it("computes the recommendation client-side when the API returns null", async () => {
    mockFetchRoutes({
      "GET /v1/me": meAdmin,
      [GET_KEY]: conflictDetailNoRecommendation,
    });
    renderWithProviders(<ConflictDetailPage />, ROUTE);

    // doc B: 0.95 × 0.85 = 0.81 beats doc A: 0.35 × 0.9 = 0.32.
    const cardB = await screen.findByTestId(`conflict-doc-${conflictDocB.id}`);
    expect(within(cardB).getByText("Recommended source of truth")).toBeInTheDocument();
    const cardA = screen.getByTestId(`conflict-doc-${conflictDocA.id}`);
    expect(
      within(cardA).queryByText("Recommended source of truth"),
    ).not.toBeInTheDocument();
  });

  it("requires a resolution note before posting", async () => {
    const fetchMock = mockFetchRoutes({
      "GET /v1/me": meAdmin,
      [GET_KEY]: conflictDetailOpen,
    });
    renderWithProviders(<ConflictDetailPage />, ROUTE);

    await screen.findByTestId("resolution-form");
    await userEvent.click(screen.getByRole("button", { name: "Resolve conflict" }));

    expect(
      await screen.findByText("A resolution note is required."),
    ).toBeInTheDocument();
    const posts = fetchMock.mock.calls.filter(
      ([, init]) => init?.method === "POST",
    );
    expect(posts).toHaveLength(0);
  });

  it("posts the selected document, note and ADR url on resolve", async () => {
    const fetchMock = mockFetchRoutes({
      "GET /v1/me": meAdmin,
      [GET_KEY]: conflictDetailOpen,
      [`POST /v1/conflicts/${conflictDetailOpen.id}/resolve`]: conflictDetailResolved,
    });
    renderWithProviders(<ConflictDetailPage />, ROUTE);

    await screen.findByTestId("resolution-form");

    // The recommended doc (A) is preselected; pick B instead.
    const cardB = screen.getByTestId(`conflict-doc-${conflictDocB.id}`);
    await userEvent.click(within(cardB).getByRole("radio"));

    await userEvent.type(
      screen.getByLabelText(/Resolution note/),
      "ADR-118 wins; the runbook predates the backoff decision.",
    );
    await userEvent.type(
      screen.getByLabelText(/Linked ADR/),
      "https://github.com/org/payments-api/blob/main/docs/adr/118.md",
    );
    await userEvent.click(screen.getByRole("button", { name: "Resolve conflict" }));

    await waitFor(() => {
      expect(toastTitles()).toContain("Conflict resolved");
    });
    const post = fetchMock.mock.calls.find(([, init]) => init?.method === "POST");
    expect(post).toBeDefined();
    expect(String(post![0])).toContain(
      `/v1/conflicts/${conflictDetailOpen.id}/resolve`,
    );
    expect(JSON.parse(String(post![1]!.body))).toEqual({
      recommended_document_id: conflictDocB.id,
      note: "ADR-118 wins; the runbook predates the backoff decision.",
      linked_adr_url: "https://github.com/org/payments-api/blob/main/docs/adr/118.md",
    });
  });

  it("disables the resolve form for viewers with a role hint", async () => {
    mockFetchRoutes({
      "GET /v1/me": meViewer,
      [GET_KEY]: conflictDetailOpen,
    });
    renderWithProviders(<ConflictDetailPage />, ROUTE);

    await screen.findByTestId("resolution-form");
    expect(screen.getByLabelText(/Resolution note/)).toBeDisabled();
    expect(screen.getByRole("button", { name: "Resolve conflict" })).toBeDisabled();
    expect(
      screen.getByText(/Only admins and leads can resolve conflicts/),
    ).toBeInTheDocument();
    // Viewers get no selection radios.
    expect(screen.queryAllByRole("radio")).toHaveLength(0);
  });

  it("shows the resolution summary for resolved conflicts", async () => {
    mockFetchRoutes({
      "GET /v1/me": meAdmin,
      [GET_KEY]: conflictDetailResolved,
    });
    renderWithProviders(<ConflictDetailPage />, ROUTE);

    const summary = await screen.findByTestId("resolution-summary");
    expect(within(summary).getByText(/ADR-118 wins/)).toBeInTheDocument();
    expect(within(summary).getByText(/Lena Lead/)).toBeInTheDocument();
    expect(
      within(summary).getByRole("link", { name: /Linked ADR \/ document/ }),
    ).toHaveAttribute("href", conflictDetailResolved.linked_adr_url);
    expect(screen.queryByTestId("resolution-form")).not.toBeInTheDocument();
  });

  it("shows loading skeletons while fetching", async () => {
    mockFetchRoutes({
      "GET /v1/me": meAdmin,
      [GET_KEY]: conflictDetailOpen,
    });
    renderWithProviders(<ConflictDetailPage />, ROUTE);

    expect(screen.getByTestId("conflict-detail-loading")).toBeInTheDocument();
    expect(await screen.findByTestId("resolution-form")).toBeInTheDocument();
  });

  it("shows an error state with retry", async () => {
    let calls = 0;
    mockFetchRoutes({
      "GET /v1/me": meAdmin,
      [GET_KEY]: () => {
        calls += 1;
        return calls === 1
          ? mockResponse({ detail: "broken" }, 500)
          : conflictDetailOpen;
      },
    });
    renderWithProviders(<ConflictDetailPage />, ROUTE);

    expect(await screen.findByText("broken")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByText(conflictDetailOpen.title)).toBeInTheDocument();
  });

  it("renders PermissionDenied on 403", async () => {
    mockFetchRoutes({
      "GET /v1/me": meViewer,
      [GET_KEY]: mockResponse({ detail: "Forbidden" }, 403),
    });
    renderWithProviders(<ConflictDetailPage />, ROUTE);

    expect(await screen.findByText("Permission denied")).toBeInTheDocument();
  });
});

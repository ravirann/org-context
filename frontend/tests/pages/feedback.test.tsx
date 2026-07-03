import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";

import { useToastStore } from "@/components/ui/toast";
import FeedbackPage from "@/pages/feedback";

import { mockFetchRoutes, mockResponse, renderWithProviders } from "../utils";

function toastTitles(): string[] {
  return useToastStore.getState().toasts.map((t) => t.title);
}

function typeSelect(): HTMLSelectElement {
  return screen.getByLabelText("Feedback type") as HTMLSelectElement;
}

beforeEach(() => {
  useToastStore.setState({ toasts: [] });
});

describe("FeedbackPage", () => {
  it("renders the form with all eight feedback types and quick actions", () => {
    mockFetchRoutes({});
    renderWithProviders(<FeedbackPage />, { route: "/feedback" });

    expect(screen.getByTestId("page-feedback")).toBeInTheDocument();
    const options = screen.getAllByRole("option");
    expect(options).toHaveLength(8);
    expect(options.map((o) => (o as HTMLOptionElement).value)).toEqual([
      "useful",
      "irrelevant",
      "missing_context",
      "stale_context",
      "permission_issue",
      "suggest_source",
      "promote_authoritative",
      "mark_deprecated",
    ]);
    expect(
      screen.getByRole("button", { name: /Report missing context/ }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Mark source as deprecated/ }),
    ).toBeInTheDocument();
  });

  it("blocks submission without a target and does not POST", async () => {
    const fetchMock = mockFetchRoutes({ "POST /v1/feedback": {} });
    renderWithProviders(<FeedbackPage />, { route: "/feedback" });

    await userEvent.click(screen.getByRole("button", { name: /Submit feedback/ }));

    expect(
      await screen.findByText(
        "Provide a context packet ID or a document ID (at least one).",
      ),
    ).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("pre-selects the type when a quick action is clicked", async () => {
    mockFetchRoutes({});
    renderWithProviders(<FeedbackPage />, { route: "/feedback" });

    expect(typeSelect().value).toBe("useful");

    const cases: Array<[RegExp, string]> = [
      [/Report missing context/, "missing_context"],
      [/Report stale context/, "stale_context"],
      [/Report permission issue/, "permission_issue"],
      [/Promote source as authoritative/, "promote_authoritative"],
      [/Mark source as deprecated/, "mark_deprecated"],
    ];
    for (const [name, value] of cases) {
      await userEvent.click(screen.getByRole("button", { name }));
      expect(typeSelect().value).toBe(value);
    }
    // The last quick action targets the document field.
    expect(screen.getByLabelText("Document ID")).toHaveFocus();
  });

  it("posts the feedback and resets the form on success", async () => {
    const fetchMock = mockFetchRoutes({
      "POST /v1/feedback": mockResponse(
        {
          id: "f-1",
          type: "stale_context",
          context_packet_id: null,
          document_id: "d0000000-0000-4000-8000-00000000000a",
          comment: "Retry policy changed in ADR-118",
          user_name: "Ava Admin",
          created_at: "2026-07-03T10:00:00Z",
        },
        201,
      ),
    });
    renderWithProviders(<FeedbackPage />, { route: "/feedback" });

    await userEvent.selectOptions(typeSelect(), "stale_context");
    await userEvent.type(
      screen.getByLabelText("Document ID"),
      "d0000000-0000-4000-8000-00000000000a",
    );
    await userEvent.type(
      screen.getByLabelText(/Comment/),
      "Retry policy changed in ADR-118",
    );
    await userEvent.click(screen.getByRole("button", { name: /Submit feedback/ }));

    await waitFor(() => {
      expect(toastTitles()).toContain("Feedback submitted");
    });

    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toContain("/v1/feedback");
    expect(init?.method).toBe("POST");
    expect(JSON.parse(String(init?.body))).toEqual({
      type: "stale_context",
      document_id: "d0000000-0000-4000-8000-00000000000a",
      comment: "Retry policy changed in ADR-118",
    });

    // Form resets.
    expect(typeSelect().value).toBe("useful");
    expect(screen.getByLabelText("Document ID")).toHaveValue("");
    expect(screen.getByLabelText(/Comment/)).toHaveValue("");
  });

  it("shows an error toast when the POST fails", async () => {
    mockFetchRoutes({
      "POST /v1/feedback": mockResponse({ detail: "Forbidden" }, 403),
    });
    renderWithProviders(<FeedbackPage />, { route: "/feedback" });

    await userEvent.type(screen.getByLabelText("Context packet ID"), "p-123");
    await userEvent.click(screen.getByRole("button", { name: /Submit feedback/ }));

    await waitFor(() => {
      expect(toastTitles()).toContain("Failed to submit feedback");
    });
    expect(
      useToastStore
        .getState()
        .toasts.some((t) => t.description === "Forbidden" && t.variant === "error"),
    ).toBe(true);
  });
});

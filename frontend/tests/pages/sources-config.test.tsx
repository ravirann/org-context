import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, type Mock } from "vitest";

import { useToastStore } from "@/components/ui/toast";
import SourcesPage from "@/pages/sources";

import { meAdmin, meEngineer, sources, sourcesResponse } from "../fixtures-runs";
import { mockFetchRoutes, renderWithProviders } from "../utils";

function callsFor(fetchMock: Mock, method: string, urlPart: string) {
  return fetchMock.mock.calls.filter(([input, init]) => {
    const url = String(input instanceof Request ? input.url : input);
    return url.includes(urlPart) && (init?.method ?? "GET") === method;
  });
}

function bodyOf(call: unknown[]): unknown {
  const init = call[1] as RequestInit | undefined;
  return init?.body ? JSON.parse(String(init.body)) : undefined;
}

const baseRoutes = {
  "GET /v1/me": meAdmin,
  "GET /v1/sources": sourcesResponse,
};

beforeEach(() => {
  useToastStore.setState({ toasts: [] });
});

describe("SourcesPage — configure dialog", () => {
  it("opens the config dialog prefilled from source.config, masked secret shown as-is", async () => {
    mockFetchRoutes(baseRoutes);
    const user = userEvent.setup();
    renderWithProviders(<SourcesPage />, { route: "/sources" });
    await screen.findByTestId("sources-table");

    await user.click(screen.getByLabelText("Configure backend monorepo"));
    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getByLabelText("Config mode")).toHaveValue("live");
    expect(within(dialog).getByLabelText("Token")).toHaveValue("•••7a2c");
    expect(within(dialog).getByLabelText("Org")).toHaveValue("example-org");
    expect(within(dialog).getByLabelText("Repos")).toHaveValue("backend, shared-libs");
    expect(within(dialog).getByText("unchanged unless replaced")).toBeInTheDocument();

    // Sync cursors shown in the footer area.
    expect(within(dialog).getByText(/pr_cursor/)).toBeInTheDocument();
    expect(within(dialog).getByText(/2026-07-01T00:00:00Z/)).toBeInTheDocument();
  });

  it("saves with the masked secret untouched when the user doesn't replace it", async () => {
    const fetchMock = mockFetchRoutes({
      ...baseRoutes,
      "PATCH /v1/sources/src-1": sources[0],
    });
    const user = userEvent.setup();
    renderWithProviders(<SourcesPage />, { route: "/sources" });
    await screen.findByTestId("sources-table");

    await user.click(screen.getByLabelText("Configure backend monorepo"));
    const dialog = screen.getByRole("dialog");
    await user.click(within(dialog).getByRole("button", { name: "Save" }));

    await waitFor(() => {
      expect(callsFor(fetchMock, "PATCH", "/v1/sources/src-1")).toHaveLength(1);
    });
    const body = bodyOf(callsFor(fetchMock, "PATCH", "/v1/sources/src-1")[0]) as {
      config: Record<string, unknown>;
    };
    expect(body.config.token).toBe("•••7a2c");
    expect(body.config.mode).toBe("live");
    expect(body.config.org).toBe("example-org");
    expect(body.config.repos).toEqual(["backend", "shared-libs"]);
  });

  it("replaces the secret with a new value when the user types one", async () => {
    const fetchMock = mockFetchRoutes({
      ...baseRoutes,
      "PATCH /v1/sources/src-1": sources[0],
    });
    const user = userEvent.setup();
    renderWithProviders(<SourcesPage />, { route: "/sources" });
    await screen.findByTestId("sources-table");

    await user.click(screen.getByLabelText("Configure backend monorepo"));
    const dialog = screen.getByRole("dialog");
    const tokenInput = within(dialog).getByLabelText("Token");
    await user.clear(tokenInput);
    await user.type(tokenInput, "ghp_brandnewtoken123");
    await user.click(within(dialog).getByRole("button", { name: "Save" }));

    await waitFor(() => {
      expect(callsFor(fetchMock, "PATCH", "/v1/sources/src-1")).toHaveLength(1);
    });
    const body = bodyOf(callsFor(fetchMock, "PATCH", "/v1/sources/src-1")[0]) as {
      config: Record<string, unknown>;
    };
    expect(body.config.token).toBe("ghp_brandnewtoken123");
    await waitFor(() => {
      expect(
        useToastStore.getState().toasts.some((t) => t.title === "Source configuration saved"),
      ).toBe(true);
    });
  });

  it("switches the field set when the mode toggle changes to demo", async () => {
    mockFetchRoutes(baseRoutes);
    const user = userEvent.setup();
    renderWithProviders(<SourcesPage />, { route: "/sources" });
    await screen.findByTestId("sources-table");

    await user.click(screen.getByLabelText("Configure backend monorepo"));
    const dialog = screen.getByRole("dialog");
    expect(within(dialog).queryByLabelText("Token")).toBeInTheDocument();

    await user.selectOptions(within(dialog).getByLabelText("Config mode"), "demo");
    expect(within(dialog).queryByLabelText("Token")).not.toBeInTheDocument();
    expect(within(dialog).queryByLabelText("Org")).not.toBeInTheDocument();
  });

  it("shows the jira field set for a jira source in live mode", async () => {
    mockFetchRoutes(baseRoutes);
    const user = userEvent.setup();
    renderWithProviders(<SourcesPage />, { route: "/sources" });
    await screen.findByTestId("sources-table");

    await user.click(screen.getByLabelText("Configure payments board"));
    const dialog = screen.getByRole("dialog");
    await user.selectOptions(within(dialog).getByLabelText("Config mode"), "live");
    expect(within(dialog).getByLabelText("Base URL")).toBeInTheDocument();
    expect(within(dialog).getByLabelText("API token")).toBeInTheDocument();
    expect(within(dialog).getByLabelText("JQL")).toBeInTheDocument();
  });

  it("is read-only for a non-admin (engineer) viewer", async () => {
    mockFetchRoutes({ "GET /v1/me": meEngineer, "GET /v1/sources": sourcesResponse });
    const user = userEvent.setup();
    renderWithProviders(<SourcesPage />, { route: "/sources" });
    await screen.findByTestId("sources-table");

    await user.click(screen.getByLabelText("Configure backend monorepo"));
    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getByLabelText("Config mode")).toBeDisabled();
    expect(within(dialog).getByLabelText("Token")).toBeDisabled();
    expect(within(dialog).queryByRole("button", { name: "Save" })).not.toBeInTheDocument();
    expect(
      within(dialog).getByRole("button", { name: "Close configuration dialog" }),
    ).toBeInTheDocument();
  });
});

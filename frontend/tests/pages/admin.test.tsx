import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";

import { useToastStore } from "@/components/ui/toast";
import AdminPage from "@/pages/admin";

import {
  adminApiKeysFixture,
  adminTeamsFixture,
  adminUsersFixture,
  auditLogsFixture,
  meAdmin,
  meViewer,
  paginated,
  settingsFixture,
  systemInfoFixture,
} from "../fixtures-admin";
import { mockFetchRoutes, mockResponse, renderWithProviders } from "../utils";

const ADMIN_ROUTES = {
  "GET /v1/me": meAdmin,
  "GET /v1/admin/users": adminUsersFixture,
  "GET /v1/admin/teams": adminTeamsFixture,
  "GET /v1/admin/api-keys": adminApiKeysFixture,
  "GET /v1/admin/audit-logs": auditLogsFixture,
  "GET /v1/settings": settingsFixture,
  "PATCH /v1/settings": settingsFixture,
};

function toastTitles(): string[] {
  return useToastStore.getState().toasts.map((t) => t.title);
}

beforeEach(() => {
  useToastStore.setState({ toasts: [] });
});

describe("AdminPage", () => {
  it("renders PermissionDenied for viewers without firing admin requests", async () => {
    const fetchMock = mockFetchRoutes({ "GET /v1/me": meViewer });
    renderWithProviders(<AdminPage />, { route: "/admin" });

    expect(await screen.findByText("Permission denied")).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent("viewer");
    expect(fetchMock.mock.calls.length).toBeGreaterThan(0);
    for (const call of fetchMock.mock.calls) {
      expect(String(call[0])).toContain("/v1/me");
    }
    expect(screen.queryByRole("tab")).not.toBeInTheDocument();
  });

  it("shows a loading skeleton while resolving the role", () => {
    mockFetchRoutes({ "GET /v1/me": meAdmin });
    renderWithProviders(<AdminPage />, { route: "/admin" });

    expect(screen.getByTestId("admin-loading")).toBeInTheDocument();
  });

  it("shows an error state when /v1/me fails", async () => {
    mockFetchRoutes({ "GET /v1/me": mockResponse({ detail: "who are you" }, 500) });
    renderWithProviders(<AdminPage />, { route: "/admin" });

    expect(await screen.findByText("who are you")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });

  it("renders the Users tab by default with roles and status", async () => {
    mockFetchRoutes(ADMIN_ROUTES);
    renderWithProviders(<AdminPage />, { route: "/admin" });

    const table = await screen.findByTestId("admin-users-table");
    expect(within(table).getByText("ava@example.com")).toBeInTheDocument();
    expect(within(table).getByLabelText("Role for ava@example.com")).toHaveValue("admin");
    expect(within(table).getByLabelText("Role for lena@example.com")).toHaveValue("lead");
    expect(within(table).getByLabelText("Role for eli@example.com")).toHaveValue(
      "engineer",
    );
    expect(within(table).getByText("inactive")).toBeInTheDocument();
    expect(within(table).getAllByText("active")).toHaveLength(2);
    expect(screen.getByTestId("page-admin")).toBeInTheDocument();
  });

  it("renders the Teams tab", async () => {
    mockFetchRoutes(ADMIN_ROUTES);
    renderWithProviders(<AdminPage />, { route: "/admin" });

    await userEvent.click(await screen.findByRole("tab", { name: "Teams" }));

    const table = await screen.findByTestId("admin-teams-table");
    expect(within(table).getByDisplayValue("Platform")).toBeInTheDocument();
    expect(within(table).getByText("11")).toBeInTheDocument();
  });

  it("renders the API keys tab with the never-displayed callout", async () => {
    mockFetchRoutes(ADMIN_ROUTES);
    renderWithProviders(<AdminPage />, { route: "/admin" });

    await userEvent.click(await screen.findByRole("tab", { name: "API keys" }));

    const table = await screen.findByTestId("admin-api-keys-table");
    expect(within(table).getByText("ava-cli")).toBeInTheDocument();
    expect(within(table).getByText("mcp")).toBeInTheDocument();
    expect(within(table).getByText("never")).toBeInTheDocument();
    expect(screen.getByText(/shown only once, right after creation/)).toBeInTheDocument();
  });

  it("warns when retrieval weights do not sum to 1 and saves the PATCH body", async () => {
    const fetchMock = mockFetchRoutes(ADMIN_ROUTES);
    renderWithProviders(<AdminPage />, { route: "/admin" });

    await userEvent.click(await screen.findByRole("tab", { name: "Retrieval" }));
    const vector = await screen.findByRole("spinbutton", { name: "Vector weight" });
    expect(vector).toHaveValue(0.5);
    expect(screen.queryByText(/Weights sum to/)).not.toBeInTheDocument();

    fireEvent.change(vector, { target: { value: "0.9" } });
    expect(await screen.findByText(/Weights sum to 1\.40/)).toBeInTheDocument();

    await userEvent.click(
      screen.getByRole("button", { name: "Save retrieval settings" }),
    );

    await waitFor(() => {
      expect(toastTitles()).toContain("Retrieval settings saved");
    });
    const patch = fetchMock.mock.calls.find(([, init]) => init?.method === "PATCH");
    expect(patch).toBeDefined();
    expect(String(patch![0])).toContain("/v1/settings");
    expect(JSON.parse(String(patch![1]!.body))).toEqual({
      retrieval_weights: { vector: 0.9, fts: 0.2, freshness: 0.15, authority: 0.15 },
      token_budget: { max_packet_tokens: 6000 },
    });
  });

  it("adds and removes PII patterns and saves the section", async () => {
    const fetchMock = mockFetchRoutes(ADMIN_ROUTES);
    renderWithProviders(<AdminPage />, { route: "/admin" });

    await userEvent.click(await screen.findByRole("tab", { name: "Rules" }));
    const pii = await screen.findByTestId("rules-pii");

    // Remove the seeded pattern.
    await userEvent.click(within(pii).getByRole("button", { name: /Remove pattern/ }));
    expect(within(pii).queryByRole("button", { name: /Remove pattern/ })).toBeNull();
    expect(within(pii).getByText("No patterns configured.")).toBeInTheDocument();

    // Add a new one.
    await userEvent.type(within(pii).getByLabelText("New PII pattern"), "secret-key");
    await userEvent.click(within(pii).getByRole("button", { name: "Add" }));
    expect(within(pii).getByText("secret-key")).toBeInTheDocument();

    await userEvent.click(
      within(pii).getByRole("button", { name: "Save pii redaction" }),
    );

    await waitFor(() => {
      expect(toastTitles()).toContain("PII redaction saved");
    });
    const patch = fetchMock.mock.calls.find(([, init]) => init?.method === "PATCH");
    expect(JSON.parse(String(patch![1]!.body))).toEqual({
      pii_redaction: { enabled: true, patterns: ["secret-key"] },
    });
  });

  it("renders rules sections with authority ranks and feature flags", async () => {
    mockFetchRoutes(ADMIN_ROUTES);
    renderWithProviders(<AdminPage />, { route: "/admin" });

    await userEvent.click(await screen.findByRole("tab", { name: "Rules" }));

    const authority = await screen.findByTestId("rules-authority");
    expect(within(authority).getByText("adr")).toBeInTheDocument();
    expect(within(authority).getByRole("spinbutton", { name: "Rank for adr" })).toHaveValue(
      100,
    );
    const flags = screen.getByTestId("rules-flags");
    expect(within(flags).getByLabelText("Toggle graph_v2")).toBeChecked();
    expect(within(flags).getByLabelText("Toggle conflict_auto_resolve")).not.toBeChecked();
    expect(screen.getByTestId("rules-evals")).toBeInTheDocument();
    expect(screen.getByTestId("rules-retention")).toBeInTheDocument();
  });

  it("filters the audit log by action and expands the JSON detail", async () => {
    const fetchMock = mockFetchRoutes({
      ...ADMIN_ROUTES,
      "GET /v1/admin/audit-logs": (url: URL) =>
        url.searchParams.get("action")
          ? paginated([auditLogsFixture.items[1]])
          : auditLogsFixture,
    });
    renderWithProviders(<AdminPage />, { route: "/admin" });

    await userEvent.click(await screen.findByRole("tab", { name: "Audit log" }));
    const table = await screen.findByTestId("admin-audit-table");
    expect(within(table).getByText("settings.update")).toBeInTheDocument();

    // Expand the detail row.
    await userEvent.click(
      within(table).getByRole("button", { name: "Toggle detail for settings.update" }),
    );
    expect(within(table).getByText(/retrieval_weights/)).toBeInTheDocument();

    // Filter (debounced).
    await userEvent.type(screen.getByLabelText("Filter by action"), "source");
    await waitFor(() => {
      const urls = fetchMock.mock.calls.map((call) => String(call[0]));
      expect(urls.some((u) => u.includes("action=source"))).toBe(true);
    });
    expect(await screen.findByText("source.sync")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.queryByText("settings.update")).not.toBeInTheDocument();
    });
  });

  it("renders the read-only System tab", async () => {
    mockFetchRoutes({ ...ADMIN_ROUTES, "GET /v1/system/info": systemInfoFixture });
    renderWithProviders(<AdminPage />, { route: "/admin" });

    await userEvent.click(await screen.findByRole("tab", { name: "System" }));

    const runtime = await screen.findByTestId("system-runtime-card");
    expect(within(runtime).getByText(/text-embedding-3-small/)).toBeInTheDocument();
    expect(within(runtime).getByText("oidc")).toBeInTheDocument();
    expect(within(runtime).getByText("3")).toBeInTheDocument();
    expect(within(runtime).getByText("0.3.0")).toBeInTheDocument();

    const json = await screen.findByTestId("system-settings-json");
    expect(json).toHaveTextContent('"max_packet_tokens": 6000');
    expect(screen.getByText("demo-mcp-token")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /\/docs/ })).toHaveAttribute(
      "href",
      "http://localhost:8000/docs",
    );
  });

  it("shows PermissionDenied inside a tab when the endpoint 403s", async () => {
    mockFetchRoutes({
      ...ADMIN_ROUTES,
      "GET /v1/admin/users": mockResponse({ detail: "Forbidden" }, 403),
    });
    renderWithProviders(<AdminPage />, { route: "/admin" });

    expect(await screen.findByText("Permission denied")).toBeInTheDocument();
    // The page chrome (tabs) is still there — only the tab body is blocked.
    expect(screen.getByRole("tab", { name: "Users" })).toBeInTheDocument();
  });

  it("shows an error state with retry inside a tab", async () => {
    let calls = 0;
    mockFetchRoutes({
      ...ADMIN_ROUTES,
      "GET /v1/admin/users": () => {
        calls += 1;
        return calls === 1
          ? mockResponse({ detail: "users broke" }, 500)
          : adminUsersFixture;
      },
    });
    renderWithProviders(<AdminPage />, { route: "/admin" });

    expect(await screen.findByText("users broke")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByTestId("admin-users-table")).toBeInTheDocument();
  });
});

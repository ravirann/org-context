import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi, type Mock } from "vitest";

import { useToastStore } from "@/components/ui/toast";
import AdminPage from "@/pages/admin";

import {
  adminApiKeysFixture,
  adminTeamsFixture,
  adminUsersFixture,
  auditLogsFixture,
  meAdmin,
  settingsFixture,
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

function bodyOf(call: unknown[]): unknown {
  const init = call[1] as RequestInit | undefined;
  return init?.body ? JSON.parse(String(init.body)) : undefined;
}

function callsFor(fetchMock: Mock, method: string, urlPart: string) {
  return fetchMock.mock.calls.filter(([input, init]) => {
    const url = String(input instanceof Request ? input.url : input);
    return url.includes(urlPart) && (init?.method ?? "GET") === method;
  });
}

beforeEach(() => {
  useToastStore.setState({ toasts: [] });
});

describe("Admin — Users tab CRUD", () => {
  it("adds a user through the dialog and refetches the list", async () => {
    const fetchMock = mockFetchRoutes({
      ...ADMIN_ROUTES,
      "POST /v1/admin/users": {
        id: "u-new",
        email: "new@example.com",
        name: "New Person",
        role: "engineer",
        team_name: "Platform",
        is_active: true,
      },
    });
    const user = userEvent.setup();
    renderWithProviders(<AdminPage />, { route: "/admin" });
    await screen.findByTestId("admin-users-table");

    await user.click(screen.getByRole("button", { name: "Add user" }));
    const dialog = screen.getByRole("dialog");
    await user.type(within(dialog).getByLabelText("Email"), "new@example.com");
    await user.type(within(dialog).getByLabelText("Name"), "New Person");
    await user.selectOptions(within(dialog).getByLabelText("Role"), "engineer");
    await user.selectOptions(
      within(dialog).getByLabelText("Team"),
      adminTeamsFixture.items[0].id,
    );
    await user.click(within(dialog).getByRole("button", { name: "Create user" }));

    await waitFor(() => {
      expect(callsFor(fetchMock, "POST", "/v1/admin/users")).toHaveLength(1);
    });
    expect(bodyOf(callsFor(fetchMock, "POST", "/v1/admin/users")[0])).toEqual({
      email: "new@example.com",
      name: "New Person",
      role: "engineer",
      team_id: adminTeamsFixture.items[0].id,
    });
    await waitFor(() => {
      expect(toastTitles()).toContain("User added");
    });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("PATCHes the role when the inline select changes", async () => {
    const fetchMock = mockFetchRoutes({
      ...ADMIN_ROUTES,
      "PATCH /v1/admin/users/6b1f0c1a-1111-4e1a-9b1a-000000000004": {
        ...adminUsersFixture.items[2],
        role: "lead",
      },
    });
    const user = userEvent.setup();
    renderWithProviders(<AdminPage />, { route: "/admin" });
    const table = await screen.findByTestId("admin-users-table");

    await user.selectOptions(
      within(table).getByLabelText("Role for eli@example.com"),
      "lead",
    );

    await waitFor(() => {
      expect(
        callsFor(fetchMock, "PATCH", "/v1/admin/users/6b1f0c1a-1111-4e1a-9b1a-000000000004"),
      ).toHaveLength(1);
    });
    expect(
      bodyOf(
        callsFor(fetchMock, "PATCH", "/v1/admin/users/6b1f0c1a-1111-4e1a-9b1a-000000000004")[0],
      ),
    ).toEqual({ role: "lead" });
    await waitFor(() => {
      expect(toastTitles()).toContain("User updated");
    });
  });

  it("confirms before deactivating a user", async () => {
    const fetchMock = mockFetchRoutes({
      ...ADMIN_ROUTES,
      "PATCH /v1/admin/users/6b1f0c1a-1111-4e1a-9b1a-000000000002": {
        ...adminUsersFixture.items[1],
        is_active: false,
      },
    });
    const user = userEvent.setup();
    renderWithProviders(<AdminPage />, { route: "/admin" });
    const table = await screen.findByTestId("admin-users-table");

    const leadRow = within(table).getByText("lena@example.com").closest("tr")!;
    await user.click(within(leadRow).getByRole("button", { name: "Deactivate" }));

    const dialog = screen.getByRole("dialog");
    expect(dialog).toHaveTextContent("Deactivate Lena Lead?");
    await user.click(within(dialog).getByRole("button", { name: "Deactivate" }));

    await waitFor(() => {
      expect(
        callsFor(
          fetchMock,
          "PATCH",
          "/v1/admin/users/6b1f0c1a-1111-4e1a-9b1a-000000000002",
        ),
      ).toHaveLength(1);
    });
    expect(
      bodyOf(
        callsFor(
          fetchMock,
          "PATCH",
          "/v1/admin/users/6b1f0c1a-1111-4e1a-9b1a-000000000002",
        )[0],
      ),
    ).toEqual({ is_active: false });
  });

  it("disables deactivate/demote controls on the caller's own row", async () => {
    mockFetchRoutes(ADMIN_ROUTES);
    renderWithProviders(<AdminPage />, { route: "/admin" });
    const table = await screen.findByTestId("admin-users-table");

    const selfRow = within(table).getByText(meAdmin.email).closest("tr")!;
    expect(within(selfRow).getByLabelText(`Role for ${meAdmin.email}`)).toBeDisabled();
    expect(within(selfRow).getByRole("button", { name: "Deactivate" })).toBeDisabled();
  });
});

describe("Admin — Teams tab CRUD", () => {
  it("creates a team through the dialog", async () => {
    const fetchMock = mockFetchRoutes({
      ...ADMIN_ROUTES,
      "POST /v1/admin/teams": {
        id: "t-new",
        name: "Growth",
        member_count: 0,
      },
    });
    const user = userEvent.setup();
    renderWithProviders(<AdminPage />, { route: "/admin" });
    await user.click(await screen.findByRole("tab", { name: "Teams" }));
    await screen.findByTestId("admin-teams-table");

    await user.click(screen.getByRole("button", { name: "Add team" }));
    const dialog = screen.getByRole("dialog");
    await user.type(within(dialog).getByLabelText("Team name"), "Growth");
    await user.click(within(dialog).getByRole("button", { name: "Create team" }));

    await waitFor(() => {
      expect(callsFor(fetchMock, "POST", "/v1/admin/teams")).toHaveLength(1);
    });
    expect(bodyOf(callsFor(fetchMock, "POST", "/v1/admin/teams")[0])).toEqual({
      name: "Growth",
    });
    await waitFor(() => {
      expect(toastTitles()).toContain("Team created");
    });
  });

  it("renames a team inline on blur", async () => {
    const fetchMock = mockFetchRoutes({
      ...ADMIN_ROUTES,
      "PATCH /v1/admin/teams/t0000000-0000-4000-8000-000000000001": {
        ...adminTeamsFixture.items[0],
        name: "Platform Core",
      },
    });
    const user = userEvent.setup();
    renderWithProviders(<AdminPage />, { route: "/admin" });
    await user.click(await screen.findByRole("tab", { name: "Teams" }));
    const table = await screen.findByTestId("admin-teams-table");

    const input = within(table).getByLabelText("Team name for Platform");
    await user.clear(input);
    await user.type(input, "Platform Core");
    await user.tab();

    await waitFor(() => {
      expect(
        callsFor(fetchMock, "PATCH", "/v1/admin/teams/t0000000-0000-4000-8000-000000000001"),
      ).toHaveLength(1);
    });
    expect(
      bodyOf(
        callsFor(
          fetchMock,
          "PATCH",
          "/v1/admin/teams/t0000000-0000-4000-8000-000000000001",
        )[0],
      ),
    ).toEqual({ name: "Platform Core" });
  });

  it("deletes a team after confirmation", async () => {
    const fetchMock = mockFetchRoutes({
      ...ADMIN_ROUTES,
      "DELETE /v1/admin/teams/t0000000-0000-4000-8000-000000000002": null,
    });
    const user = userEvent.setup();
    renderWithProviders(<AdminPage />, { route: "/admin" });
    await user.click(await screen.findByRole("tab", { name: "Teams" }));
    const table = await screen.findByTestId("admin-teams-table");

    await user.click(within(table).getByRole("button", { name: "Delete Payments" }));
    const dialog = screen.getByRole("dialog");
    expect(dialog).toHaveTextContent("members will be unassigned");
    await user.click(within(dialog).getByRole("button", { name: "Delete team" }));

    await waitFor(() => {
      expect(
        callsFor(
          fetchMock,
          "DELETE",
          "/v1/admin/teams/t0000000-0000-4000-8000-000000000002",
        ),
      ).toHaveLength(1);
    });
    await waitFor(() => {
      expect(toastTitles()).toContain("Team deleted");
    });
  });
});

describe("Admin — API keys tab CRUD", () => {
  it("creates a key and shows the raw key once with a working copy button", async () => {
    const fetchMock = mockFetchRoutes({
      ...ADMIN_ROUTES,
      "POST /v1/admin/api-keys": {
        id: "k-new",
        label: "ci-bot",
        kind: "api",
        user_name: "Ava Admin",
        raw_key: "ce_api_deadbeefdeadbeefdeadbeefdeadbeef",
      },
    });
    // userEvent.setup() installs its own clipboard shim, so define ours
    // afterwards or it gets clobbered.
    const user = userEvent.setup();
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });
    renderWithProviders(<AdminPage />, { route: "/admin" });
    await user.click(await screen.findByRole("tab", { name: "API keys" }));
    await screen.findByTestId("admin-api-keys-table");

    await user.click(screen.getByRole("button", { name: "Create key" }));
    const dialog = screen.getByRole("dialog");
    await user.type(within(dialog).getByLabelText("Key label"), "ci-bot");
    await user.selectOptions(within(dialog).getByLabelText("Key kind"), "api");
    await user.selectOptions(
      within(dialog).getByLabelText("Key user"),
      meAdmin.id,
    );
    await user.click(within(dialog).getByRole("button", { name: "Create key" }));

    await waitFor(() => {
      expect(callsFor(fetchMock, "POST", "/v1/admin/api-keys")).toHaveLength(1);
    });
    expect(bodyOf(callsFor(fetchMock, "POST", "/v1/admin/api-keys")[0])).toEqual({
      label: "ci-bot",
      kind: "api",
      user_id: meAdmin.id,
    });

    expect(await screen.findByTestId("raw-key-block")).toHaveTextContent(
      "ce_api_deadbeefdeadbeefdeadbeefdeadbeef",
    );
    expect(
      screen.getByText("Copy this key now — it is shown only once and cannot be retrieved later."),
    ).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Copy" }));
    await waitFor(() => {
      expect(writeText).toHaveBeenCalledWith("ce_api_deadbeefdeadbeefdeadbeefdeadbeef");
    });
    await waitFor(() => {
      expect(toastTitles()).toContain("Copied to clipboard");
    });
  });

  it("revokes a key after confirmation", async () => {
    const fetchMock = mockFetchRoutes({
      ...ADMIN_ROUTES,
      "POST /v1/admin/api-keys/k0000000-0000-4000-8000-000000000001/revoke": {
        ...adminApiKeysFixture.items[0],
        is_active: false,
      },
    });
    const user = userEvent.setup();
    renderWithProviders(<AdminPage />, { route: "/admin" });
    await user.click(await screen.findByRole("tab", { name: "API keys" }));
    const table = await screen.findByTestId("admin-api-keys-table");

    await user.click(within(table).getAllByRole("button", { name: "Revoke" })[0]);
    const dialog = screen.getByRole("dialog");
    expect(dialog).toHaveTextContent("ava-cli");
    await user.click(within(dialog).getByRole("button", { name: "Revoke key" }));

    await waitFor(() => {
      expect(
        callsFor(
          fetchMock,
          "POST",
          "/v1/admin/api-keys/k0000000-0000-4000-8000-000000000001/revoke",
        ),
      ).toHaveLength(1);
    });
    await waitFor(() => {
      expect(toastTitles()).toContain("Key revoked");
    });
  });

  it("disables Revoke for already-inactive keys", async () => {
    mockFetchRoutes(ADMIN_ROUTES);
    const user = userEvent.setup();
    renderWithProviders(<AdminPage />, { route: "/admin" });
    await user.click(await screen.findByRole("tab", { name: "API keys" }));
    const table = await screen.findByTestId("admin-api-keys-table");

    const revokeButtons = within(table).getAllByRole("button", { name: "Revoke" });
    expect(revokeButtons[1]).toBeDisabled();
  });

  it("shows a failure toast when key creation errors", async () => {
    mockFetchRoutes({
      ...ADMIN_ROUTES,
      "POST /v1/admin/api-keys": mockResponse({ detail: "label already exists" }, 409),
    });
    const user = userEvent.setup();
    renderWithProviders(<AdminPage />, { route: "/admin" });
    await user.click(await screen.findByRole("tab", { name: "API keys" }));
    await screen.findByTestId("admin-api-keys-table");

    await user.click(screen.getByRole("button", { name: "Create key" }));
    const dialog = screen.getByRole("dialog");
    await user.type(within(dialog).getByLabelText("Key label"), "dup");
    await user.click(within(dialog).getByRole("button", { name: "Create key" }));

    await waitFor(() => {
      expect(toastTitles()).toContain("Failed to create key");
    });
  });
});

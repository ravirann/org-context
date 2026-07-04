import { screen, within } from "@testing-library/react";
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
  settingsFixture,
  systemInfoDeterministicFixture,
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
};

async function openSystemTab() {
  renderWithProviders(<AdminPage />, { route: "/admin" });
  await userEvent.click(await screen.findByRole("tab", { name: "System" }));
}

beforeEach(() => {
  useToastStore.setState({ toasts: [] });
});

describe("AdminPage — System → Runtime card", () => {
  it("renders embedding provider/model/dim, auth mode, queue depth and version", async () => {
    mockFetchRoutes({ ...ADMIN_ROUTES, "GET /v1/system/info": systemInfoFixture });
    await openSystemTab();

    const card = await screen.findByTestId("system-runtime-card");
    expect(within(card).getByText(/openai/)).toBeInTheDocument();
    expect(within(card).getByText(/text-embedding-3-small/)).toBeInTheDocument();
    expect(within(card).getByText(/384 dim/)).toBeInTheDocument();
    expect(within(card).getByText("oidc")).toBeInTheDocument();
    expect(within(card).getByText("3")).toBeInTheDocument();
    expect(within(card).getByText("0.3.0")).toBeInTheDocument();
    // Non-deterministic provider — no "deterministic" hint shown.
    expect(within(card).queryByText(/no semantic signal/)).not.toBeInTheDocument();
  });

  it("shows the deterministic hint when embedding.provider is deterministic", async () => {
    mockFetchRoutes({
      ...ADMIN_ROUTES,
      "GET /v1/system/info": systemInfoDeterministicFixture,
    });
    await openSystemTab();

    const card = await screen.findByTestId("system-runtime-card");
    expect(
      within(card).getByText("no semantic signal — deterministic"),
    ).toBeInTheDocument();
  });

  it("renders a dash for a null queue_depth", async () => {
    mockFetchRoutes({
      ...ADMIN_ROUTES,
      "GET /v1/system/info": systemInfoDeterministicFixture,
    });
    await openSystemTab();

    const card = await screen.findByTestId("system-runtime-card");
    expect(within(card).getByText("—")).toBeInTheDocument();
  });

  it("shows PermissionDenied inside the card on a 403", async () => {
    mockFetchRoutes({
      ...ADMIN_ROUTES,
      "GET /v1/system/info": mockResponse({ detail: "Forbidden" }, 403),
    });
    await openSystemTab();

    expect(await screen.findByText("Permission denied")).toBeInTheDocument();
    // The rest of the System tab (settings JSON) still renders independently.
    expect(await screen.findByTestId("system-settings-json")).toBeInTheDocument();
  });
});

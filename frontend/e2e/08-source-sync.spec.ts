import { expect, test } from "@playwright/test";

import { captureScreenshot, setDesktopViewport, switchApiKey } from "./helpers";

/**
 * Scenario 8: admin triggers a source sync on /sources ("Sync now") and sees
 * the optimistic "syncing" state plus a "Sync queued" toast. Negative case:
 * switching to the viewer key and visiting the admin Settings page (/admin)
 * shows the full-page PermissionDenied — GET /v1/sources itself is readable
 * by every role, but /admin is gated on role === "admin" client-side.
 */
test.describe("source sync", () => {
  test.beforeEach(async ({ page }) => {
    await setDesktopViewport(page);
  });

  test("admin syncs a source now and sees the queued toast", async ({ page }) => {
    await page.goto("/sources");

    const sourcesPage = page.getByTestId("page-sources");
    await expect(sourcesPage).toBeVisible();

    const table = page.getByTestId("sources-table");
    await expect(table).toBeVisible({ timeout: 10_000 });

    const firstRow = table.locator("tbody tr").first();
    await expect(firstRow).toBeVisible();
    const syncButton = firstRow.getByRole("button", { name: /Sync .* now/ });
    await expect(syncButton).toBeVisible();

    const [response] = await Promise.all([
      page.waitForResponse(
        (res) => /\/v1\/sources\/[\w-]+\/sync/.test(res.url()) && res.request().method() === "POST",
      ),
      syncButton.click(),
    ]);
    expect(response.ok()).toBeTruthy();

    await expect(page.getByRole("status").filter({ hasText: /sync queued/i })).toBeVisible({
      timeout: 10_000,
    });

    await captureScreenshot(page, "08-source-sync-admin");
  });

  test("viewer sees PermissionDenied on the admin Settings page", async ({ page }) => {
    await page.goto("/");
    await switchApiKey(page, "Viewer");

    await page.goto("/admin");
    const adminPage = page.getByTestId("page-admin");
    await expect(adminPage).toBeVisible();
    await expect(adminPage.getByRole("alert").getByText(/permission denied/i)).toBeVisible({
      timeout: 10_000,
    });

    // Also confirm the Sources page itself renders read-only for viewer:
    // GET /v1/sources succeeds for every role, but Sync/Delete are disabled.
    await page.goto("/sources");
    const sourcesPage = page.getByTestId("page-sources");
    await expect(sourcesPage).toBeVisible();
    const table = page.getByTestId("sources-table");
    await expect(table).toBeVisible({ timeout: 10_000 });
    const firstSyncButton = table.locator("tbody tr").first().getByRole("button", {
      name: /Sync .* now/,
    });
    await expect(firstSyncButton).toBeDisabled();

    await captureScreenshot(page, "08-source-sync-viewer-denied");
  });
});

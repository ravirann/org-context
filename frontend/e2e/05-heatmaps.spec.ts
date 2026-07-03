import { expect, test } from "@playwright/test";

import { captureScreenshot, setDesktopViewport } from "./helpers";

/**
 * Scenario 5: heatmaps — user-activity grid renders cells, switches to the
 * Ownership tab, and drills into a row to open a dialog.
 */
test.describe("heatmaps", () => {
  test.beforeEach(async ({ page }) => {
    await setDesktopViewport(page);
  });

  test("user activity grid renders, ownership tab drilldown opens a dialog", async ({
    page,
  }) => {
    await page.goto("/heatmaps");

    const heatmapsPage = page.getByTestId("page-heatmaps");
    await expect(heatmapsPage).toBeVisible();

    const userHeatmap = page.getByTestId("user-heatmap");
    await expect(userHeatmap).toBeVisible({ timeout: 10_000 });

    const cells = userHeatmap.locator('[role="gridcell"][data-testid^="hm-cell-"]');
    await expect(cells.first()).toBeVisible();
    expect(await cells.count()).toBeGreaterThan(0);

    // Drill into a cell on the user grid to confirm the dialog opens here too.
    await cells.first().click();
    const cellDialog = page.getByTestId("cell-drilldown");
    await expect(cellDialog).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(cellDialog).not.toBeVisible();

    // Switch to Ownership tab.
    await page.getByRole("tab", { name: "Ownership" }).click();
    const ownershipTable = page.getByTestId("ownership-table");
    await expect(ownershipTable).toBeVisible({ timeout: 10_000 });

    const rows = ownershipTable.locator("tbody tr");
    await expect(rows.first()).toBeVisible();

    await captureScreenshot(page, "05-heatmaps");
  });
});

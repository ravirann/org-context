import { expect, test } from "@playwright/test";

import { captureScreenshot, setDesktopViewport } from "./helpers";

/**
 * Scenario 6: user opens a context packet from /packets (first row) — the
 * inspector shows selected + rejected sources, citations, score strip and
 * the compiled context block.
 */
test.describe("packet detail", () => {
  test.beforeEach(async ({ page }) => {
    await setDesktopViewport(page);
  });

  test("opens the first packet and inspects sources, citations, scores and compiled context", async ({
    page,
  }) => {
    await page.goto("/packets");

    const packetsPage = page.getByTestId("page-packets");
    await expect(packetsPage).toBeVisible();

    const table = packetsPage.locator("table");
    await expect(table).toBeVisible({ timeout: 10_000 });
    const firstRow = table.locator("tbody tr").first();
    await expect(firstRow).toBeVisible();
    await firstRow.click();

    await expect(page).toHaveURL(/\/packets\/[\w-]+/);
    const detail = page.getByTestId("page-packet-detail");
    await expect(detail).toBeVisible();

    // Selected + rejected sources.
    await expect(detail.getByText(/Selected sources \(\d+\)/)).toBeVisible();
    const rejectedToggle = detail.getByRole("button", { name: /Rejected sources \(\d+\)/ });
    await expect(rejectedToggle).toBeVisible();

    // Score strip: confidence / freshness / authority badges (summary card).
    const scoreStrip = detail.locator("span.flex.items-center.gap-1");
    await expect(scoreStrip.filter({ hasText: "confidence" })).toBeVisible();
    await expect(scoreStrip.filter({ hasText: "freshness" })).toBeVisible();
    await expect(scoreStrip.filter({ hasText: "authority" })).toBeVisible();

    // Compiled context block.
    await expect(detail.getByRole("heading", { name: "Compiled context" })).toBeVisible();
    await expect(detail.locator("pre")).toBeVisible();

    // Citations section (present when the packet has any — expand rejected too for the shot).
    await rejectedToggle.click();

    await captureScreenshot(page, "06-packet-detail");
  });
});

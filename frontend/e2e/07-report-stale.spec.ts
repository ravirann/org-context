import { expect, test } from "@playwright/test";

import { captureScreenshot, setDesktopViewport } from "./helpers";

/**
 * Scenario 7: user reports stale context from a document detail page.
 * Clicking "Report stale" fires POST /v1/feedback (201) and confirms via a
 * success toast.
 */
test.describe("report stale context", () => {
  test.beforeEach(async ({ page }) => {
    await setDesktopViewport(page);
  });

  test("clicking Report stale posts feedback and shows a success toast", async ({ page }) => {
    await page.goto("/explorer?q=webhook%20retry");

    const results = page.getByRole("list", { name: "Search results" });
    await expect(results).toBeVisible({ timeout: 10_000 });
    await results.getByRole("listitem").first().getByRole("link").click();

    await expect(page).toHaveURL(/\/explorer\/documents\/[\w-]+/);
    const detail = page.getByTestId("page-document-detail");
    await expect(detail).toBeVisible();

    const [response] = await Promise.all([
      page.waitForResponse(
        (res) => res.url().includes("/v1/feedback") && res.request().method() === "POST",
      ),
      page.getByRole("button", { name: "Report stale" }).click(),
    ]);
    expect(response.status()).toBe(201);

    await expect(page.getByRole("status").filter({ hasText: /reported as stale/i })).toBeVisible({
      timeout: 10_000,
    });

    await captureScreenshot(page, "07-report-stale");
  });
});

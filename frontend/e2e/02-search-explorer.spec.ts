import { expect, test } from "@playwright/test";

import { captureScreenshot, setDesktopViewport } from "./helpers";

/**
 * Scenario 2: user searches context via the topbar global search, lands on
 * /explorer?q=..., and sees a non-empty results list with doc_type badges.
 */
test.describe("global search -> explorer", () => {
  test.beforeEach(async ({ page }) => {
    await setDesktopViewport(page);
  });

  test("topbar search navigates to explorer with results", async ({ page }) => {
    await page.goto("/");

    const search = page.getByRole("searchbox", { name: "Global search" });
    await search.fill("webhook retry");
    await search.press("Enter");

    await expect(page).toHaveURL(/\/explorer\?q=webhook(\+|%20)retry/);
    await expect(page.getByTestId("page-explorer")).toBeVisible();

    const results = page.getByRole("list", { name: "Search results" });
    await expect(results).toBeVisible({ timeout: 10_000 });

    const items = results.getByRole("listitem");
    await expect(items.first()).toBeVisible();
    const count = await items.count();
    expect(count).toBeGreaterThan(0);

    // doc_type badges are visible on results (rendered as Badge "outline" variant).
    await expect(
      items.first().getByText(/^(code|pr|ticket|doc|message|adr|incident|ci_run|feedback)$/i),
    ).toBeVisible();

    await captureScreenshot(page, "02-search-explorer");
  });
});

import { expect, test } from "@playwright/test";

import { captureScreenshot, setDesktopViewport } from "./helpers";

/**
 * Scenario 3: user opens a document from search results into the document
 * detail page — content/chunks tabs, Permissions ACL panel, related docs.
 */
test.describe("document detail", () => {
  test.beforeEach(async ({ page }) => {
    await setDesktopViewport(page);
  });

  test("opens a document and inspects tabs", async ({ page }) => {
    await page.goto("/explorer?q=webhook%20retry");

    const results = page.getByRole("list", { name: "Search results" });
    await expect(results).toBeVisible({ timeout: 10_000 });
    const firstResult = results.getByRole("listitem").first();
    await expect(firstResult).toBeVisible();
    await firstResult.getByRole("link").click();

    await expect(page).toHaveURL(/\/explorer\/documents\/[\w-]+/);
    const detail = page.getByTestId("page-document-detail");
    await expect(detail).toBeVisible();

    const tabs = detail.getByRole("tablist");
    await expect(tabs).toBeVisible();
    await expect(tabs.getByRole("tab", { name: /^Content$/ })).toBeVisible();
    const chunksTab = tabs.getByRole("tab", { name: /^Chunks/ });
    const permissionsTab = tabs.getByRole("tab", { name: /^Permissions$/ });
    const relatedTab = tabs.getByRole("tab", { name: /^Related/ });
    await expect(chunksTab).toBeVisible();
    await expect(permissionsTab).toBeVisible();
    await expect(relatedTab).toBeVisible();

    // Chunks tab.
    await chunksTab.click();
    await expect(detail.getByRole("tabpanel")).toBeVisible();

    // Permissions tab shows the ACL panel.
    await permissionsTab.click();
    await expect(detail.getByRole("heading", { name: "Access control" })).toBeVisible();

    // Related docs section (may be empty state or a list — assert the section renders).
    await relatedTab.click();
    const relatedPanel = detail.getByRole("tabpanel");
    await expect(relatedPanel).toBeVisible();

    await captureScreenshot(page, "03-document-detail");
  });
});

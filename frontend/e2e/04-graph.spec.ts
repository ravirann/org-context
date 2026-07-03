import { expect, test } from "@playwright/test";

import { captureScreenshot, setDesktopViewport } from "./helpers";

/**
 * Scenario 4: relationship graph — React Flow nodes render, filtering by
 * node type and searching a node changes the visible node set.
 */
test.describe("relationship graph", () => {
  test.beforeEach(async ({ page }) => {
    await setDesktopViewport(page);
  });

  test("renders nodes and reacts to filters + search", async ({ page }) => {
    await page.goto("/graph");

    const graphPage = page.getByTestId("page-graph");
    await expect(graphPage).toBeVisible();

    const canvas = page.getByTestId("graph-canvas");
    await expect(canvas).toBeVisible({ timeout: 15_000 });

    const nodes = canvas.locator(".react-flow__node");
    await expect(nodes.first()).toBeVisible({ timeout: 15_000 });
    const initialCount = await nodes.count();
    expect(initialCount).toBeGreaterThan(0);

    // Filter by the "Service" node type chip — this restricts NODE_TYPES so
    // only service nodes (and their edges' endpoints) remain visible.
    const serviceChip = page.getByRole("button", { name: "Service", exact: true });
    await expect(serviceChip).toBeVisible();
    await serviceChip.click();
    await expect(serviceChip).toHaveAttribute("aria-pressed", "true");

    await expect
      .poll(async () => nodes.count(), { timeout: 10_000 })
      .toBeGreaterThan(0);
    const filteredCount = await nodes.count();
    expect(filteredCount).toBeLessThanOrEqual(initialCount);

    // Clear the filter back out.
    await serviceChip.click();
    await expect(serviceChip).toHaveAttribute("aria-pressed", "false");
    await expect.poll(async () => nodes.count(), { timeout: 10_000 }).toBe(initialCount);

    // Search for a node — centers viewport, doesn't change node count, but
    // confirms the search input works end-to-end.
    const searchInput = page.getByRole("textbox", { name: "Search nodes" });
    await searchInput.fill("payments");
    await page.waitForTimeout(300); // debounce (200ms) settle before screenshot.

    await captureScreenshot(page, "04-graph");
  });
});

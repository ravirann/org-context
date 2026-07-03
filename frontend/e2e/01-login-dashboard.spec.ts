import { expect, test } from "@playwright/test";

import { captureScreenshot, setDesktopViewport, switchApiKey } from "./helpers";

/**
 * Scenario 1: user "logs in" by picking a role via the topbar key switcher,
 * then views the dashboard — seeded stat cards and trend charts render.
 */
test.describe("login + dashboard", () => {
  test.beforeEach(async ({ page }) => {
    await setDesktopViewport(page);
  });

  test("switches role via the key switcher and the /v1/me-driven role chip updates", async ({
    page,
  }) => {
    await page.goto("/");

    const trigger = page.getByRole("button", { name: "Switch API key" });
    await expect(trigger).toBeVisible();
    // Default demo key is admin.
    await expect(trigger).toContainText("admin");

    await switchApiKey(page, "Viewer");
    await expect(trigger).toContainText("viewer");

    // Switch back to admin for the rest of the dashboard assertions.
    await switchApiKey(page, "Admin");
    await expect(trigger).toContainText("admin");
  });

  test("dashboard shows seeded stat cards and rendered trend charts", async ({ page }) => {
    await page.goto("/");

    const dashboard = page.getByTestId("page-dashboard");
    await expect(dashboard).toBeVisible();
    await expect(page.getByRole("heading", { level: 1, name: "Dashboard" })).toBeVisible();

    // Stat cards carry seeded numbers — indexed documents > 0, connected sources == 8.
    const metrics = page.getByRole("region", { name: "Key metrics" }).or(
      page.locator('[aria-label="Key metrics"]'),
    );
    await expect(metrics).toBeVisible();

    const docsCard = metrics.getByText("Indexed documents").locator("..");
    await expect(docsCard).toBeVisible();

    // Assert the numeric values directly via text content within the metrics section.
    await expect(metrics).toContainText(/Connected sources/);
    await expect
      .poll(async () => {
        const text = await metrics.innerText();
        const match = text.match(/Connected sources\s*\n?\s*(\d+)/);
        return match ? Number(match[1]) : null;
      })
      .toBe(8);

    await expect
      .poll(async () => {
        const text = await metrics.innerText();
        const match = text.match(/Indexed documents\s*\n?\s*([\d,]+)/);
        return match ? Number(match[1].replace(/,/g, "")) : null;
      })
      .toBeGreaterThan(0);

    // Trend charts render as SVGs (recharts ResponsiveContainer -> svg).
    const trendsSection = page.locator('[aria-label="Trends"]');
    await expect(trendsSection).toBeVisible();
    await expect(trendsSection.locator("svg").first()).toBeVisible();
    const svgCount = await trendsSection.locator("svg").count();
    expect(svgCount).toBeGreaterThan(0);

    await captureScreenshot(page, "01-login-dashboard");
  });

  test("dark mode dashboard screenshot", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByTestId("page-dashboard")).toBeVisible();

    const themeToggle = page.getByRole("button", { name: "Toggle theme" });
    await themeToggle.click();
    await expect(page.locator("html")).toHaveClass(/dark/);
    // Let charts re-render with dark palette vars.
    await expect(page.locator('[aria-label="Trends"] svg').first()).toBeVisible();

    await captureScreenshot(page, "01-dashboard-dark-mode");

    // Restore light mode so it doesn't leak (storage is per-context anyway, but be tidy).
    await themeToggle.click();
  });
});

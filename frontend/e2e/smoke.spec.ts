import { expect, test } from "@playwright/test";

/**
 * Smoke test against the compose stack (UI :8080 + seeded API :8000).
 * Assertions stick to layout elements owned by the frontend foundation so
 * they keep passing after page agents replace the placeholder pages.
 */
test("loads the dashboard shell", async ({ page }) => {
  await page.goto("/");

  await expect(page).toHaveTitle(/Org Context/);

  // Sidebar with primary navigation
  const nav = page.getByRole("navigation", { name: "Primary" });
  await expect(nav).toBeVisible();
  await expect(nav.getByRole("link", { name: "Dashboard" })).toBeVisible();
  await expect(nav.getByRole("link", { name: "Context Explorer" })).toBeVisible();

  // Topbar controls
  await expect(page.getByRole("searchbox", { name: "Global search" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Toggle theme" })).toBeVisible();

  // Dashboard page mounted in <main>
  await expect(page.getByRole("main")).toBeVisible();
  await expect(
    page.getByRole("heading", { level: 1, name: "Dashboard" }),
  ).toBeVisible();
});

import { expect, type Page } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

/** Seeded demo API keys, mirrors src/components/layout/topbar.tsx DEMO_KEYS. */
export const DEMO_KEYS = {
  admin: "demo-admin-key",
  lead: "demo-lead-key",
  engineer: "demo-engineer-key",
  viewer: "demo-viewer-key",
} as const;

export type DemoRoleLabel = "Admin" | "Lead" | "Engineer" | "Viewer";

const SCREENSHOT_DIR = path.join(__dirname, "screenshots");

/** Full-page screenshot at the fixed 1440x900 viewport into e2e/screenshots/<name>.png. */
export async function captureScreenshot(page: Page, name: string): Promise<void> {
  await page.screenshot({
    path: path.join(SCREENSHOT_DIR, `${name}.png`),
    fullPage: true,
  });
}

/**
 * Switches the active API key (and therefore role) via the topbar's "Switch
 * API key" dropdown, and waits for the role badge to reflect the change.
 */
export async function switchApiKey(page: Page, roleLabel: DemoRoleLabel): Promise<void> {
  await page.getByRole("button", { name: "Switch API key" }).click();
  await page.getByRole("menuitem", { name: new RegExp(`^${roleLabel}\\b`) }).click();
  // Menu closes and the topbar refetches /v1/me; wait for the badge text.
  await expect(page.getByRole("button", { name: "Switch API key" })).toBeVisible();
}

/** Sets viewport to the standard desktop size used across all scenario screenshots. */
export async function setDesktopViewport(page: Page): Promise<void> {
  await page.setViewportSize({ width: 1440, height: 900 });
}

/** Waits for at least one toast with the given (partial, case-insensitive) title text. */
export async function expectToast(page: Page, textPattern: string | RegExp): Promise<void> {
  const pattern = typeof textPattern === "string" ? new RegExp(textPattern, "i") : textPattern;
  await expect(page.getByText(pattern).first()).toBeVisible({ timeout: 10_000 });
}

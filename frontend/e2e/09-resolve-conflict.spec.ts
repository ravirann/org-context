import { expect, test } from "@playwright/test";

import { captureScreenshot, setDesktopViewport } from "./helpers";

/**
 * Scenario 9: user resolves a conflict. This mutates the DB (conflict status
 * open -> resolved) so it runs serially and only once against the freshly
 * seeded data.
 */
test.describe.configure({ mode: "serial" });

test.describe("resolve conflict", () => {
  test.beforeEach(async ({ page }) => {
    await setDesktopViewport(page);
  });

  test("opens a conflict, compares docs side-by-side, submits a resolution note", async ({
    page,
  }) => {
    await page.goto("/conflicts?status=open");

    const conflictsPage = page.getByTestId("page-conflicts");
    await expect(conflictsPage).toBeVisible();

    const table = page.getByTestId("conflicts-table");
    await expect(table).toBeVisible({ timeout: 10_000 });
    const firstRow = table.locator("tbody tr").first();
    await expect(firstRow).toBeVisible();
    await firstRow.click();

    await expect(page).toHaveURL(/\/conflicts\/[\w-]+/);
    const detail = page.getByTestId("page-conflict-detail");
    await expect(detail).toBeVisible();

    // Side-by-side conflicting documents.
    const docCards = detail.locator('[data-testid^="conflict-doc-"]');
    await expect(docCards.first()).toBeVisible({ timeout: 10_000 });
    const docCount = await docCards.count();
    expect(docCount).toBeGreaterThanOrEqual(2);

    // Fill the resolution note and submit.
    const form = page.getByTestId("resolution-form");
    await expect(form).toBeVisible();
    await form.getByLabel(/Resolution note/).fill(
      "E2E test: Confirmed with the payments team — the ADR reflects current production behavior.",
    );

    const [response] = await Promise.all([
      page.waitForResponse(
        (res) => /\/v1\/conflicts\/[\w-]+\/resolve/.test(res.url()) && res.request().method() === "POST",
      ),
      form.getByRole("button", { name: "Resolve conflict" }).click(),
    ]);
    expect(response.ok()).toBeTruthy();

    await expect(page.getByRole("status").filter({ hasText: /conflict resolved/i })).toBeVisible({
      timeout: 10_000,
    });

    // Status badge flips to resolved and the resolution summary replaces the form.
    await expect(detail.getByTestId("resolution-summary")).toBeVisible({ timeout: 10_000 });
    await expect(detail.getByText(/^resolved$/i)).toBeVisible();

    await captureScreenshot(page, "09-resolve-conflict");
  });
});

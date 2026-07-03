import { expect, test } from "@playwright/test";

import { captureScreenshot, setDesktopViewport } from "./helpers";

/**
 * Scenario 10: user runs an eval on /evals ("Run eval"). A toast confirms
 * the run was queued, and the new run appears in the history table — the
 * real Dramatiq worker processes it, so we poll (reload) until it leaves
 * "running" or up to 30s, whichever comes first.
 */
test.describe("run eval", () => {
  test.beforeEach(async ({ page }) => {
    await setDesktopViewport(page);
  });

  test("queues an eval run and it shows up in history", async ({ page }) => {
    await page.goto("/evals");

    const evalsPage = page.getByTestId("page-evals");
    await expect(evalsPage).toBeVisible();

    const historyTable = page.getByTestId("eval-history-table");
    await expect(historyTable).toBeVisible({ timeout: 10_000 });
    const beforeCount = await historyTable.locator("tbody tr").count();

    const [response] = await Promise.all([
      page.waitForResponse(
        (res) => res.url().includes("/v1/evals/run") && res.request().method() === "POST",
      ),
      page.getByRole("button", { name: "Run eval" }).click(),
    ]);
    expect(response.ok()).toBeTruthy();

    await expect(page.getByRole("status").filter({ hasText: /eval queued/i })).toBeVisible({
      timeout: 10_000,
    });

    // New run appears in history after the query invalidation refetch.
    await expect
      .poll(async () => historyTable.locator("tbody tr").count(), { timeout: 10_000 })
      .toBeGreaterThan(beforeCount);

    const newestRow = historyTable.locator("tbody tr").first();
    await expect(newestRow).toBeVisible();
    await expect(newestRow).toContainText(/running|completed|failed/i);

    // The real Dramatiq worker processes the run asynchronously — poll (via
    // reload) up to 30s for it to leave the "running" state.
    await expect
      .poll(
        async () => {
          await page.reload();
          const row = page.getByTestId("eval-history-table").locator("tbody tr").first();
          await expect(row).toBeVisible({ timeout: 10_000 });
          return (await row.innerText()).match(/running|completed|failed/i)?.[0].toLowerCase();
        },
        { timeout: 30_000, intervals: [2000, 3000, 5000, 5000, 5000] },
      )
      .not.toBe("running");

    await captureScreenshot(page, "10-run-eval");
  });
});

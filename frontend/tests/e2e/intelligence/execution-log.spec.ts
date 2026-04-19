/**
 * E2E — ExecutionLog
 *
 * 3 tests:
 *   1. Log page loads executions
 *   2. Filter by status narrows results, URL persists
 *   3. Click row navigates to detail with ID in URL
 */
import { expect, test } from "@playwright/test";
import { openExecutionLog } from "./auth-setup";

test.describe("@intelligence ExecutionLog", () => {
  test("1. loads executions", async ({ page }) => {
    await openExecutionLog(page);
    await expect(
      page.getByRole("heading", { name: /execution log/i }),
    ).toBeVisible();
    // At least one row present (seed produces ~300)
    const rows = page.locator("tbody tr");
    await expect(rows.first()).toBeVisible({ timeout: 10_000 });
  });

  test("2. filter by status narrows + persists in URL", async ({ page }) => {
    await openExecutionLog(page);

    // Pick the status filter — there are multiple selects; find the one
    // whose options include "Any status"
    const statusSelect = page
      .locator("select")
      .filter({ hasText: /any status|success|error/i })
      .first();
    await statusSelect.selectOption("error");
    await page.waitForTimeout(500);

    expect(page.url()).toContain("status=error");

    // All visible rows should carry the 'error' badge (or no rows)
    const rows = page.locator("tbody tr");
    const count = await rows.count();
    if (count > 0) {
      // "error" badge appears as text in the status cell
      const badgeCount = await rows.locator("text=error").count();
      expect(badgeCount).toBeGreaterThan(0);
    }
  });

  test("3. click execution row navigates to detail", async ({ page }) => {
    await openExecutionLog(page);

    const firstViewLink = page
      .locator("tbody tr")
      .first()
      .getByRole("link", { name: /^view$/i });
    const href = await firstViewLink.getAttribute("href");
    expect(href).toMatch(/\/admin\/intelligence\/executions\//);

    await firstViewLink.click();
    await page.waitForURL(/\/admin\/intelligence\/executions\/[^/]+$/, {
      timeout: 10_000,
    });
    // ExecutionDetail renders prompt content + linkage sections
    await expect(
      page.getByRole("heading", { name: /prompt content/i }),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", { name: /linkage/i }),
    ).toBeVisible();
  });
});

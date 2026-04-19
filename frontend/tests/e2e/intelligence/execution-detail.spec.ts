/**
 * E2E — ExecutionDetail
 *
 * 2 tests:
 *   1. Detail page shows summary + rendered content
 *   2. Linkage empty state renders as single-paragraph note when nothing linked
 */
import { expect, test } from "@playwright/test";
import { openExecutionLog } from "./auth-setup";

async function firstExecutionDetail(page: import("@playwright/test").Page) {
  await openExecutionLog(page);
  const viewLink = page
    .locator("tbody tr")
    .first()
    .getByRole("link", { name: /^view$/i });
  await viewLink.click();
  await page.waitForURL(/\/admin\/intelligence\/executions\/[^/]+$/);
  await page.waitForLoadState("networkidle");
}

test.describe("@intelligence ExecutionDetail", () => {
  test("1. shows summary + rendered content", async ({ page }) => {
    await firstExecutionDetail(page);

    // Summary fields appear (model, caller module, etc.)
    await expect(page.getByText(/model used/i).first()).toBeVisible();
    await expect(page.getByText(/caller module/i).first()).toBeVisible();

    // Rendered prompt blocks
    await expect(
      page.getByRole("heading", { name: /prompt content/i }),
    ).toBeVisible();

    // Response section
    await expect(
      page.getByRole("heading", { name: /^response$/i }),
    ).toBeVisible();
  });

  test("2. linkage section renders (empty or populated)", async ({ page }) => {
    await firstExecutionDetail(page);

    await expect(
      page.getByRole("heading", { name: /^linkage$/i }),
    ).toBeVisible();
    // Either "No entity linkage" prose OR a populated table — both are OK
    const empty = page.getByText(/no entity linkage/i);
    const emptyCount = await empty.count();
    if (emptyCount === 0) {
      // If populated, there should be at least one uppercase linkage label
      const rows = page.locator("table tbody tr");
      await expect(rows.first()).toBeVisible();
    }
  });
});

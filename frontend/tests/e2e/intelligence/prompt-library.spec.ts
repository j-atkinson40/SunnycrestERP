/**
 * E2E — PromptLibrary
 *
 * 3 tests:
 *   1. Library page loads and shows prompts
 *   2. Search filter narrows rows
 *   3. Click prompt navigates to detail
 */
import { expect, test } from "@playwright/test";
import { openPromptLibrary } from "./auth-setup";

test.describe("@intelligence PromptLibrary", () => {
  test("1. loads and shows prompts", async ({ page }) => {
    await openPromptLibrary(page);

    // Heading
    await expect(
      page.getByRole("heading", { name: /prompt library/i }),
    ).toBeVisible();

    // At least one prompt row rendered (seed data produces ~70+)
    const rows = page.locator("tbody tr");
    await expect(rows.first()).toBeVisible({ timeout: 10_000 });
  });

  test("2. search filter narrows results", async ({ page }) => {
    await openPromptLibrary(page);

    const rowsBefore = await page.locator("tbody tr").count();
    expect(rowsBefore).toBeGreaterThan(1);

    // Search for something that matches a subset
    await page
      .getByPlaceholder(/search key \/ description/i)
      .fill("briefing");
    // Wait for URL to update (filter persistence)
    await page.waitForTimeout(400);

    const rowsAfter = await page.locator("tbody tr").count();
    expect(rowsAfter).toBeLessThan(rowsBefore);

    // URL now contains the search param
    expect(page.url()).toContain("search=briefing");
  });

  test("3. click prompt navigates to detail", async ({ page }) => {
    await openPromptLibrary(page);

    const firstLink = page
      .locator("tbody tr")
      .first()
      .locator("a.font-mono")
      .first();
    const href = await firstLink.getAttribute("href");
    expect(href).toMatch(/\/admin\/intelligence\/prompts\//);

    await firstLink.click();
    await page.waitForURL(/\/admin\/intelligence\/prompts\/[^/]+$/, {
      timeout: 10_000,
    });
    // Detail page should show the prompt_key as a heading
    const keyHeading = page.locator("h1.font-mono").first();
    await expect(keyHeading).toBeVisible();
  });
});

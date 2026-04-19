/**
 * E2E — PromptDetail
 *
 * 3 tests:
 *   1. Detail page shows active version + version history + chart + audit tab
 *   2. Clicking a non-active version swaps the panel + shows "Return to active"
 *   3. Edit button reflects permission (disabled when not allowed)
 */
import { expect, test } from "@playwright/test";
import { openPromptLibrary } from "./auth-setup";

async function openFirstPrompt(page: import("@playwright/test").Page) {
  await openPromptLibrary(page);
  const firstLink = page
    .locator("tbody tr")
    .first()
    .locator("a.font-mono")
    .first();
  await firstLink.click();
  await page.waitForURL(/\/admin\/intelligence\/prompts\/[^/]+$/);
  await page.waitForLoadState("networkidle");
}

test.describe("@intelligence PromptDetail", () => {
  test("1. shows active version, history, chart, audit", async ({ page }) => {
    await openFirstPrompt(page);

    // Active version heading appears
    await expect(
      page.getByRole("heading", { name: /active version|viewing version/i }),
    ).toBeVisible();

    // Version History section
    await expect(
      page.getByRole("heading", { name: /version history/i }),
    ).toBeVisible();

    // History (audit) section
    await expect(
      page.getByRole("heading", { name: /^history$/i }),
    ).toBeVisible();

    // Daily activity chart heading
    await expect(
      page.getByRole("heading", { name: /daily activity/i }),
    ).toBeVisible();
  });

  test("2. clicking non-active version swaps the panel with Return link", async ({
    page,
  }) => {
    await openFirstPrompt(page);

    // Find a retired / draft version row in the history table
    const retiredRow = page
      .locator("tbody tr")
      .filter({ hasText: /retired/i })
      .first();
    const count = await retiredRow.count();
    test.skip(count === 0, "No retired version to exercise");

    await retiredRow.click();
    await expect(
      page.getByRole("button", { name: /return to active version/i }).or(
        page.getByText(/return to active version/i),
      ),
    ).toBeVisible({ timeout: 5_000 });
  });

  test("3. Edit button exists and is permission-gated", async ({ page }) => {
    await openFirstPrompt(page);
    // Edit button should exist for any admin-visible prompt
    const editButton = page
      .getByRole("button", { name: /^edit$|^open draft$/i })
      .first();
    await expect(editButton).toBeVisible();
    // If the prompt is platform-global and the user isn't super_admin,
    // the button is disabled and the tooltip carries the reason.
    const isDisabled = await editButton.isDisabled();
    if (isDisabled) {
      const title = await editButton.getAttribute("title");
      expect(title ?? "").toMatch(/permission|super_admin|cannot edit/i);
    }
  });
});

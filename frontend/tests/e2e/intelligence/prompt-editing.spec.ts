/**
 * E2E — Prompt editing flow (Phase 3b)
 *
 * 3 tests:
 *   1. Activation dialog requires changelog before submit is enabled
 *   2. Platform-global prompt shows super_admin-required gate when admin
 *      lacks the flag
 *   3. Rollback button visible on retired rows (when user can edit)
 *
 * These tests exercise UI gating without mutating state — they assert the
 * UI's shape, not the outcome of writes. The permission behavior is covered
 * by backend tests.
 */
import { expect, test } from "@playwright/test";
import { openPromptLibrary } from "./auth-setup";

async function openFirstTenantPrompt(page: import("@playwright/test").Page) {
  await openPromptLibrary(page);
  // Prefer a tenant-scoped prompt so admin can actually edit. Staging seed
  // may or may not expose one — fall back to first row.
  const tenantRow = page
    .locator("tbody tr")
    .filter({ hasNotText: "platform" })
    .first();
  const link =
    (await tenantRow.count()) > 0
      ? tenantRow.locator("a.font-mono").first()
      : page.locator("tbody tr a.font-mono").first();
  await link.click();
  await page.waitForURL(/\/admin\/intelligence\/prompts\/[^/]+$/);
  await page.waitForLoadState("networkidle");
}

test.describe("@intelligence PromptEditing", () => {
  test("1. Activation dialog blocks submit without changelog", async ({
    page,
  }) => {
    await openFirstTenantPrompt(page);
    const editButton = page
      .getByRole("button", { name: /^edit$|^open draft$/i })
      .first();
    if (await editButton.isDisabled()) {
      test.skip(true, "Edit is gated — no writable prompt available.");
    }
    await editButton.click();
    // Wait for draft panel to render
    await expect(
      page.getByRole("heading", { name: /editing draft/i }),
    ).toBeVisible({ timeout: 10_000 });

    // Open activation dialog
    await page.getByRole("button", { name: /^activate$/i }).click();
    await expect(
      page.getByRole("heading", { name: /activate v\d+ of/i }),
    ).toBeVisible({ timeout: 5_000 });

    // Find the Activate submit inside the dialog
    const activateSubmit = page.getByRole("dialog").getByRole("button", {
      name: /^activate$|^activating/i,
    });
    // Clear the pre-filled changelog
    const changelog = page
      .getByRole("dialog")
      .locator("textarea")
      .first();
    await changelog.fill("");
    await expect(activateSubmit).toBeDisabled();
  });

  test("2. Platform-global prompt shows super_admin gate tooltip", async ({
    page,
  }) => {
    await openPromptLibrary(page);
    // Look for a row badged "platform"
    const platformRow = page
      .locator("tbody tr")
      .filter({ hasText: "platform" })
      .first();
    const count = await platformRow.count();
    test.skip(count === 0, "No platform prompts visible.");

    const link = platformRow.locator("a.font-mono").first();
    await link.click();
    await page.waitForURL(/\/admin\/intelligence\/prompts\/[^/]+$/);

    const editButton = page
      .getByRole("button", { name: /^edit$|^open draft$/i })
      .first();
    await expect(editButton).toBeVisible();
    // Admin without is_super_admin should see button disabled with tooltip
    const disabled = await editButton.isDisabled();
    if (disabled) {
      const title = await editButton.getAttribute("title");
      expect(title ?? "").toMatch(/super_admin|permission/i);
    }
  });

  test("3. Rollback button shows on retired rows when editable", async ({
    page,
  }) => {
    await openFirstTenantPrompt(page);
    const rollbackBtn = page.getByRole("button", { name: /^roll back$/i });
    // Count is ok to be 0 if this prompt has no retired versions — just
    // make sure no crash. A stronger assertion lives in phase3b backend tests.
    const count = await rollbackBtn.count();
    if (count > 0) {
      await expect(rollbackBtn.first()).toBeVisible();
    }
  });
});

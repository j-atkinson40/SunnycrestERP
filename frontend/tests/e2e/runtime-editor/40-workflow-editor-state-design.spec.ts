/**
 * Gate 40 — Workflow editor state design (Builder Craft Arc Phase 1b).
 *
 * §18.1 + §18.3 adoption smoke against staging:
 *   1. FILTERED-empty: filtering the workflow-type list to no matches shows
 *      the designed "No matches" state with clear-filter — and the
 *      create-invitation does NOT show over the active filter (the
 *      platform never lies about state).
 *   2. `?` opens the shortcut overlay (one screen, grouped by task).
 */
import { test, expect } from "@playwright/test"
import { STAGING_FRONTEND, loginAsPlatformAdmin } from "./_shared"

test.describe("Gate 40 — Workflow editor state design (Craft 1b)", () => {
  test("filtered-empty shows No-matches + clear-filter, never the create-invitation", async ({
    page,
  }) => {
    await loginAsPlatformAdmin(page)
    await page.goto(
      `${STAGING_FRONTEND}/bridgeable-admin/visual-editor/workflows`,
    )
    await expect(page.getByTestId("workflow-editor-page")).toBeVisible({
      timeout: 15_000,
    })

    // Filter to a string no workflow type matches.
    await page
      .getByTestId("hierarchical-browser-search")
      .fill("zzz-no-such-type")

    const filtered = page.getByTestId("workflow-browser-filtered-empty")
    await expect(filtered).toBeVisible()
    await expect(filtered).toContainText("No matches")
    // §18.1 — the create-invitation must NOT show over an active filter.
    await expect(
      page.getByTestId("workflow-browser-empty-create"),
    ).toHaveCount(0)

    // Clear-filter restores the list.
    await page.getByTestId("workflow-browser-clear-filters").click()
    await expect(filtered).toHaveCount(0)
  })

  test("? opens the shortcut overlay", async ({ page }) => {
    await loginAsPlatformAdmin(page)
    await page.goto(
      `${STAGING_FRONTEND}/bridgeable-admin/visual-editor/workflows`,
    )
    await expect(page.getByTestId("workflow-editor-page")).toBeVisible({
      timeout: 15_000,
    })

    // Focus the page body (no input focused), then press ?.
    await page.getByTestId("workflow-editor-page").click()
    await page.keyboard.press("?")
    const overlay = page.getByTestId("shortcut-overlay")
    await expect(overlay).toBeVisible()
    await expect(overlay).toContainText("Workflow editor shortcuts")
    await expect(overlay).toContainText("Generate workflow from prompt")
    // Esc closes (ui/dialog).
    await page.keyboard.press("Escape")
    await expect(overlay).toHaveCount(0)
  })
})

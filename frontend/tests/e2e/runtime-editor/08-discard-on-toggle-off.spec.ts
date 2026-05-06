/**
 * Gate 8: Toggle off with uncommitted drafts → confirm dialog →
 * Discard reverts staged state.
 */
import { test, expect } from "@playwright/test"
import { openEditorForHopkins } from "./_shared"


test.describe("Gate 8 — discard on toggle-off", () => {
  test("uncommitted drafts → confirm dialog → discard clears staged", async ({
    page,
  }) => {
    await openEditorForHopkins(page)
    await page.getByTestId("runtime-editor-toggle").click()
    await page.locator("[data-component-name]").first().click()
    await page.getByTestId("runtime-inspector-tab-theme").click()

    // Stage an override.
    const accentInput = page.getByTestId("runtime-inspector-token-input-accent")
    await accentInput.fill("oklch(0.50 0.10 40)")
    await accentInput.blur()
    await page.waitForTimeout(200)

    // Toggle off — should open confirm dialog because stagedCount > 0.
    await page.getByTestId("runtime-editor-toggle").click()
    const dialog = page.getByTestId("runtime-editor-confirm-dialog")
    await expect(dialog).toBeVisible({ timeout: 5_000 })
    await expect(
      page.getByTestId("runtime-editor-confirm-discard"),
    ).toBeVisible()
    await expect(
      page.getByTestId("runtime-editor-confirm-commit"),
    ).toBeVisible()
    await expect(
      page.getByTestId("runtime-editor-confirm-cancel"),
    ).toBeVisible()

    // Click discard.
    await page.getByTestId("runtime-editor-confirm-discard").click()
    await expect(dialog).toHaveCount(0, { timeout: 5_000 })

    // Edit mode is now off; URL drops ?edit=1.
    expect(page.url()).not.toContain("edit=1")
    await expect(
      page.getByTestId("runtime-editor-toggle"),
    ).toHaveAttribute("data-active", "false")
  })
})

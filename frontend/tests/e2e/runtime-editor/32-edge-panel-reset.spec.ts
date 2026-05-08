/**
 * Gate 32 — Reset to default clears per-user override.
 *
 * R-5.1 — apply an override (hide a placement, save), then click
 * Reset to default + confirm. The override is cleared; reload
 * shows tenant default unmodified.
 */
import { test, expect } from "@playwright/test"
import { loginAsTestcoAdmin, STAGING_FRONTEND } from "./_shared"


test.describe("Gate 32 — Edge panel reset clears override", () => {
  test("reset-all confirmation clears all customizations", async ({ page }) => {
    await loginAsTestcoAdmin(page)
    await page.goto(`${STAGING_FRONTEND}/settings/edge-panel`)
    await page.waitForLoadState("networkidle")

    const root = page.getByTestId("edge-panel-settings-page")
    await root.waitFor({ state: "visible", timeout: 15_000 })

    // Apply an override: hide first placement + save.
    const hideButtons = page.locator(
      '[data-testid^="edge-panel-settings-placement-toggle-hide-"]',
    )
    await hideButtons.first().waitFor({ state: "visible", timeout: 10_000 })
    await hideButtons.first().click()
    await page.getByTestId("edge-panel-settings-save").click()
    await expect(
      page.getByTestId("edge-panel-settings-unsaved-indicator"),
    ).not.toBeVisible({ timeout: 10_000 })

    // After save, at least one placement is in the hidden state.
    const hidden = page.locator(
      '[data-testid^="edge-panel-settings-placement-"][data-hidden="true"]',
    )
    await expect(hidden.first()).toBeVisible({ timeout: 5_000 })

    // Now click Reset to default.
    await page.getByTestId("edge-panel-settings-reset-all").click()
    const dialog = page.getByTestId("edge-panel-reset-dialog-panel")
    await dialog.waitFor({ state: "visible", timeout: 5_000 })
    await page.getByTestId("edge-panel-reset-dialog-panel-confirm").click()

    // Wait for reset to complete.
    await page.waitForTimeout(1500)

    // No placement should be in hidden state any more.
    await expect(
      page.locator(
        '[data-testid^="edge-panel-settings-placement-"][data-hidden="true"]',
      ),
    ).toHaveCount(0, { timeout: 10_000 })

    // Reload preserves the cleared state.
    await page.reload()
    await page.waitForLoadState("networkidle")
    await root.waitFor({ state: "visible", timeout: 15_000 })
    await expect(
      page.locator(
        '[data-testid^="edge-panel-settings-placement-"][data-hidden="true"]',
      ),
    ).toHaveCount(0, { timeout: 10_000 })
  })
})

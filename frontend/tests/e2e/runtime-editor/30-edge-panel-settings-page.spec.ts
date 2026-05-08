/**
 * Gate 30 — `/settings/edge-panel` mounts and persists basic edits.
 *
 * R-5.1 — settings page loads with the tenant default rendered,
 * a placeholder hide-toggle persists across reload via PATCH +
 * GET round-trip on the per-user override blob.
 *
 * Spec runs against staging. Requires r91 migration applied + the
 * default platform_default edge_panel composition seeded.
 */
import { test, expect } from "@playwright/test"
import { loginAsTestcoAdmin, STAGING_FRONTEND } from "./_shared"


test.describe("Gate 30 — Edge panel settings page", () => {
  test("settings page mounts + tenant default visible", async ({ page }) => {
    await loginAsTestcoAdmin(page)
    await page.goto(`${STAGING_FRONTEND}/settings/edge-panel`)
    await page.waitForLoadState("networkidle")

    // Page root mounts.
    const root = page.getByTestId("edge-panel-settings-page")
    await root.waitFor({ state: "visible", timeout: 15_000 })

    // Page list shows at least one tenant page row (the seeded
    // platform_default composition has 2 pages: Quick Actions +
    // Dispatch).
    const pageList = page.getByTestId("edge-panel-settings-page-list")
    await pageList.waitFor({ state: "visible", timeout: 10_000 })
    const rows = page.locator(
      '[data-testid^="edge-panel-settings-page-row-"]',
    )
    await expect(rows.first()).toBeVisible()

    // Editor + preview panes mount.
    await expect(
      page.getByTestId("edge-panel-settings-page-editor"),
    ).toBeVisible()
    await expect(
      page.getByTestId("edge-panel-settings-preview"),
    ).toBeVisible()

    // Reset-all button is present (always rendered).
    await expect(
      page.getByTestId("edge-panel-settings-reset-all"),
    ).toBeVisible()
  })

  test("hiding a placement, saving, reload preserves state", async ({ page }) => {
    await loginAsTestcoAdmin(page)
    await page.goto(`${STAGING_FRONTEND}/settings/edge-panel`)
    await page.waitForLoadState("networkidle")

    const root = page.getByTestId("edge-panel-settings-page")
    await root.waitFor({ state: "visible", timeout: 15_000 })

    // Hide first tenant placement we can find.
    const hideButtons = page.locator(
      '[data-testid^="edge-panel-settings-placement-toggle-hide-"]',
    )
    const firstHide = hideButtons.first()
    await firstHide.waitFor({ state: "visible", timeout: 10_000 })
    await firstHide.click()

    // Unsaved indicator appears.
    await expect(
      page.getByTestId("edge-panel-settings-unsaved-indicator"),
    ).toBeVisible()

    // Save the change.
    await page.getByTestId("edge-panel-settings-save").click()
    // Indicator should disappear after save.
    await expect(
      page.getByTestId("edge-panel-settings-unsaved-indicator"),
    ).not.toBeVisible({ timeout: 10_000 })

    // Reload and verify the state survived (a placement is still
    // marked as hidden in the page-row attribute layer).
    await page.reload()
    await page.waitForLoadState("networkidle")
    await root.waitFor({ state: "visible", timeout: 15_000 })
    // At least one placement should still be in hidden state.
    const hiddenPlacement = page.locator(
      '[data-testid^="edge-panel-settings-placement-"][data-hidden="true"]',
    )
    await expect(hiddenPlacement.first()).toBeVisible({ timeout: 10_000 })
  })
})

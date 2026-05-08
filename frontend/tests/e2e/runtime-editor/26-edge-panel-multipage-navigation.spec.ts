/**
 * Gate 26 — Multi-page edge panel navigation via dots indicator.
 *
 * R-5.0 — when a panel has 2+ pages, the bottom dots indicator
 * lets the user switch between pages. Click on a dot updates the
 * active page; ArrowRight cycles forward.
 *
 * Spec runs against staging. Requires `seed_edge_panel.py` to seed
 * the canonical 2-page (Quick Actions + Dispatch) platform_default
 * composition.
 */
import { test, expect } from "@playwright/test"
import {
  loginAsHopkinsDirector,
  setupPage,
  STAGING_FRONTEND,
} from "./_shared"


test.describe("Gate 26 — Multi-page edge panel navigation", () => {
  test("dots reflect page count + click switches active page", async ({
    page,
  }) => {
    await setupPage(page)
    await loginAsHopkinsDirector(page)
    await page.goto(`${STAGING_FRONTEND}/home`)
    await page.waitForLoadState("networkidle")

    await page.keyboard.press("Meta+Shift+E")
    const dots = page.getByTestId("edge-panel-dots")
    await dots.waitFor({ state: "visible", timeout: 10_000 })

    // Two pages → two dots in the indicator.
    const dot0 = page.getByTestId("edge-panel-dot-0")
    const dot1 = page.getByTestId("edge-panel-dot-1")
    await expect(dot0).toBeVisible()
    await expect(dot1).toBeVisible()
    await expect(dot0).toHaveAttribute("data-active", "true")
    await expect(dot1).toHaveAttribute("data-active", "false")

    // Click dot 1 → active flips.
    await dot1.click()
    await expect(dot1).toHaveAttribute("data-active", "true")
    await expect(dot0).toHaveAttribute("data-active", "false")
  })
})

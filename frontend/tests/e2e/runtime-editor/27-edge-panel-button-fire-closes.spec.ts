/**
 * Gate 27 — R-4 button on edge panel fires action + auto-closes panel.
 *
 * R-5.0 close-on-fire pattern: when an R-4 RegisteredButton lives
 * inside an edge panel and is clicked, the dispatch fires + the
 * panel auto-closes (per `closePanelAfterFire` defaulting true on
 * the contract). The success behavior (toast / navigate / stay)
 * runs as before.
 *
 * Validates `navigate-to-pulse` button on the seeded default panel
 * (Quick Actions page).
 */
import { test, expect } from "@playwright/test"
import {
  loginAsHopkinsDirector,
  setupPage,
  STAGING_FRONTEND,
} from "./_shared"


test.describe("Gate 27 — Edge panel button fire closes panel", () => {
  test("clicking navigate-to-pulse fires + closes panel", async ({ page }) => {
    await setupPage(page)
    await loginAsHopkinsDirector(page)
    await page.goto(`${STAGING_FRONTEND}/home`)
    await page.waitForLoadState("networkidle")

    await page.keyboard.press("Meta+Shift+E")
    const panel = page.getByTestId("edge-panel")
    await panel.waitFor({ state: "visible", timeout: 10_000 })
    await expect(panel).toHaveAttribute("data-edge-panel-open", "true")

    // Find the navigate-to-pulse button — rendered through
    // RegisteredButton inside the panel composition. Looks up by the
    // composition placement's rendered button label or the data
    // attribute set on the wrapped boundary div.
    const button = page.locator(
      `[data-component-name="navigate-to-pulse"]`,
    ).first()
    await button.waitFor({ state: "visible", timeout: 10_000 })
    await button.click()

    // After dispatch, the panel auto-closes (close-on-fire default).
    await expect(panel).toHaveAttribute("data-edge-panel-open", "false", {
      timeout: 5_000,
    })
  })
})

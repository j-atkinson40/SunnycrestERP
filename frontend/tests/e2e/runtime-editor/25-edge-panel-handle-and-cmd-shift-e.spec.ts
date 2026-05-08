/**
 * Gate 25 — Edge panel handle visible + Cmd+Shift+E opens the panel.
 *
 * R-5.0 — first user-facing assertion: every authenticated tenant
 * route mounts EdgePanelHandle (right-edge tab) at z-edge-panel (96).
 * The keyboard hook also wires Cmd+Shift+E to toggle.
 *
 * Spec runs against staging. Requires r91 migration applied + the
 * default platform_default edge_panel composition seeded via
 * `seed_edge_panel.py`.
 */
import { test, expect } from "@playwright/test"
import {
  loginAsHopkinsDirector,
  setupPage,
  STAGING_FRONTEND,
} from "./_shared"


test.describe("Gate 25 — Edge panel handle + Cmd+Shift+E", () => {
  test("handle visible on authenticated route + Cmd+Shift+E opens panel", async ({
    page,
  }) => {
    await setupPage(page)
    await loginAsHopkinsDirector(page)
    await page.goto(`${STAGING_FRONTEND}/home`)
    await page.waitForLoadState("networkidle")

    // Handle is the always-visible right-edge tab.
    const handle = page.getByTestId("edge-panel-handle")
    await handle.waitFor({ state: "visible", timeout: 15_000 })

    // Cmd+Shift+E opens the panel.
    await page.keyboard.press("Meta+Shift+E")
    const panel = page.getByTestId("edge-panel")
    await panel.waitFor({ state: "visible", timeout: 5_000 })
    await expect(panel).toHaveAttribute("data-edge-panel-open", "true")

    // Esc closes.
    await page.keyboard.press("Escape")
    await expect(panel).toHaveAttribute("data-edge-panel-open", "false")
  })
})

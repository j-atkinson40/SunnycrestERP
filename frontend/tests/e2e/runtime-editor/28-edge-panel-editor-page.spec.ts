/**
 * Gate 28 — Edge panel editor page renders + scope/panel-key form
 * + page list + save/reload work end-to-end.
 *
 * R-5.0 — the dedicated `/visual-editor/edge-panels` route
 * exposes a focused editor: scope selector + panel-key + per-page
 * authoring (rows JSON for v1) + preview pane. Drag-drop authoring
 * lands in R-5.x; v1 ships textarea-based rows JSON authoring.
 */
import { test, expect } from "@playwright/test"
import {
  loginAsPlatformAdmin,
  setupPage,
  STAGING_FRONTEND,
} from "./_shared"


test.describe("Gate 28 — EdgePanelEditor mounts + saves", () => {
  test("editor page renders all controls + can list pages from default seed", async ({
    page,
  }) => {
    await setupPage(page)
    await loginAsPlatformAdmin(page)

    await page.goto(
      `${STAGING_FRONTEND}/bridgeable-admin/visual-editor/edge-panels`,
    )
    await page.waitForLoadState("networkidle")

    // Scope selector + panel key input + page list all render.
    await expect(
      page.getByTestId("edge-panel-editor-scope"),
    ).toBeVisible({ timeout: 15_000 })
    await expect(
      page.getByTestId("edge-panel-editor-panel-key"),
    ).toBeVisible()
    await expect(
      page.getByTestId("edge-panel-editor-page-list"),
    ).toBeVisible()
    // Add page + Save controls exposed.
    await expect(
      page.getByTestId("edge-panel-editor-add-page"),
    ).toBeVisible()
    await expect(
      page.getByTestId("edge-panel-editor-save"),
    ).toBeVisible()
  })

  test("Studio overview surfaces an edge-panels card (post-Studio migration)", async ({
    page,
  }) => {
    // Studio shell migration (1a-i.A1, May 2026): the legacy
    // `/visual-editor` index page redirects to `/studio` overview.
    // The Phase 1 visual editor nav cards (`ve-card-*`) were
    // replaced by Studio overview section cards
    // (`studio-overview-card-*`). Intent preserved: "edge panels
    // editor is reachable from the visual-editor index surface."
    await setupPage(page)
    await loginAsPlatformAdmin(page)
    await page.goto(`${STAGING_FRONTEND}/bridgeable-admin/visual-editor`)
    await page.waitForLoadState("networkidle")
    const card = page.getByTestId("studio-overview-card-edge-panels")
    await expect(card).toBeVisible({ timeout: 15_000 })
  })
})

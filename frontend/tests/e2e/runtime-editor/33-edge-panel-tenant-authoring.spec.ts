/**
 * Gate 33 — Edge panel tenant-default drag-drop authoring (R-5.2).
 *
 * R-5.0's JSON-textarea row authoring is retired. The
 * EdgePanelEditorPage now mounts the canonical R-3.1
 * InteractivePlacementCanvas substrate as its third consumer
 * (alongside CompositionEditorPage + FocusEditorPage's Composition
 * tab).
 *
 * Asserts:
 *   - The canvas root mounts at `/visual-editor/edge-panels`.
 *   - The R-5.0 textarea (data-testid="edge-panel-editor-rows-json")
 *     no longer renders.
 *   - R-5.0 spec 28's chrome (page list, Save button, etc.) stays
 *     green.
 */
import { test, expect } from "@playwright/test"
import {
  loginAsPlatformAdmin,
  setupPage,
  STAGING_FRONTEND,
} from "./_shared"


test.describe("Gate 33 — Edge panel tenant-default drag-drop authoring", () => {
  test("editor canvas mounts; JSON-textarea retired", async ({ page }) => {
    await setupPage(page)
    await loginAsPlatformAdmin(page)
    await page.goto(
      `${STAGING_FRONTEND}/bridgeable-admin/visual-editor/edge-panels`,
    )
    await page.waitForLoadState("networkidle")

    // R-5.2 — canvas substrate mounts (third consumer of the R-3.1
    // InteractivePlacementCanvas).
    await expect(
      page.getByTestId("edge-panel-editor-canvas"),
    ).toBeVisible({ timeout: 15_000 })

    // R-5.0's JSON textarea is retired (no fallback authoring path).
    await expect(page.getByTestId("edge-panel-editor-rows-json")).toHaveCount(
      0,
    )

    // R-5.0 spec 28 chrome still present — preserves the
    // backwards-compat assertion that the surrounding page-list +
    // panel-key + scope + save controls all still render.
    await expect(
      page.getByTestId("edge-panel-editor-scope"),
    ).toBeVisible()
    await expect(
      page.getByTestId("edge-panel-editor-panel-key"),
    ).toBeVisible()
    await expect(
      page.getByTestId("edge-panel-editor-page-list"),
    ).toBeVisible()
    await expect(
      page.getByTestId("edge-panel-editor-save"),
    ).toBeVisible()
  })
})

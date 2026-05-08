/**
 * Gate 29 — Mode-mutex with runtime editor.
 *
 * R-5.0 — the edge panel handle hides when runtime editor is in
 * `edit` mode (body[data-runtime-editor-mode="edit"]). When the
 * editor exits edit mode, the handle re-appears.
 *
 * This is one-way: open edge panel does NOT hide the editor's
 * inspector (different audiences). The mutex resolves the spatial
 * collision over the right edge of the viewport.
 */
import { test, expect } from "@playwright/test"
import {
  openEditorForTestco,
  STAGING_FRONTEND,
} from "./_shared"


test.describe("Gate 29 — Edge panel handle mode-mutex with runtime editor", () => {
  test("entering edit mode hides handle; exiting reveals", async ({ page }) => {
    const sess = await openEditorForTestco(page)
    const params =
      `?tenant=${encodeURIComponent(sess.tenantSlug)}` +
      `&user=${encodeURIComponent(sess.impersonatedUserId)}`
    await page.goto(
      `${STAGING_FRONTEND}/bridgeable-admin/runtime-editor/home${params}`,
    )
    await page.waitForLoadState("networkidle")

    // Pre-edit-mode: handle visible (runtime editor mounted but not
    // yet in edit mode).
    await expect(
      page.getByTestId("edge-panel-handle"),
    ).toBeVisible({ timeout: 15_000 })

    // Toggle edit mode.
    await page.getByTestId("runtime-editor-toggle").click()
    await expect(
      page.getByTestId("runtime-editor-edit-indicator"),
    ).toBeVisible({ timeout: 10_000 })

    // Handle should disappear under data-runtime-editor-mode="edit".
    await expect(
      page.getByTestId("edge-panel-handle"),
    ).not.toBeVisible({ timeout: 5_000 })

    // Toggle off — handle returns.
    await page.getByTestId("runtime-editor-toggle").click()
    await expect(
      page.getByTestId("edge-panel-handle"),
    ).toBeVisible({ timeout: 10_000 })
  })
})

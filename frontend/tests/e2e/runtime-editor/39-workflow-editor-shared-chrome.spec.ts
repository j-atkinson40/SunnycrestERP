/**
 * Gate 39 — Workflow editor shared chrome (Builder Craft Arc Phase 1a).
 *
 * Phase 1a piloted the shared Studio chrome set (PanelHeader / Toolbar /
 * Tooltip / Select / Icon) on the Workflow editor ONLY. This smoke asserts
 * the editor renders with the shared chrome mounted in a real browser:
 *
 *   1. The top bar is the shared PanelHeader (data-slot="panel-header")
 *   2. The actions cluster is a real toolbar (role="toolbar")
 *   3. The action buttons survived the adoption (testids preserved)
 *
 * Visual parity is the phase contract — this is a structure smoke, not a
 * visual diff. The other 6 builders are intentionally NOT asserted here
 * (they adopt at follower velocity later).
 */
import { test, expect } from "@playwright/test"
import { STAGING_FRONTEND, loginAsPlatformAdmin } from "./_shared"

test.describe("Gate 39 — Workflow editor shared chrome (Craft 1a)", () => {
  test("workflow editor mounts with PanelHeader + Toolbar chrome", async ({
    page,
  }) => {
    await loginAsPlatformAdmin(page)
    await page.goto(
      `${STAGING_FRONTEND}/bridgeable-admin/visual-editor/workflows`,
    )

    // The editor page itself mounts.
    await expect(page.getByTestId("workflow-editor-page")).toBeVisible({
      timeout: 15_000,
    })

    // 1. Shared PanelHeader hosts the top bar.
    await expect(
      page.locator('[data-slot="panel-header"]').first(),
    ).toBeVisible()

    // 2. The actions cluster is a real toolbar with its accessible name.
    await expect(
      page.getByRole("toolbar", { name: "Workflow editor actions" }),
    ).toBeVisible()

    // 3. Action testids preserved through the adoption (parity guard).
    await expect(page.getByTestId("workflow-editor-save")).toBeVisible()
    await expect(page.getByTestId("workflow-editor-discard")).toBeVisible()
    await expect(
      page.getByTestId("workflow-editor-save-notify"),
    ).toBeVisible()
  })
})

/**
 * Gate 3: Click a registered widget in edit mode → selection border
 * appears + inspector panel mounts with Theme/Class/Props tabs.
 */
import { test, expect } from "@playwright/test"
import { openEditorForHopkins } from "./_shared"


test.describe("Gate 3 — click widget opens inspector", () => {
  test("click registered widget → selection overlay + 3-tab inspector", async ({
    page,
  }) => {
    await openEditorForHopkins(page)

    // Enter edit mode.
    await page.getByTestId("runtime-editor-toggle").click()
    await expect(
      page.getByTestId("runtime-editor-edit-indicator"),
    ).toBeVisible()

    // Find any registered widget on the dashboard. Hopkins FH director
    // dashboard renders at least one of: today, operator-profile,
    // recent-activity, anomalies, vault-schedule. Click the first
    // visible data-component-name boundary.
    const widget = page
      .locator("[data-component-name]")
      .first()
    await widget.waitFor({ state: "visible", timeout: 15_000 })
    await widget.click()

    // Selection overlay (brass border) renders.
    await expect(
      page.getByTestId("runtime-editor-selection-overlay"),
    ).toBeVisible({ timeout: 10_000 })

    // Inspector panel mounts with 3 tabs.
    await expect(page.getByTestId("runtime-inspector-panel")).toBeVisible()
    await expect(
      page.getByTestId("runtime-inspector-tab-theme"),
    ).toBeVisible()
    await expect(
      page.getByTestId("runtime-inspector-tab-class"),
    ).toBeVisible()
    await expect(
      page.getByTestId("runtime-inspector-tab-props"),
    ).toBeVisible()

    // Default active tab: Props.
    await expect(
      page.getByTestId("runtime-inspector-tab-props"),
    ).toHaveAttribute("data-active", "true")
  })
})

/**
 * Gate 15: AncillaryCard click-to-edit. Same shape as Gate 14 but
 * targets `data-component-name="ancillary-card"`. Renders inside the
 * scheduling Focus accessory rail (post-R-1.6.12 SchedulingFocus-
 * WithAccessories integration); the spec opens the Focus via Cmd+K
 * after entering edit mode.
 *
 * testco's seed_dispatch_demo populates 3 ancillary deliveries across
 * today + the next few days, so at least one AncillaryCard renders
 * inside the kanban core's accessory rail when the scheduling Focus
 * mounts.
 */
import { test, expect } from "@playwright/test"
import { openEditorForTestco } from "./_shared"


test.describe("Gate 15 — AncillaryCard click-to-edit", () => {
  test("click AncillaryCard inside scheduling Focus → inspector mounts with ancillary-card selected", async ({
    page,
  }) => {
    await openEditorForTestco(page)

    // Navigate to dispatcher kanban first; AncillaryCard renders
    // inside the same kanban core that hosts DeliveryCard.
    await page.goto(
      page.url().replace(/\/runtime-editor\/?.*$/, "/dispatch/funeral-schedule") +
        page.url().match(/\?.*/)![0],
    )
    await page.waitForLoadState("networkidle")

    await page.getByTestId("runtime-editor-toggle").click()
    await expect(
      page.getByTestId("runtime-editor-edit-indicator"),
    ).toBeVisible()

    // Wait for at least one AncillaryCard to render. seed_dispatch_demo
    // creates 3 ancillaries; if the dispatch surface has >0 visible
    // ancillary cards on today's schedule, the spec proceeds.
    const card = page
      .locator('[data-component-name="ancillary-card"]')
      .first()
    await card.waitFor({ state: "visible", timeout: 20_000 })
    await card.click()

    await expect(
      page.getByTestId("runtime-editor-selection-overlay"),
    ).toBeVisible({ timeout: 10_000 })

    await expect(page.getByTestId("runtime-inspector-panel")).toBeVisible()
    await expect(page.getByTestId("runtime-inspector-panel")).toContainText(
      "ancillary-card",
    )
  })
})

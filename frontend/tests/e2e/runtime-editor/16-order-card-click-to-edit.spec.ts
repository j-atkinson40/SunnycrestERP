/**
 * Gate 16: OrderCard click-to-edit. OrderCard renders in the
 * scheduling-board kanban-panel (route `/scheduling`), which is gated
 * by the `funeral-kanban` extension. testco doesn't currently have
 * that extension enabled — Hopkins FH does. So this spec drives the
 * Hopkins FH path (where the FH-side daily kanban is the canonical
 * OrderCard surface) and asserts the same `data-component-name=
 * "order-card"` boundary div + inspector mount.
 *
 * Why Hopkins not testco for this card specifically: per the
 * R-2.0 investigation, OrderCard's render sites are split — the
 * extracted file lives at components/delivery/OrderCard.tsx and is
 * imported by the kanban-panel which mounts on /scheduling. /scheduling
 * is the FH-side kanban (funeral-kanban extension) — Hopkins is the
 * canonical seeded fixture. testco's manufacturer-side surface uses
 * DeliveryCard via /dispatch/funeral-schedule (Gate 14).
 */
import { test, expect } from "@playwright/test"
import { openEditorForHopkins } from "./_shared"


test.describe("Gate 16 — OrderCard click-to-edit", () => {
  test("click OrderCard on /scheduling → inspector mounts with order-card selected", async ({
    page,
  }) => {
    await openEditorForHopkins(page)

    // Navigate the impersonated tenant tree to the FH-side kanban.
    await page.goto(
      page.url().replace(/\/runtime-editor\/?.*$/, "/scheduling") +
        page.url().match(/\?.*/)![0],
    )
    await page.waitForLoadState("networkidle")

    await page.getByTestId("runtime-editor-toggle").click()
    await expect(
      page.getByTestId("runtime-editor-edit-indicator"),
    ).toBeVisible()

    const card = page
      .locator('[data-component-name="order-card"]')
      .first()
    await card.waitFor({ state: "visible", timeout: 20_000 })
    await card.click()

    await expect(
      page.getByTestId("runtime-editor-selection-overlay"),
    ).toBeVisible({ timeout: 10_000 })

    await expect(page.getByTestId("runtime-inspector-panel")).toBeVisible()
    await expect(page.getByTestId("runtime-inspector-panel")).toContainText(
      "order-card",
    )
  })
})

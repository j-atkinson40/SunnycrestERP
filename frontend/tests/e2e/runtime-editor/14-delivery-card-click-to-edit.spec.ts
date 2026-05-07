/**
 * Gate 14: Click DeliveryCard inside the runtime editor under testco
 * impersonation → selection border + 3-tab inspector + delivery-card
 * resolves as the selected component name.
 *
 * Validates R-2.0's Path 1 wrapping for entity cards. Pre-R-2.0
 * DeliveryCard had no `data-component-name` boundary; SelectionOverlay's
 * capture-phase walker couldn't resolve a click on a DeliveryCard. This
 * spec asserts that the wrapped version (imported from
 * `lib/visual-editor/registry/registrations/entity-cards`) emits the
 * boundary div correctly and the inspector mounts with the right
 * registered name.
 */
import { test, expect } from "@playwright/test"
import { openEditorForTestco } from "./_shared"


test.describe("Gate 14 — DeliveryCard click-to-edit", () => {
  test("click DeliveryCard on /dispatch/funeral-schedule → inspector mounts with delivery-card selected", async ({
    page,
  }) => {
    await openEditorForTestco(page)

    // Navigate the impersonated tenant tree to the dispatcher's daily
    // surface. Editor shell wraps the tenant route tree; we navigate
    // INSIDE it via React Router, not a full page reload, so the
    // editor's edit-mode + writers state survives.
    await page.goto(
      page.url().replace(/\/runtime-editor\/?.*$/, "/dispatch/funeral-schedule") +
        page.url().match(/\?.*/)![0],
    )
    await page.waitForLoadState("networkidle")

    // Toggle edit mode.
    await page.getByTestId("runtime-editor-toggle").click()
    await expect(
      page.getByTestId("runtime-editor-edit-indicator"),
    ).toBeVisible()

    // Find a DeliveryCard. testco's seed_dispatch_demo populates ~5
    // kanban deliveries for today; the first visible card with
    // data-component-name="delivery-card" is the click target.
    const card = page
      .locator('[data-component-name="delivery-card"]')
      .first()
    await card.waitFor({ state: "visible", timeout: 15_000 })
    await card.click()

    // Selection overlay (brass border) appears.
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

    // The inspector resolves the selected component to "delivery-card"
    // (matches the registered name in entity-cards.ts).
    await expect(page.getByTestId("runtime-inspector-panel")).toContainText(
      "delivery-card",
    )
  })
})

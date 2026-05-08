/**
 * Gate 22: Click on a DeliveryCardHeader sub-section inside the
 * runtime editor → outer tabs strip [Card][Header][Body][Actions]
 * [Hole-dug-badge] mounts and the Header tab is active by default.
 *
 * R-2.1 — first arc surfacing the discriminated selection union
 * (`{kind: "component-section"}`) end-to-end through the editor:
 *
 *   1. SelectionOverlay's capture-phase walker resolves the deepest
 *      `[data-component-name]` ancestor (R-2.1 sub-section boundary
 *      inside the parent card boundary).
 *   2. When the resolved slug contains a dot, walker dispatches
 *      selectSection (not selectComponent), passing parent linkage
 *      from the registry's extensions.entityCardSection shape.
 *   3. EditModeContext.selection transitions to
 *      {kind: "component-section", parentKind, parentName, ...}.
 *   4. InspectorPanel reads selection + getSubSectionsFor + renders
 *      the outer tab strip; the section's tab is active by default.
 *
 * Surface: testco's daily dispatcher kanban
 * (/dispatch/funeral-schedule). seed_dispatch_demo populates
 * ~5 kanban deliveries per day so DeliveryCard renders.
 */
import { test, expect } from "@playwright/test"
import { openEditorForTestco } from "./_shared"


test.describe("Gate 22 — DeliveryCard sub-section click-to-edit", () => {
  test("click DeliveryCardHeader → outer tabs mount + Header tab active", async ({
    page,
  }) => {
    const sess = await openEditorForTestco(page)

    const params =
      `?tenant=${encodeURIComponent(sess.tenantSlug)}` +
      `&user=${encodeURIComponent(sess.impersonatedUserId)}`
    await page.goto(
      `/bridgeable-admin/runtime-editor/dispatch/funeral-schedule${params}`,
    )
    await page.waitForLoadState("networkidle")

    // Toggle edit mode.
    await page.getByTestId("runtime-editor-toggle").click()
    await expect(
      page.getByTestId("runtime-editor-edit-indicator"),
    ).toBeVisible({ timeout: 10_000 })

    // R-2.1 — clicking the header sub-section. The header's boundary
    // div nests inside the parent card's boundary div via Path 1
    // wrapping. SelectionOverlay walks UP from event.target and
    // stops at the deepest `[data-component-name]` — which is the
    // header's `delivery-card.header` slug.
    const headerSection = page
      .locator('[data-component-name="delivery-card.header"]')
      .first()
    await headerSection.waitFor({ state: "visible", timeout: 20_000 })
    await headerSection.click()

    // Brass selection border appears.
    await expect(
      page.getByTestId("runtime-editor-selection-overlay"),
    ).toBeVisible({ timeout: 10_000 })

    // Inspector panel mounts with R-2.1 outer tabs strip.
    await expect(page.getByTestId("runtime-inspector-panel")).toBeVisible()
    await expect(
      page.getByTestId("runtime-inspector-outer-tabs"),
    ).toBeVisible()

    // 5 outer tabs present: Card + 4 delivery-card sub-sections.
    await expect(
      page.getByTestId("runtime-inspector-outer-tab-card"),
    ).toBeVisible()
    await expect(
      page.getByTestId("runtime-inspector-outer-tab-delivery-card.header"),
    ).toBeVisible()
    await expect(
      page.getByTestId("runtime-inspector-outer-tab-delivery-card.body"),
    ).toBeVisible()
    await expect(
      page.getByTestId("runtime-inspector-outer-tab-delivery-card.actions"),
    ).toBeVisible()
    await expect(
      page.getByTestId(
        "runtime-inspector-outer-tab-delivery-card.hole-dug-badge",
      ),
    ).toBeVisible()

    // Header tab is active (selection is the section, not the parent).
    const headerTab = page.getByTestId(
      "runtime-inspector-outer-tab-delivery-card.header",
    )
    await expect(headerTab).toHaveAttribute("data-active", "true")
    const cardTab = page.getByTestId("runtime-inspector-outer-tab-card")
    await expect(cardTab).toHaveAttribute("data-active", "false")

    // Inspector header carries the section's displayName + slug.
    const inspectorName = page.getByTestId(
      "runtime-inspector-component-name",
    )
    await expect(inspectorName).toHaveText("Delivery Card · Header")
    await expect(inspectorName).toHaveAttribute(
      "data-component-slug",
      "delivery-card.header",
    )

    // Clicking the Card tab transitions inspector scope to the parent.
    await cardTab.click()
    await expect(cardTab).toHaveAttribute("data-active", "true")
    await expect(headerTab).toHaveAttribute("data-active", "false")
  })
})

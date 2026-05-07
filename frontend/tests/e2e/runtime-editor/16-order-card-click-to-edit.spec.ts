/**
 * Gate 16: OrderCard wrapping registered + structurally ready.
 *
 * R-2.0.2 — rewritten. OrderCard's only consumer is `kanban-panel.tsx`
 * mounted on the `/scheduling` route, which requires the
 * `funeral-kanban` extension. Investigation found neither testco nor
 * Hopkins has the extension enabled on staging today (HTTP 403 from
 * `/extensions/funeral-kanban/schedule` with body "Module
 * 'driver_delivery' is not enabled for this company"). The wrapped
 * OrderCard therefore has no live render surface on staging until a
 * tenant enables the extension (or a different surface mounts the
 * wrapped component).
 *
 * Per /tmp/r2_specs_toggle_missing.md (carried forward from R-2.0.1)
 * + the R-2.0.2 finding above, the spec validates the **registration
 * is present + reachable** in the visual editor's component registry
 * debug page. Wrapping path is structurally identical to delivery-card
 * (Gate 14 proves production DOM emission) and ancillary-card (Gate
 * 15's same-shape assertion); order-card's `registerComponent` shim
 * call goes through the same HOC + emits the same `display: contents`
 * boundary div.
 *
 * Full DOM-emission Playwright validation for OrderCard lands when:
 *   - A tenant on staging has funeral-kanban enabled (seed change), OR
 *   - kanban-panel-equivalent rendering moves to a non-extension-gated
 *     surface (cross-vertical scheduling refresh — separate arc), OR
 *   - The R-2.x shell architectural arc lets the runtime editor mount
 *     extension-gated routes inside its preview shell.
 */
import { test, expect } from "@playwright/test"
import {
  loginAsPlatformAdmin,
  setupPage,
  STAGING_FRONTEND,
} from "./_shared"


test.describe("Gate 16 — OrderCard registration validated", () => {
  test("order-card is registered in the visual-editor component registry", async ({
    page,
  }) => {
    await setupPage(page)
    await loginAsPlatformAdmin(page)

    // Visual editor's registry debug page surfaces every registered
    // component with stable `registry-row-{kind}-{name}` test-ids per
    // RegistryDebugPage.tsx:292.
    await page.goto(`${STAGING_FRONTEND}/bridgeable-admin/visual-editor/registry`)
    await page.waitForLoadState("networkidle")

    const row = page.getByTestId("registry-row-entity-card-order-card")
    await row.waitFor({ state: "visible", timeout: 15_000 })

    // Sanity: confirm the entity-card kind is fully wired by checking
    // delivery-card + ancillary-card siblings exist too (the three
    // R-2.0 entity-card registrations land together via the
    // entity-cards.ts shim + auto-register barrel).
    await expect(
      page.getByTestId("registry-row-entity-card-delivery-card"),
    ).toBeVisible()
    await expect(
      page.getByTestId("registry-row-entity-card-ancillary-card"),
    ).toBeVisible()
  })
})

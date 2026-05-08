/**
 * Gate 16: OrderCard wrapping registered + structurally ready.
 *
 * R-2.0.3 — kept as registry-presence (R-2.0.2 pattern) explicitly,
 * NOT restored to full-DOM editor click-to-edit. R-2.x converted
 * renderTenantSlugRoutes to relative paths so the editor shell
 * mounts arbitrary tenant routes (specs 14 + 15 restored to
 * full-DOM under R-2.0.3). But OrderCard's only consumer remains
 * `kanban-panel.tsx` on the `/scheduling` route, which requires the
 * `funeral-kanban` extension. Per R-2.0.2's investigation, neither
 * testco nor Hopkins has the extension enabled on staging (HTTP 403
 * from `/extensions/funeral-kanban/schedule`: "Module 'driver_delivery'
 * is not enabled for this company"). The wrapped OrderCard has no
 * live render surface on staging today.
 *
 * R-2.x routing fix unblocks the editor mounting `/scheduling`, but
 * the `/scheduling` page itself short-circuits to a 403/empty state
 * when funeral-kanban is disabled — the kanban-panel where OrderCard
 * lives never renders. So full-DOM Gate 16 remains gated on the
 * fixture change (enable funeral-kanban on a dev tenant) which is
 * a separate fixture arc, NOT R-2.0.3 scope.
 *
 * Validates the registration is present + reachable. Wrapping path
 * is structurally identical to delivery-card (Gate 14) and
 * ancillary-card (Gate 15) — same `registerComponent` HOC, same
 * `display: contents` boundary div, same auto-register barrel.
 *
 * Full DOM-emission Gate 16 lands when:
 *   - A dev tenant on staging has funeral-kanban enabled (fixture
 *     change), OR
 *   - kanban-panel-equivalent rendering moves to a non-extension-
 *     gated surface (cross-vertical scheduling refresh — separate
 *     arc).
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

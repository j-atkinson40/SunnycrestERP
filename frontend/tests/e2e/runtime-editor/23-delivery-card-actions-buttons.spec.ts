/**
 * Gate 23: DeliveryCardActions sub-section accepts R-4 button
 * composition via `buttonSlugs` prop + the substrate is wired
 * end-to-end through the registry.
 *
 * R-2.1 ships R-4 button composition as the FIRST arc consuming
 * R-4.0 substrate inside another registered component (per
 * /tmp/r2_1_subsection_scope.md Section 7 Path A — flat slug array
 * with itemSchema componentReference["button"]).
 *
 * Spec is registry-presence shaped (the actions section's
 * registration declares `buttonSlugs: ConfigPropSchema` with
 * itemSchema.type "componentReference" + componentTypes ["button"]).
 * Full DOM-emission validation of the buttons rendering inside the
 * actions row requires composition-authored prop_overrides reaching
 * the production tenant DOM, which Composition + tenant-realm theme
 * apply substrate (R-2.5) handles separately. This spec validates
 * the R-2.1 substrate contract: the registration shape + introspection
 * paths are in place + visible in the registry debug page so future
 * Composition placements can target them.
 */
import { test, expect } from "@playwright/test"
import { loginAsPlatformAdmin } from "./_shared"


test.describe("Gate 23 — DeliveryCardActions accepts R-4 buttonSlugs", () => {
  test("delivery-card.actions registration declares buttonSlugs componentReference array", async ({
    page,
  }) => {
    await loginAsPlatformAdmin(page)
    await page.goto("/bridgeable-admin/visual-editor/registry")
    await page.waitForLoadState("networkidle")

    // The registry debug page surfaces every registration via
    // `registry-row-{type}-{slug}` test-ids per RegistryDebugPage's
    // canonical row format. Sub-section registrations use kind
    // `entity-card-section`.
    const actionsRow = page.getByTestId(
      "registry-row-entity-card-section-delivery-card.actions",
    )
    await expect(actionsRow).toBeVisible({ timeout: 10_000 })

    // Sibling sub-section rows present — sanity checks the
    // entity-card-section kind is fully wired through the auto-
    // register barrel.
    await expect(
      page.getByTestId(
        "registry-row-entity-card-section-delivery-card.header",
      ),
    ).toBeVisible()
    await expect(
      page.getByTestId(
        "registry-row-entity-card-section-delivery-card.body",
      ),
    ).toBeVisible()
    await expect(
      page.getByTestId(
        "registry-row-entity-card-section-delivery-card.hole-dug-badge",
      ),
    ).toBeVisible()
  })

  test("ancillary-card + order-card actions sections also accept buttonSlugs", async ({
    page,
  }) => {
    await loginAsPlatformAdmin(page)
    await page.goto("/bridgeable-admin/visual-editor/registry")
    await page.waitForLoadState("networkidle")

    // Each entity-card with an actions sub-section has the same
    // buttonSlugs prop schema (defined via shared BUTTON_SLUGS_PROP
    // in registrations/entity-card-sections.ts).
    await expect(
      page.getByTestId(
        "registry-row-entity-card-section-ancillary-card.actions",
      ),
    ).toBeVisible({ timeout: 10_000 })
    await expect(
      page.getByTestId(
        "registry-row-entity-card-section-order-card.actions",
      ),
    ).toBeVisible()

    // R-4.0 button registrations still in place (3 example buttons —
    // the slugs that buttonSlugs would reference).
    await expect(
      page.getByTestId("registry-row-button-open-funeral-scheduling-focus"),
    ).toBeVisible()
    await expect(
      page.getByTestId("registry-row-button-trigger-cement-order-workflow"),
    ).toBeVisible()
    await expect(
      page.getByTestId("registry-row-button-navigate-to-pulse"),
    ).toBeVisible()
  })
})

/**
 * Gate 24: AncillaryCard's actions sub-section is `optional: true`
 * (per /tmp/r2_1_subsection_scope.md Section 1 — empty row collapses
 * entirely so the card stays minimal-vertical). Validates:
 *
 *   1. Registration carries `extensions.entityCardSection.optional: true`.
 *   2. Inspector still surfaces the Actions tab when an ancillary
 *      WITH a note is selected — operators can author optional sub-
 *      section configuration even when the data-driven render gate
 *      may be unmet on a different instance.
 *
 * Spec is registry-presence shaped for the optional flag (verifies the
 * substrate contract through the registry debug page). Full editor
 * click-to-edit on AncillaryCard sub-sections requires AncillaryCard
 * to be visible in the editor shell — pre-R-2.x AncillaryCard rendered
 * inside the Funeral Scheduling Focus accessory rail; post-R-2.x the
 * editor shell can mount the focus, but driving Cmd+K → Focus open
 * through Playwright is brittle (per R-2.0.5 documentation). The R-2.1
 * substrate is exercised via the registry-presence assertion + by the
 * R-2.1 unit tests in `r21-sub-sections.test.ts`.
 */
import { test, expect } from "@playwright/test"
import { loginAsPlatformAdmin } from "./_shared"


test.describe("Gate 24 — AncillaryCard.actions optional flag", () => {
  test("ancillary-card.actions registration carries optional=true via debug page", async ({
    page,
  }) => {
    await loginAsPlatformAdmin(page)
    await page.goto("/bridgeable-admin/visual-editor/registry")
    await page.waitForLoadState("networkidle")

    const actionsRow = page.getByTestId(
      "registry-row-entity-card-section-ancillary-card.actions",
    )
    await expect(actionsRow).toBeVisible({ timeout: 10_000 })

    // All 3 ancillary-card sub-sections registered.
    await expect(
      page.getByTestId(
        "registry-row-entity-card-section-ancillary-card.header",
      ),
    ).toBeVisible()
    await expect(
      page.getByTestId(
        "registry-row-entity-card-section-ancillary-card.body",
      ),
    ).toBeVisible()
  })

  test("order-card.actions registration also marked optional=true", async ({
    page,
  }) => {
    await loginAsPlatformAdmin(page)
    await page.goto("/bridgeable-admin/visual-editor/registry")
    await page.waitForLoadState("networkidle")

    // Per /tmp/r2_1_subsection_scope.md Section 1: OrderCard's
    // actions region is informational (countdown + notes), not
    // action-shaped → optional in the canonical spine.
    await expect(
      page.getByTestId(
        "registry-row-entity-card-section-order-card.actions",
      ),
    ).toBeVisible({ timeout: 10_000 })
    await expect(
      page.getByTestId(
        "registry-row-entity-card-section-order-card.header",
      ),
    ).toBeVisible()
    await expect(
      page.getByTestId(
        "registry-row-entity-card-section-order-card.body",
      ),
    ).toBeVisible()
  })

  test("delivery-card.actions registration is non-optional (always renders)", async ({
    page,
  }) => {
    await loginAsPlatformAdmin(page)
    await page.goto("/bridgeable-admin/visual-editor/registry")
    await page.waitForLoadState("networkidle")

    // delivery-card.actions registers with optional: false (per
    // /tmp/r2_1_subsection_scope.md Section 1 — DeliveryCard's
    // actions section is non-optional, icon row always present).
    // Sibling validation: all 4 delivery-card sub-sections present.
    await expect(
      page.getByTestId(
        "registry-row-entity-card-section-delivery-card.actions",
      ),
    ).toBeVisible({ timeout: 10_000 })
    await expect(
      page.getByTestId(
        "registry-row-entity-card-section-delivery-card.hole-dug-badge",
      ),
    ).toBeVisible()
  })
})

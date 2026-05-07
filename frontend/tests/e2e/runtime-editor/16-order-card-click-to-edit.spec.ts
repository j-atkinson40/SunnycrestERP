/**
 * Gate 16: OrderCard `data-component-name` reaches production DOM.
 *
 * R-2.0.1 — rewritten from runtime-editor click-to-edit to production-
 * tenant-DOM validation, mirroring Gate 14's shape. See
 * /tmp/r2_specs_toggle_missing.md for the architectural finding.
 *
 * OrderCard's canonical surface is the FH-side scheduling kanban at
 * `/scheduling`, which is gated by the `funeral-kanban` extension.
 * Hopkins FH has it enabled; testco doesn't. Spec drives the Hopkins
 * direct-tenant path (NOT impersonation — same R-2.0.1 pattern as
 * Gate 14).
 */
import { test, expect } from "@playwright/test"
import { loginAsHopkinsDirector } from "./_shared"


test.describe("Gate 16 — OrderCard wrapping reaches production DOM", () => {
  test("data-component-name=order-card present on /scheduling", async ({
    page,
  }) => {
    await loginAsHopkinsDirector(page)

    // Navigate to the FH-side scheduling kanban. seed_fh_demo
    // populates demo cases; the kanban-panel renders OrderCard for
    // each scheduled delivery.
    await page.goto("/scheduling")
    await page.waitForLoadState("networkidle")

    // Assert the wrapped OrderCard boundary div emits
    // data-component-name in production DOM. R-2.0's extraction of
    // OrderCard from kanban-panel.tsx + Path 1 wrapping at
    // entity-cards.ts shim + render-site rewrite at kanban-panel
    // are all upstream of this assertion.
    const card = page.locator('[data-component-name="order-card"]').first()
    await card.waitFor({ state: "visible", timeout: 20_000 })

    const childCount = await card.evaluate((el) => el.children.length)
    expect(childCount).toBeGreaterThan(0)
  })
})

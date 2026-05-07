/**
 * Gate 14: DeliveryCard `data-component-name` reaches production DOM.
 *
 * R-2.0.1 — rewritten from runtime-editor click-to-edit to production-
 * tenant-DOM validation. See /tmp/r2_specs_toggle_missing.md for the
 * architectural finding: R-2.0's original spec design assumed the
 * runtime editor shell could mount tenant routes beyond HomePage —
 * the current shell architecture (TenantRouteTree's inner `<Routes>`
 * matching against full URL pathname rather than splat-relative)
 * supports only `/` and `*`-catch-all, both of which fall through to
 * HomePage. Mounting `/dispatch/funeral-schedule` inside the shell
 * needs `BrowserRouter basename` (or equivalent) wired into
 * TenantProviders — that's an R-2.x architectural arc, not a 5-LOC
 * spec fix.
 *
 * What this spec asserts INSTEAD: the foundational R-2.0 + R-2.5
 * promise that wrapped DeliveryCard emits the
 * `data-component-name="delivery-card"` boundary div on the actual
 * user-facing surface (`/dispatch/funeral-schedule` for testco
 * dispatcher daily use). This validates:
 *   - R-1.6.12 Path 1 widget wrapping extends to entity cards
 *   - R-2.0's `registrations/entity-cards.ts` shim wraps + exports
 *     the cards correctly
 *   - Render-site rewrites hit the wrapped versions (eslint-rule-
 *     enforced, but Playwright proves runtime DOM emission)
 *   - R-2.5's tenant-realm theme apply runs on this route too
 *
 * Click-to-edit on entity cards within the runtime editor lands
 * post-R-2.x once the shell mounts arbitrary tenant routes.
 */
import { test, expect } from "@playwright/test"
import { loginAsTestcoAdmin } from "./_shared"


test.describe("Gate 14 — DeliveryCard wrapping reaches production DOM", () => {
  test("data-component-name=delivery-card present on /dispatch/funeral-schedule", async ({
    page,
  }) => {
    await loginAsTestcoAdmin(page)

    // Navigate the production tenant tree to the dispatcher daily
    // surface. seed_dispatch_demo populates ~5 kanban deliveries for
    // today; DeliveryCard renders for each.
    await page.goto("/dispatch/funeral-schedule")
    await page.waitForLoadState("networkidle")

    // Assert the wrapped DeliveryCard boundary div emits
    // data-component-name in production DOM. The wrapping is
    // R-2.0's foundational guarantee — without it, click-to-edit
    // can never work regardless of editor shell architecture.
    const card = page
      .locator('[data-component-name="delivery-card"]')
      .first()
    await card.waitFor({ state: "visible", timeout: 20_000 })

    // Sanity: the boundary div is `display: contents` so it doesn't
    // affect layout — assert it has a child element (the original
    // DeliveryCardRaw render).
    const childCount = await card.evaluate((el) => el.children.length)
    expect(childCount).toBeGreaterThan(0)
  })
})

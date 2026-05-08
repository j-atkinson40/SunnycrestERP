/**
 * Gate 14: Click DeliveryCard inside the runtime editor on
 * `/dispatch/funeral-schedule` (testco) → selection overlay + 3-tab
 * inspector + delivery-card resolves as the selected component.
 *
 * R-2.0.3 — restored to full-DOM editor click-to-edit. R-2.0.1 had
 * rewritten this to a production-DOM-only check because the editor
 * shell could only render HomePage regardless of path hint
 * (TenantRouteTree's nested <Routes> matched against full URL
 * pathname; absolute-path routes inside the splat parent didn't
 * match → R-1.6.9 catch-all `*` → HomePage). R-2.x converted
 * renderTenantSlugRoutes to relative paths; the editor shell now
 * mounts arbitrary tenant routes inside its splat. Spec returns to
 * its R-2.0 design.
 *
 * Validates:
 *   - R-2.x routing: editor mounts /dispatch/funeral-schedule
 *   - R-2.0 Path 1 wrapping: DeliveryCard emits
 *     data-component-name="delivery-card" boundary div
 *   - SelectionOverlay capture-phase walker resolves entity-card
 *     clicks
 *   - InspectorPanel mounts with the registered component (Delivery
 *     Card / delivery-card) + 3 tabs (theme/class/props)
 *
 * Surface: testco's daily dispatcher kanban. seed_dispatch_demo
 * populates ~5 kanban deliveries for today; DeliveryCard renders
 * for each.
 */
import { test, expect } from "@playwright/test"
import { openEditorForTestco } from "./_shared"


test.describe("Gate 14 — DeliveryCard click-to-edit", () => {
  test("click DeliveryCard inside editor → inspector mounts with delivery-card selected", async ({
    page,
  }) => {
    const sess = await openEditorForTestco(page)

    // Editor shell currently at /bridgeable-admin/runtime-editor/
    // ?tenant=testco&user=...; navigate to the dispatcher daily
    // surface inside the shell. Splat remainder
    // `dispatch/funeral-schedule` resolves to the relative
    // `<Route path="dispatch/funeral-schedule">` per R-2.x's universal
    // relative-paths conversion. Query params preserved (the editor
    // shell reads tenant + user from useSearchParams).
    const params =
      `?tenant=${encodeURIComponent(sess.tenantSlug)}` +
      `&user=${encodeURIComponent(sess.impersonatedUserId)}`
    await page.goto(
      `/bridgeable-admin/runtime-editor/dispatch/funeral-schedule${params}`,
    )
    await page.waitForLoadState("networkidle")

    // Toggle edit mode. Pre-toggle the selection overlay isn't
    // armed — clicks would fall through to widget-level handlers.
    await page.getByTestId("runtime-editor-toggle").click()
    await expect(
      page.getByTestId("runtime-editor-edit-indicator"),
    ).toBeVisible({ timeout: 10_000 })

    // Find a DeliveryCard. seed_dispatch_demo guarantees today has
    // at least 5 kanban deliveries on testco. Boundary div is
    // display:contents (R-2.0 wrapping pattern); the click can land
    // on the boundary OR a child — SelectionOverlay's capture-phase
    // walker resolves to the nearest [data-component-name] ancestor.
    const card = page
      .locator('[data-component-name="delivery-card"]')
      .first()
    await card.waitFor({ state: "visible", timeout: 20_000 })
    await card.click()

    // Brass selection border appears.
    await expect(
      page.getByTestId("runtime-editor-selection-overlay"),
    ).toBeVisible({ timeout: 10_000 })

    // Inspector panel mounts with the 3-tab strip.
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

    // Inspector header renders the registered displayName "Delivery
    // Card" + carries data-component-slug="delivery-card" (the
    // slug-form name from registrations/entity-cards.ts). Asserting
    // both: visible text confirms the user-facing surface; data
    // attribute confirms the registered slug reaches the inspector.
    const componentName = page.getByTestId("runtime-inspector-component-name")
    await expect(componentName).toHaveText("Delivery Card")
    await expect(componentName).toHaveAttribute(
      "data-component-slug",
      "delivery-card",
    )
  })
})

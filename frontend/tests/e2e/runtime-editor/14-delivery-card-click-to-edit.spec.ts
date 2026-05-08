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

    // R-2.1.1 — funeral-schedule pre-mounts every day as an absolute-
    // positioned layer (funeral-schedule.tsx:1010+); inactive days sit
    // at translateY(±100%) clipped by the stage's overflow-hidden.
    // Cards in inactive panes are in the DOM but rendered offscreen
    // via CSS transform — Playwright's auto-scroll-into-view cannot
    // bring CSS-transform-positioned elements into view. The locator
    // MUST scope to the active day pane (data-active="true") so
    // .first() lands on a visible card. The pre-mount + transform
    // pattern is intentional iOS-Smart-Stack day-rotation UX; spec-
    // side scoping is the canonical fix per /tmp/r2_1_1_viewport_
    // regression.md Section 4.
    //
    // Click target is the parent boundary div with display:contents.
    // dispatchEvent("click") is the canonical Playwright primitive
    // for triggering SelectionOverlay's capture-phase walker on a
    // display:contents element — fires the click event ON the wrapper
    // directly, bypassing element-from-point + viewport checks. Walker
    // reads e.target, finds data-component-name="delivery-card" on the
    // target itself, dispatches selectComponent("delivery-card").
    const card = page
      .locator(
        '[data-slot="dispatch-fs-day-pane"][data-active="true"] ' +
          '[data-component-name="delivery-card"]',
      )
      .first()
    await card.waitFor({ state: "attached", timeout: 20_000 })
    await card.dispatchEvent("click")

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

/**
 * Gate 15: Click AncillaryCard inside the runtime editor with the
 * funeral-scheduling Focus open → selection overlay + 3-tab inspector
 * + ancillary-card resolves as the selected component.
 *
 * R-2.0.3 — restored to full-DOM editor click-to-edit. R-2.0.1 had
 * rewritten this to a registry-presence assertion because:
 *   1. Editor shell couldn't mount /dispatch/funeral-schedule
 *      pre-R-2.x (TenantRouteTree absolute-path mismatch issue).
 *   2. AncillaryCard renders ONLY inside `SchedulingKanbanCore`, which
 *      mounts as the funeral-scheduling Focus's operational core.
 *      Driving Cmd+K → "scheduling" Focus open through Playwright was
 *      flaky.
 *
 * R-2.x converted renderTenantSlugRoutes to relative paths so the
 * editor shell mounts arbitrary tenant routes. The Focus opens via
 * URL `?focus=funeral-scheduling` query param (FocusContext reads
 * `focusParam = searchParams.get("focus")` and auto-opens on mount —
 * `focus-context.tsx:186 + :207-219`). URL-driven Focus open is more
 * reliable than Cmd+K interaction in Playwright.
 *
 * Validates:
 *   - R-2.x routing: editor mounts /dispatch/funeral-schedule
 *   - URL-driven Focus open via ?focus=funeral-scheduling
 *   - R-2.0 Path 1 wrapping: AncillaryCard emits
 *     data-component-name="ancillary-card" boundary div inside the
 *     Focus core
 *   - SelectionOverlay capture-phase walker resolves clicks on
 *     AncillaryCard inside the Focus
 *   - InspectorPanel mounts with the registered component (Ancillary
 *     Card / ancillary-card) + 3 tabs
 *
 * Surface: testco's funeral-scheduling Focus. seed_dispatch_demo
 * populates ancillary deliveries (kanban-attached + standalone);
 * AncillaryCard renders for standalone ancillaries inside the Focus
 * kanban (`SchedulingKanbanCore.tsx:1190 + :1476`).
 */
import { test, expect } from "@playwright/test"
import { openEditorForTestco } from "./_shared"


test.describe("Gate 15 — AncillaryCard click-to-edit", () => {
  test("click AncillaryCard inside editor (Focus open) → inspector mounts with ancillary-card selected", async ({
    page,
  }) => {
    const sess = await openEditorForTestco(page)

    // Navigate to dispatch surface inside editor shell + auto-open
    // the funeral-scheduling Focus via URL param. Editor shell reads
    // `?tenant` + `?user` from useSearchParams; FocusContext reads
    // `?focus`. All three coexist in the same query string.
    const params =
      `?tenant=${encodeURIComponent(sess.tenantSlug)}` +
      `&user=${encodeURIComponent(sess.impersonatedUserId)}` +
      `&focus=funeral-scheduling`
    await page.goto(
      `/bridgeable-admin/runtime-editor/dispatch/funeral-schedule${params}`,
    )
    await page.waitForLoadState("networkidle")

    // Toggle edit mode. The Focus core mounts inside the editor's
    // tenant content wrapper; SelectionOverlay's
    // [data-runtime-host-root] boundary still applies — clicks
    // inside the Focus get walked up to the AncillaryCard boundary
    // div, not bubbled into editor chrome.
    await page.getByTestId("runtime-editor-toggle").click()
    await expect(
      page.getByTestId("runtime-editor-edit-indicator"),
    ).toBeVisible({ timeout: 10_000 })

    // Find an AncillaryCard. seed_dispatch_demo populates standalone
    // ancillary deliveries that render via SchedulingKanbanCore.
    // First match wins; SelectionOverlay walks up to the boundary.
    const card = page
      .locator('[data-component-name="ancillary-card"]')
      .first()
    await card.waitFor({ state: "visible", timeout: 20_000 })
    await card.click()

    // Selection overlay (brass border) on the clicked card.
    await expect(
      page.getByTestId("runtime-editor-selection-overlay"),
    ).toBeVisible({ timeout: 10_000 })

    // Inspector panel mounts with 3-tab strip.
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

    // Inspector resolves ancillary-card. Visible text shows the
    // registered displayName "Ancillary Card"; data-component-slug
    // carries the slug from registrations/entity-cards.ts.
    const componentName = page.getByTestId("runtime-inspector-component-name")
    await expect(componentName).toHaveText("Ancillary Card")
    await expect(componentName).toHaveAttribute(
      "data-component-slug",
      "ancillary-card",
    )
  })
})

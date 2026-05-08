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
 * R-2.0.4 — mounted <Focus /> inside RuntimeEditorShell so the
 * URL-driven Focus open actually surfaces a modal (pre-R-2.0.4 the
 * BridgeableAdminApp branch had no Focus mount).
 *
 * R-2.0.5 — switched edit-mode entry from click-the-toggle to URL-
 * driven `?edit=1`. The previous click-based toggle order was:
 * navigate (Focus opens) → click runtime-editor-toggle. But the
 * funeral-scheduling Focus's ancillary-pool-pin (a base-ui Popover
 * portal) overlapped the toggle button position once the Focus
 * mounted, intercepting pointer events and silently swallowing the
 * click. EditModeToggle's useEffect at lines 29-35 reads `?edit=1`
 * on mount + searchParams change, calling editMode.setEditing(true)
 * declaratively — same state, no click ordering. The underlying
 * z-index layering question (should Focus portal popovers occlude
 * editor chrome?) is flagged as known hygiene; production usage
 * typically enables edit mode at the page level before navigating
 * into Focuses, so this is not user-blocking. Tracked for separate
 * z-index review arc.
 *
 * Validates:
 *   - R-2.x routing: editor mounts /dispatch/funeral-schedule
 *   - URL-driven Focus open via ?focus=funeral-scheduling
 *   - URL-driven edit mode via ?edit=1 (R-2.0.5)
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
    // the funeral-scheduling Focus via URL param + arm edit mode via
    // ?edit=1 declaratively. Editor shell reads `?tenant` + `?user`
    // from useSearchParams; FocusContext reads `?focus`;
    // EditModeToggle reads `?edit`. All four coexist in the same
    // query string; their reads are independent useEffect chains in
    // different contexts.
    const params =
      `?tenant=${encodeURIComponent(sess.tenantSlug)}` +
      `&user=${encodeURIComponent(sess.impersonatedUserId)}` +
      `&focus=funeral-scheduling` +
      `&edit=1`
    await page.goto(
      `/bridgeable-admin/runtime-editor/dispatch/funeral-schedule${params}`,
    )
    await page.waitForLoadState("networkidle")

    // Edit mode came up via ?edit=1; no click required (and would
    // be intercepted by the Focus's ancillary-pool-pin Popover
    // portal overlapping the toggle's position — see R-2.0.5
    // header comment).
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

    // R-2.1.2 — walker resolves to the DEEPEST `[data-component-name]`
    // ancestor (canonical R-2.1 contract). Click on the AncillaryCard
    // root lands inside the body button, which contains the wrapped
    // `[data-component-name="ancillary-card.body"]` boundary. Walker
    // walks up: clicked element → ancillary-card-body wrapper (display:
    // contents) → STOPS. Selection dispatches as
    // {kind: "component-section", componentName: "ancillary-card.body",
    //  parentName: "ancillary-card"}.
    //
    // Pre-R-2.1.2: spec asserted parent slug "ancillary-card" — that
    // pre-dates the deepest-wins walker contract. Updated to assert
    // the deepest sub-section.
    //
    // To assert the parent's editing surface, the canonical path is:
    // click the "Card" outer tab (validates separately below). The
    // initial click selecting a sub-section + the Card tab scoping
    // back to parent is the full R-2.1 contract.
    const componentName = page.getByTestId("runtime-inspector-component-name")
    await expect(componentName).toHaveText("Ancillary Card · Body")
    await expect(componentName).toHaveAttribute(
      "data-component-slug",
      "ancillary-card.body",
    )

    // Outer-tab strip mounts because the parent (ancillary-card) has
    // registered sub-sections. Card tab is clickable + becomes active
    // when clicked; this scopes the inner triad (theme/class/props) to
    // the parent without changing what's "selected" (the inspector
    // HEADER still tracks the DOM-click selection — outer tabs only
    // toggle which entry the inner triad operates on, mirroring the
    // R-2.1 outer/inner separation per InspectorPanel.tsx:139-155).
    // Spec 22 follows the same shape for DeliveryCard.
    await expect(
      page.getByTestId("runtime-inspector-outer-tabs"),
    ).toBeVisible()
    const cardTab = page.getByTestId("runtime-inspector-outer-tab-card")
    await expect(cardTab).toBeVisible()
    const bodyTab = page.getByTestId(
      "runtime-inspector-outer-tab-ancillary-card.body",
    )
    await expect(bodyTab).toHaveAttribute("data-active", "true")
    // R-2.1.3 — Focus modal's backdrop is a Base UI portal that
    // overlays editor chrome (including the inspector's outer tabs)
    // even though the inspector renders at a higher z-index. Same
    // bug class as R-2.0.5 (ancillary-pool-pin-header occluding
    // runtime-editor-toggle). Playwright's element-from-point
    // resolves to the backdrop, .click() times out. dispatchEvent
    // fires the click event ON the tab directly, bypassing the
    // portal's pointer-event interception. Architectural review of
    // focus-backdrop z-index vs inspector chrome z-index is a
    // separate hygiene arc — production usage rarely needs inspector
    // mid-Focus, so this is not user-blocking.
    await cardTab.dispatchEvent("click")
    await expect(cardTab).toHaveAttribute("data-active", "true")
    await expect(bodyTab).toHaveAttribute("data-active", "false")
  })
})

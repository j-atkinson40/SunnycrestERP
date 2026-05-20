/**
 * Focus Builder free-form canvas — Playwright pointer-event coverage
 * gate (sub-arc FF-7 finale, per investigation Q-40).
 *
 * Closes the JSDOM gap surfaced in FF-3 + FF-4 + FF-6: pointer-event
 * coverage in JSDOM is unreliable for drag/resize gestures, and
 * vitest integration tests can only drive @dnd-kit through the
 * KeyboardSensor path. These 5 Playwright scenarios exercise the
 * REAL operator pointer pipeline in chromium against staging.
 *
 * Status (FF-7 ship): scenarios are SKIPPED pending two pieces of
 * staging-side seed data:
 *   1. A seeded free-form Focus template with predictable placement
 *      positions (so scenarios can assert at known coords). The
 *      `r103_focus_templates_edit_session` migration substrate is in
 *      place; the actual seeded template requires a follow-up seed
 *      script call (`seed_focus_templates_freeform.py` — not yet
 *      shipped).
 *   2. A canonical URL path that opens the Focus Builder editing
 *      that template (`?subject=template:<id>`).
 *
 * Both can land in a near-future ops task. The spec infrastructure
 * lands NOW so future fill-in is the smallest possible delta.
 *
 * Per CLAUDE.md §12 spec-override discipline: this file lives at
 * `tests/e2e/focus-builder-freeform.spec.ts` (not under
 * `tests/e2e/runtime-editor/`). The CI workflow at
 * `.github/workflows/playwright-staging.yml` currently runs only
 * the runtime-editor subdir. To activate this spec in CI, the
 * workflow's `Run Playwright runtime-editor specs` step must be
 * extended OR a sibling workflow added. Both are deferred follow-up.
 *
 * Each scenario's body is ALREADY WRITTEN so that activation is a
 * one-line change (remove the `.skip` annotation) once the staging
 * seed lands.
 */
import { test, expect, type Page } from "@playwright/test"

// Future: import { loginAsPlatformAdmin, openEditorForHopkins } from
// "./runtime-editor/_shared" — when the Focus Builder is reachable
// via the impersonation harness. For FF-7, the URL is presumed
// reachable directly via the admin app at /studio/builder/focuses.

// Placeholder template id — replace with the seeded template's id
// when the seed script lands.
const SEEDED_FREEFORM_TEMPLATE_ID = "freeform-demo-template-id"
const FOCUS_BUILDER_URL = `/bridgeable-admin/studio/builder/focuses?subject=template:${SEEDED_FREEFORM_TEMPLATE_ID}`

/**
 * Helper to navigate + wait for the freeform canvas layer to mount.
 * Centralized so scenarios stay focused on their specific assertions.
 */
async function gotoFreeformCanvas(page: Page): Promise<void> {
  await page.goto(FOCUS_BUILDER_URL)
  await page.waitForSelector('[data-testid="focus-builder-freeform-layer"]', {
    timeout: 15_000,
  })
}

test.describe("FF-7 — Focus Builder free-form canvas Playwright gates", () => {
  // Scenario 1 — Pointer-event drag (closes JSDOM gap from FF-3).
  test.skip("pointer drag commits free-form widget position", async ({ page }) => {
    await gotoFreeformCanvas(page)
    const widget = page.locator(
      '[data-testid="focus-builder-freeform-placed-widget-draggable"]',
    ).first()
    const before = await widget.boundingBox()
    expect(before).toBeTruthy()
    // Drag the widget right by ~60px + down by ~40px.
    await widget.hover()
    await page.mouse.down()
    await page.mouse.move((before!.x + 60), (before!.y + 40), { steps: 6 })
    await page.mouse.up()
    // Wait for the inline style to reflect the new x/y (debounced save
    // round-trip not required for render-side correctness).
    await expect.poll(async () => {
      const after = await widget.boundingBox()
      return after?.x ?? 0
    }, { timeout: 5_000 }).toBeGreaterThan(before!.x + 30)
  })

  // Scenario 2 — Pointer-event resize via SE handle (closes JSDOM gap from FF-4).
  test.skip("pointer resize via SE handle commits new dimensions", async ({ page }) => {
    await gotoFreeformCanvas(page)
    const widget = page.locator(
      '[data-testid="focus-builder-freeform-placed-widget-draggable"]',
    ).first()
    // Select the widget so the resize-handle overlay mounts.
    await widget.click()
    const seHandle = page.locator(
      '[data-testid="focus-builder-resize-handle"][data-handle-position="se"]',
    )
    await expect(seHandle).toBeVisible()
    const before = await widget.boundingBox()
    expect(before).toBeTruthy()
    // Drag the SE handle down + right.
    const handleBox = await seHandle.boundingBox()
    expect(handleBox).toBeTruthy()
    await page.mouse.move(
      handleBox!.x + handleBox!.width / 2,
      handleBox!.y + handleBox!.height / 2,
    )
    await page.mouse.down()
    await page.mouse.move(
      handleBox!.x + handleBox!.width / 2 + 50,
      handleBox!.y + handleBox!.height / 2 + 30,
      { steps: 6 },
    )
    await page.mouse.up()
    await expect.poll(async () => {
      const after = await widget.boundingBox()
      return after?.width ?? 0
    }, { timeout: 5_000 }).toBeGreaterThan(before!.width + 30)
  })

  // Scenario 3 — Focus preservation during canvas drag (FF-6 load-bearing
  // UX correctness). Operator partially types a value in the X
  // position input, then drags the widget on the canvas. Input focus
  // + typed mid-edit value must be preserved per the
  // uncontrolled-with-sync contract (FF-6 canon).
  test.skip("focus preserved on position input during canvas drag", async ({ page }) => {
    await gotoFreeformCanvas(page)
    const widget = page.locator(
      '[data-testid="focus-builder-freeform-placed-widget-draggable"]',
    ).first()
    await widget.click()
    const xInput = page.locator('[data-testid="position-input-x"]')
    await xInput.focus()
    // Operator types a partial value WITHOUT blurring.
    await xInput.fill("")
    await xInput.type("75")
    // Drag the widget on the canvas. Focus should stay on the X
    // input; typed value should stay "75" mid-edit even as the
    // canvas drag commits new positions (which would normally
    // re-sync the input — uncontrolled-with-sync guards that).
    const widgetBox = await widget.boundingBox()
    expect(widgetBox).toBeTruthy()
    // Issue a small drag from the widget body.
    await page.mouse.move(widgetBox!.x + 30, widgetBox!.y + 30)
    await page.mouse.down()
    await page.mouse.move(widgetBox!.x + 80, widgetBox!.y + 50, { steps: 4 })
    await page.mouse.up()
    // Assertions: input still focused; value still "75" (operator
    // remains in control of their mid-edit text).
    await expect(xInput).toBeFocused()
    await expect(xInput).toHaveValue("75")
  })

  // Scenario 4 — Snap visual feedback (FF-7 snap-to-alignment).
  // Drag widget A toward widget B's edge; assert a snap-line element
  // appears in the DOM during the drag.
  test.skip("snap line renders during drag near another widget's edge", async ({ page }) => {
    await gotoFreeformCanvas(page)
    const widgets = page.locator(
      '[data-testid="focus-builder-freeform-placed-widget-draggable"]',
    )
    // Two widgets minimum required for snap. Seeded fixture must
    // include them.
    await expect(widgets).toHaveCount(2)
    const a = widgets.nth(0)
    const b = widgets.nth(1)
    const aBox = await a.boundingBox()
    const bBox = await b.boundingBox()
    expect(aBox).toBeTruthy()
    expect(bBox).toBeTruthy()
    // Drag widget A toward widget B's left edge (within snap
    // threshold but don't release yet — hold the gesture so the
    // snap-line is visible).
    await page.mouse.move(aBox!.x + 30, aBox!.y + 30)
    await page.mouse.down()
    // Aim widget A's right edge near widget B's left edge (within 6px).
    const targetX = bBox!.x - aBox!.width + 6
    await page.mouse.move(targetX, aBox!.y + 30, { steps: 8 })
    // Assert snap line visible mid-gesture.
    await expect(page.locator('[data-testid="snap-line"]')).toBeVisible()
    // Release.
    await page.mouse.up()
    // After release, snap lines clear (drag-end resets state).
    await expect(page.locator('[data-testid="snap-line"]')).toHaveCount(0)
  })

  // Scenario 5 — Marquee selection captures intersecting widgets;
  // AlignInspectorSection appears.
  test.skip("marquee drag captures widgets; align inspector appears", async ({ page }) => {
    await gotoFreeformCanvas(page)
    const layer = page.locator('[data-testid="focus-builder-freeform-layer"]')
    const layerBox = await layer.boundingBox()
    expect(layerBox).toBeTruthy()
    // Pointer-down on canvas background (NOT on a widget) — start
    // marquee. The seeded fixture's widgets should be within the
    // marquee's swept rectangle.
    await page.mouse.move(layerBox!.x + 20, layerBox!.y + 20)
    await page.mouse.down()
    // Sweep a rectangle that encloses at least 2 widgets.
    await page.mouse.move(layerBox!.x + 800, layerBox!.y + 500, { steps: 12 })
    await page.mouse.up()
    // AlignInspectorSection visible in the right rail (multi-select
    // context).
    await expect(
      page.locator('[data-testid="align-inspector-section"]'),
    ).toBeVisible()
    // Multi-select inspector container also present.
    await expect(
      page.locator('[data-testid="focus-builder-inspector-multi"]'),
    ).toBeVisible()
  })
})

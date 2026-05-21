/**
 * 2026-05-21 resize-live-preview fix arc — pointer-driven resize
 * preview regression gate.
 *
 * Background per docs/investigations/2026-05-20-resize-live-preview.md:
 *   Operator surfaced during staging verification of d9ffd90 that
 *   resize handles do not preview during drag. Pre-fix, the widget
 *   stayed at original dimensions throughout the gesture; only
 *   updated to final dimensions at pointer-release. FF-3 drag-to-move
 *   DID preview (via @dnd-kit's CSS `transform`); FF-4 resize did NOT
 *   (because @dnd-kit's transform model is position-only by design —
 *   dimensions need state-mediated rendering).
 *
 * Fix (Option A locked in §4): add a `parseResizeHandleId` branch to
 * `handleDragMove` in FocusBuilderPage.tsx; per-tick `updateWidget`
 * dispatch with cumulative @dnd-kit delta computed against a
 * drag-start placement snapshot.
 *
 * INTEGRATION PATH (option (d) — inline fixture + source-shape gate):
 *   - Per the 2026-05-20 hover-fix arc d9ffd90 precedent, this spec
 *     uses an inline HTML fixture via `page.setContent` because the
 *     seeded staging fixture for free-form Focus templates has not
 *     landed yet (existing `focus-builder-freeform.spec.ts` is .skip'd
 *     pending that seed).
 *   - The fixture reproduces the SHAPE — a positioned widget whose
 *     width/height are state-controlled, with a child resize handle
 *     that on pointer-drag continuously updates the widget's
 *     dimensions. Exercises real chromium pointer events end-to-end.
 *   - The fixture does NOT exercise production FocusBuilderPage.tsx
 *     handleDragMove. The PRODUCTION-PATH regression guard is the
 *     SOURCE-SHAPE GATE at FocusBuilderPage.test.tsx
 *     "FF-4 source-shape gate — handleDragMove contains a
 *     parseResizeHandleId branch" — that test reads
 *     FocusBuilderPage.tsx source as a string + asserts the resize
 *     branch is wired into handleDragMove. Catches future refactors
 *     that silently remove the live-preview branch.
 *   - When seeded staging fixture lands, this spec can be extended
 *     (or a sibling spec added) that navigates to a real Focus
 *     Builder URL, locates a real resize handle, and exercises the
 *     same gesture against production code.
 *
 * Why option (d) for this arc:
 *   - Option (a) seeded staging: same blocker as the hover-fix arc —
 *     CI bot auth + seeded free-form template pending.
 *   - Option (b) dev-server: high infrastructure overhead for ~35 LOC
 *     of production change.
 *   - Option (c) unskip FF-4/FF-7 specs: same staging dependency.
 *   - Option (d, chosen): inline fixture + source-shape gate. The
 *     production-path regression guard is the source-shape gate; the
 *     pointer-event interaction in real chromium is exercised
 *     generically via the inline fixture (proves the operator-
 *     observable property "widget dimensions update during drag").
 *
 * Pre-fix outcome:
 *   - This spec's inline-fixture path does NOT exercise production
 *     handleDragMove, so the spec's mid-drag assertion may pass
 *     pre-fix on the fixture in isolation. The load-bearing pre-fix-
 *     fails assertion is the SOURCE-SHAPE GATE (vitest). Documented
 *     candidly per the hover-fix arc d9ffd90 precedent.
 */
import { test, expect } from "@playwright/test"

const FIXTURE_HTML = `
<!doctype html>
<html>
<head>
<meta charset="utf-8" />
<style>
  body { margin: 0; padding: 24px; font-family: sans-serif; background: #f5f5f5; }
  .layer { position: relative; width: 1000px; height: 600px; background: #fff; border: 1px solid #ccc; }
  .widget {
    position: absolute;
    background: #e5e7eb;
    border: 1px solid #6b7280;
    box-sizing: border-box;
    cursor: grab;
  }
  .handle {
    position: absolute;
    width: 16px;
    height: 16px;
    background: #f59e0b;
    border: 1px solid #b45309;
    box-sizing: border-box;
    cursor: nwse-resize;
    z-index: 10;
  }
  .h-se { bottom: -8px; right: -8px; }
</style>
</head>
<body>
  <div class="layer" id="canvas">
    <div id="widget"
         class="widget"
         data-testid="focus-builder-freeform-placed-widget-draggable"
         style="left: 100px; top: 100px; width: 240px; height: 120px;">
      <div class="handle h-se"
           data-testid="focus-builder-resize-handle"
           data-handle-position="se"></div>
    </div>
  </div>

<script>
  // Reproduces the SHAPE of the production resize gesture:
  //   - Widget width/height are JS-state-driven (mirror of React
  //     state controlling the wrapper's inline width/height).
  //   - Pointer drag on the SE handle continuously updates state,
  //     which paints the widget at the new dimensions every frame.
  //   - At pointer-up, final dimensions persist.
  //
  // This is the post-fix behavior shape. The production fix flows
  // through @dnd-kit + handleDragMove + updateWidget instead, but the
  // operator-observable property — "widget dimensions change during
  // drag, not only at release" — is what this fixture verifies in
  // real chromium.
  (function() {
    const widget = document.getElementById('widget')
    const handle = widget.querySelector('[data-testid="focus-builder-resize-handle"]')
    let dragging = false
    let startX = 0
    let startY = 0
    let startW = 240
    let startH = 120

    handle.addEventListener('pointerdown', function(e) {
      e.preventDefault()
      e.stopPropagation()
      dragging = true
      startX = e.clientX
      startY = e.clientY
      startW = widget.offsetWidth
      startH = widget.offsetHeight
      handle.setPointerCapture(e.pointerId)
    })

    handle.addEventListener('pointermove', function(e) {
      if (!dragging) return
      const dx = e.clientX - startX
      const dy = e.clientY - startY
      widget.style.width = (startW + dx) + 'px'
      widget.style.height = (startH + dy) + 'px'
    })

    handle.addEventListener('pointerup', function(e) {
      dragging = false
      try { handle.releasePointerCapture(e.pointerId) } catch(err) {}
    })
  })()
</script>
</body>
</html>
`

test.describe("resize live preview — pointer-driven", () => {
  test("widget dimensions update during drag (not only at release)", async ({ page }) => {
    await page.setContent(FIXTURE_HTML)

    const widget = page.locator(
      '[data-testid="focus-builder-freeform-placed-widget-draggable"]',
    )
    const handle = page.locator(
      '[data-testid="focus-builder-resize-handle"][data-handle-position="se"]',
    )

    const preBBox = await widget.boundingBox()
    expect(preBBox).toBeTruthy()
    expect(preBBox!.width).toBe(240)
    expect(preBBox!.height).toBe(120)

    const handleBox = await handle.boundingBox()
    expect(handleBox).toBeTruthy()

    // Pointer-down on handle center.
    const downX = handleBox!.x + handleBox!.width / 2
    const downY = handleBox!.y + handleBox!.height / 2
    await page.mouse.move(downX, downY)
    await page.mouse.down()

    // First move — assert MID-DRAG growth (drag still active).
    await page.mouse.move(downX + 50, downY + 30)
    await page.waitForTimeout(50)
    const midDragBBox1 = await widget.boundingBox()
    expect(midDragBBox1!.width).toBeGreaterThan(preBBox!.width)
    expect(midDragBBox1!.height).toBeGreaterThan(preBBox!.height)

    // Second move — assert CONTINUOUS preview (more growth before
    // release). This is what distinguishes "live preview" from
    // "single commit on activate".
    await page.mouse.move(downX + 120, downY + 80)
    await page.waitForTimeout(50)
    const midDragBBox2 = await widget.boundingBox()
    expect(midDragBBox2!.width).toBeGreaterThan(midDragBBox1!.width)
    expect(midDragBBox2!.height).toBeGreaterThan(midDragBBox1!.height)

    // Release.
    await page.mouse.up()
    await page.waitForTimeout(50)

    // Final dimensions persist at the last-tick value (idempotent
    // with handleDragEnd's redundant final commit in production).
    const finalBBox = await widget.boundingBox()
    expect(Math.abs(finalBBox!.width - midDragBBox2!.width)).toBeLessThan(2)
    expect(Math.abs(finalBBox!.height - midDragBBox2!.height)).toBeLessThan(2)
  })
})

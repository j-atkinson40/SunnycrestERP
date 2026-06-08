/**
 * Workflow editor canvas — negative-coordinate support (staging gates).
 *
 * Root cause (see /tmp/workflow_canvas_leftside_bug.md → the fix commit): the
 * canvas was origin-anchored to (0,0)..(maxX,maxY) and ignored negative content
 * coords, so any node at x<0 / y<0 rendered off-surface, its edges clipped at
 * the SVG x<0 boundary, and pan was dead over that region. funeral_cascade
 * seeds the burial path at x=-300, which surfaced it. The fix gives the canvas
 * a content-origin offset (`bbox.originX/originY = min(0, minX/minY)`) applied
 * at the node/container left/top, the edge-SVG viewBox, the pan-clamp, and the
 * drag-to-connect hit-test — a no-op for non-negative canvases (byte-identical).
 *
 * The DETERMINISTIC gate for this fix is the runnable unit + jsdom suite:
 *   - canvas-layout.test.ts — bbox yields origin (0,0) for non-negative content
 *     (byte-identical guard) and min(0,minX/minY) for negative; the drag-clamp
 *     lower bound.
 *   - GraphCanvas.test.tsx — a negative-x node renders ON-SURFACE (left shifted
 *     by -origin, not off at left<0); the edge-SVG viewBox starts at the
 *     negative origin so the leftward edge is in-viewport (not clipped) + the
 *     edge renders; a non-negative canvas is byte-identical (viewBox "0 0 …").
 *
 * The two scenarios below are the live-browser corroboration (pan-drag +
 * rendered-geometry) that jsdom can't provide. They are `test.skip` skeletons
 * — matching the established codebase convention for deep workflow/Focus canvas
 * Playwright that depends on the platform-admin auth harness (cf.
 * focus-builder-freeform.spec.ts's skipped pointer-drag scenarios + its
 * "Future: loginAsPlatformAdmin / openEditor…" note). Un-skip once that harness
 * lands; the assertions are structured against the shipped fix.
 */
import { test, expect, Page } from "@playwright/test"

// The workflow editor loads funeral_cascade (funeral_home vertical_default) via
// the scope/vertical/workflow_type selectors; the page reads workflow_type from
// the query string. Adjust to the harness's canonical studio path when un-skipped.
const FUNERAL_CASCADE_URL =
  "/bridgeable-admin/visual-editor/workflows" +
  "?scope=vertical_default&vertical=funeral_home&workflow_type=funeral_cascade"

// The burial-branch edge (decision → burial path) lives at negative x in the
// seed (burial path x=-300); pre-fix it clipped/did-not-render.
const BURIAL_EDGE_TESTID = "edge-e_branch_burial"

async function gotoFuneralCascadeCanvas(page: Page): Promise<void> {
  await page.goto(FUNERAL_CASCADE_URL)
  await page.waitForSelector('[data-testid="graph-canvas-surface"]', {
    timeout: 15_000,
  })
}

test.describe("Workflow canvas — negative-coordinate support (funeral_cascade burial path)", () => {
  // Scenario 1 — the leftward burial-branch edge renders a non-empty, in-viewport
  // path (pre-fix: clipped at the SVG x<0 boundary → absent/empty).
  test.skip("the burial-branch edge renders a non-empty path inside the SVG viewBox", async ({
    page,
  }) => {
    await gotoFuneralCascadeCanvas(page)
    const edgePath = page
      .locator(`[data-testid="${BURIAL_EDGE_TESTID}"] path`)
      .first()
    await expect(edgePath).toBeVisible()
    const d = await edgePath.getAttribute("d")
    expect(d && d.length).toBeTruthy()
    // The path is in-viewport: the SVG viewBox now starts at the negative
    // origin, so the edge's negative-x geometry is within it (not clipped).
    const viewBox = await page
      .locator('[data-testid="graph-canvas-edges"]')
      .getAttribute("viewBox")
    expect(viewBox).toBeTruthy()
    const [vbMinX] = (viewBox as string).split(" ").map(Number)
    // funeral_cascade's leftmost content is x=-300 → viewBox minX <= -300.
    expect(vbMinX).toBeLessThanOrEqual(-300)
  })

  // Scenario 2 — pan works across the FULL canvas width, including the left
  // (negative-x) region (pre-fix: dead there — that region fell outside the
  // origin-anchored surface div, so pointer-downs never engaged pan).
  test.skip("pan works in the left (negative-x) region, not just the right", async ({
    page,
  }) => {
    await gotoFuneralCascadeCanvas(page)
    const surface = page.locator('[data-testid="graph-canvas-surface"]')
    const box = await surface.boundingBox()
    expect(box).toBeTruthy()
    const panXBefore = Number(await surface.getAttribute("data-pan-x"))
    // Drag from a point in the LEFT third of the viewport (over the burial
    // subtree's region) — a background pan.
    const startX = box!.x + box!.width * 0.15
    const startY = box!.y + box!.height * 0.5
    await page.mouse.move(startX, startY)
    await page.mouse.down()
    await page.mouse.move(startX + 120, startY, { steps: 8 })
    await page.mouse.up()
    await expect
      .poll(async () => Number(await surface.getAttribute("data-pan-x")), {
        timeout: 5_000,
      })
      .not.toBe(panXBefore)
  })
})

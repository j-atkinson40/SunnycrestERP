/**
 * canvas-pan-zoom tests — Phase B integration-phase (pan + zoom).
 *
 * Pure-function coverage for the view-transform math. The zoom-to-cursor
 * invariant + boundary-clamp correctness live here (unit-testable without
 * DOM per the canvas-layout / simulate-trace Q-40 precedent); the
 * GraphCanvas integration test asserts the resulting inline transform
 * string + gesture wiring.
 */
import { describe, expect, it } from "vitest"

import {
  ZOOM_MIN,
  ZOOM_MAX,
  PAN_DRAG_THRESHOLD,
  DEFAULT_VIEW,
  clampZoom,
  computeZoomToCursor,
  clampPan,
  formatZoomPercent,
} from "./canvas-pan-zoom"


describe("canvas-pan-zoom — constants", () => {
  it("locks the operator-confirmed zoom range + 3px threshold", () => {
    expect(ZOOM_MIN).toBe(0.25)
    expect(ZOOM_MAX).toBe(2.0)
    expect(PAN_DRAG_THRESHOLD).toBe(3)
    expect(DEFAULT_VIEW).toEqual({ panX: 0, panY: 0, zoom: 1 })
  })
})


describe("canvas-pan-zoom — clampZoom", () => {
  it("passes through an in-range zoom", () => {
    expect(clampZoom(1)).toBe(1)
    expect(clampZoom(0.5)).toBe(0.5)
  })
  it("clamps below ZOOM_MIN and above ZOOM_MAX", () => {
    expect(clampZoom(0.1)).toBe(ZOOM_MIN)
    expect(clampZoom(5)).toBe(ZOOM_MAX)
  })
})


describe("canvas-pan-zoom — computeZoomToCursor", () => {
  it("zoom-in (wheel up, negative deltaY) increases zoom", () => {
    const next = computeZoomToCursor(DEFAULT_VIEW, 100, 100, -100)
    expect(next.zoom).toBeGreaterThan(1)
    expect(next.zoom).toBeLessThanOrEqual(ZOOM_MAX)
  })

  it("zoom-out (wheel down, positive deltaY) decreases zoom", () => {
    const next = computeZoomToCursor(DEFAULT_VIEW, 100, 100, 100)
    expect(next.zoom).toBeLessThan(1)
    expect(next.zoom).toBeGreaterThanOrEqual(ZOOM_MIN)
  })

  it("INVARIANT: the world point under the cursor maps to the same screen point after zoom", () => {
    // world = (cursorScreen - pan) / zoom; after zoom the same world point
    // must still resolve to the same screen coordinate under the cursor.
    const view = { panX: 50, panY: 30, zoom: 1 }
    const cursorX = 200
    const cursorY = 140
    const next = computeZoomToCursor(view, cursorX, cursorY, -120)

    const worldX = (cursorX - view.panX) / view.zoom
    const worldY = (cursorY - view.panY) / view.zoom
    const screenXAfter = next.panX + worldX * next.zoom
    const screenYAfter = next.panY + worldY * next.zoom

    expect(screenXAfter).toBeCloseTo(cursorX, 6)
    expect(screenYAfter).toBeCloseTo(cursorY, 6)
  })

  it("at ZOOM_MAX a further zoom-in is a no-op (zoom clamped, pan unchanged)", () => {
    const view = { panX: 12, panY: 34, zoom: ZOOM_MAX }
    const next = computeZoomToCursor(view, 300, 200, -500)
    expect(next.zoom).toBe(ZOOM_MAX)
    expect(next.panX).toBe(12)
    expect(next.panY).toBe(34)
  })

  it("at ZOOM_MIN a further zoom-out is a no-op (zoom clamped, pan unchanged)", () => {
    const view = { panX: 12, panY: 34, zoom: ZOOM_MIN }
    const next = computeZoomToCursor(view, 300, 200, 500)
    expect(next.zoom).toBe(ZOOM_MIN)
    expect(next.panX).toBe(12)
    expect(next.panY).toBe(34)
  })
})


describe("canvas-pan-zoom — clampPan (zoom-aware boundary)", () => {
  const content = { minX: 0, minY: 0, maxX: 400, maxY: 300 }
  const viewport = { width: 800, height: 600 }
  const MARGIN = 120

  it("leaves an in-range pan unchanged", () => {
    const out = clampPan({ panX: 50, panY: 40, zoom: 1 }, content, viewport, MARGIN)
    expect(out.panX).toBe(50)
    expect(out.panY).toBe(40)
  })

  it("clamps a far-positive pan so the content's left edge can't pass viewport − margin", () => {
    // hiX = W - margin - minX*z = 800 - 120 - 0 = 680
    const out = clampPan({ panX: 10000, panY: 0, zoom: 1 }, content, viewport, MARGIN)
    expect(out.panX).toBe(680)
  })

  it("clamps a far-negative pan so the content's right edge stays ≥ margin", () => {
    // loX = margin - maxX*z = 120 - 400 = -280
    const out = clampPan({ panX: -10000, panY: 0, zoom: 1 }, content, viewport, MARGIN)
    expect(out.panX).toBe(-280)
  })

  it("is zoom-aware — the clamp range shifts as zoom changes", () => {
    // At zoom 2: loX = 120 - 400*2 = -680 (was -280 at zoom 1).
    const out = clampPan({ panX: -10000, panY: 0, zoom: 2 }, content, viewport, MARGIN)
    expect(out.panX).toBe(-680)
  })

  it("pins to the lower bound when content is smaller than the margin budget", () => {
    const tiny = { minX: 0, minY: 0, maxX: 10, maxY: 10 }
    const out = clampPan({ panX: 0, panY: 0, zoom: 1 }, tiny, viewport, MARGIN)
    // loX = 120 - 10 = 110; hiX = 800 - 120 - 0 = 680 → 0 clamps up to 110.
    expect(out.panX).toBe(110)
  })
})


describe("canvas-pan-zoom — formatZoomPercent", () => {
  it("renders zoom as an integer percent", () => {
    expect(formatZoomPercent(1)).toBe("100%")
    expect(formatZoomPercent(0.25)).toBe("25%")
    expect(formatZoomPercent(2)).toBe("200%")
    expect(formatZoomPercent(1.1618)).toBe("116%")
  })
})

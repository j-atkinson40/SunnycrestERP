/**
 * Canvas geometry — pure-function unit tests.
 */

import { describe, expect, it } from "vitest"

import {
  GRID_STEP,
  clampToCanvas,
  computeCoreRect,
  enforceMinSize,
  findOpenZone,
  rectsOverlap,
  snapTo8px,
  type Rect,
} from "./geometry"


describe("snapTo8px", () => {
  it("snaps to nearest 8px multiple (round half to even is acceptable)", () => {
    expect(snapTo8px(0)).toBe(0)
    expect(snapTo8px(3)).toBe(0)
    expect(snapTo8px(5)).toBe(8)
    expect(snapTo8px(8)).toBe(8)
    expect(snapTo8px(11)).toBe(8)
    expect(snapTo8px(12)).toBe(16)
    expect(snapTo8px(16)).toBe(16)
  })

  it("handles fractional inputs from cursor deltas", () => {
    expect(snapTo8px(7.3)).toBe(8)
    expect(snapTo8px(7.99)).toBe(8)
    expect(snapTo8px(100.5)).toBe(104)
  })

  it("snaps negative inputs consistently (future-proof)", () => {
    // JS Math.round uses round-half-away-from-zero for positive
    // values but round-half-to-positive-infinity for negatives —
    // so snapTo8px(-3) = round(-0.375) * 8 = 0, while
    // snapTo8px(-5) = round(-0.625) * 8 = -8. We assert the observed
    // behavior to pin it against future Math.round changes.
    expect(snapTo8px(-3)).toBe(0)
    expect(snapTo8px(-5)).toBe(-8)
    expect(snapTo8px(-8)).toBe(-8)
    expect(snapTo8px(-16)).toBe(-16)
  })

  it("GRID_STEP constant is 8", () => {
    expect(GRID_STEP).toBe(8)
  })
})


describe("rectsOverlap", () => {
  const a = { x: 0, y: 0, width: 100, height: 100 }

  it("overlapping rects return true", () => {
    expect(
      rectsOverlap(a, { x: 50, y: 50, width: 100, height: 100 }),
    ).toBe(true)
  })

  it("edge-touching is NOT overlap (exclusive boundaries)", () => {
    expect(
      rectsOverlap(a, { x: 100, y: 0, width: 50, height: 50 }),
    ).toBe(false)
    expect(
      rectsOverlap(a, { x: 0, y: 100, width: 50, height: 50 }),
    ).toBe(false)
  })

  it("disjoint rects return false", () => {
    expect(
      rectsOverlap(a, { x: 200, y: 200, width: 50, height: 50 }),
    ).toBe(false)
  })

  it("contained rect returns true", () => {
    expect(
      rectsOverlap(a, { x: 25, y: 25, width: 50, height: 50 }),
    ).toBe(true)
  })
})


describe("clampToCanvas", () => {
  it("leaves in-bounds widgets unchanged", () => {
    const w = { x: 32, y: 32, width: 200, height: 100 }
    expect(clampToCanvas(w, 1000, 800)).toEqual(w)
  })

  it("clamps widget past the right edge", () => {
    const w = { x: 900, y: 32, width: 200, height: 100 }
    expect(clampToCanvas(w, 1000, 800)).toEqual({
      x: 800,
      y: 32,
      width: 200,
      height: 100,
    })
  })

  it("clamps widget past the bottom edge", () => {
    const w = { x: 32, y: 750, width: 200, height: 100 }
    expect(clampToCanvas(w, 1000, 800)).toEqual({
      x: 32,
      y: 700,
      width: 200,
      height: 100,
    })
  })

  it("clamps widget past the top/left edge to 0,0", () => {
    const w = { x: -50, y: -50, width: 200, height: 100 }
    expect(clampToCanvas(w, 1000, 800)).toEqual({
      x: 0,
      y: 0,
      width: 200,
      height: 100,
    })
  })
})


describe("enforceMinSize", () => {
  it("widens undersized widget to min width", () => {
    const w = { x: 0, y: 0, width: 100, height: 200 }
    expect(enforceMinSize(w, 200, 100)).toEqual({
      x: 0,
      y: 0,
      width: 200,
      height: 200,
    })
  })

  it("leaves oversized widgets unchanged", () => {
    const w = { x: 0, y: 0, width: 400, height: 300 }
    expect(enforceMinSize(w, 200, 100)).toEqual(w)
  })
})


describe("computeCoreRect", () => {
  it("caps core at max dimensions on a 1920x1080 viewport", () => {
    const r = computeCoreRect(1920, 1080)
    // 1920*0.9 = 1728 > 1400, so width is capped at 1400.
    // 1080*0.85 = 918 > 900, so height is capped at 900.
    expect(r.width).toBe(1400)
    expect(r.height).toBe(900)
    expect(r.x).toBe((1920 - 1400) / 2)
    expect(r.y).toBe((1080 - 900) / 2)
  })

  it("scales core with the viewport when smaller than max", () => {
    const r = computeCoreRect(1000, 600)
    expect(r.width).toBeCloseTo(900, 0) // 1000 * 0.9
    expect(r.height).toBeCloseTo(510, 0) // 600 * 0.85
  })
})


describe("findOpenZone", () => {
  // Test viewport: 2400x1400 with core capped at 1400x900 centered.
  // Top rail: 250px tall. Left/right rails: 500px wide. Bottom: 250.
  // Generous dimensions so widgets of the sizes below have room.
  const big = {
    canvasWidth: 2400,
    canvasHeight: 1400,
    coreRect: computeCoreRect(2400, 1400),
    existing: [] as Rect[],
  }

  it("places a widget in the top rail first (preference order)", () => {
    const pos = findOpenZone({
      ...big,
      widgetWidth: 320,
      widgetHeight: 80,
    })
    expect(pos).not.toBeNull()
    // Top rail: y is above the core's top edge.
    expect(pos!.y + pos!.height).toBeLessThanOrEqual(big.coreRect.y)
  })

  it("falls to left rail when widget doesn't fit the top rail", () => {
    // 400px-tall widget can't fit in the 250-px top rail.
    const pos = findOpenZone({
      ...big,
      widgetWidth: 200,
      widgetHeight: 400,
    })
    expect(pos).not.toBeNull()
    // Should land in the left rail (x is left of the core).
    expect(pos!.x + pos!.width).toBeLessThanOrEqual(big.coreRect.x)
  })

  it("returns null when no zone fits the widget", () => {
    const pos = findOpenZone({
      ...big,
      widgetWidth: 9999, // wider than the whole canvas
      widgetHeight: 80,
    })
    expect(pos).toBeNull()
  })

  it("avoids overlapping existing widgets", () => {
    // Place an existing widget in the natural top-rail first slot.
    const existing: Rect[] = [{ x: 8, y: 8, width: 320, height: 80 }]
    const pos = findOpenZone({
      ...big,
      existing,
      widgetWidth: 320,
      widgetHeight: 80,
    })
    expect(pos).not.toBeNull()
    // The returned position should not overlap the existing rect.
    expect(
      rectsOverlap(
        { x: pos!.x, y: pos!.y, width: pos!.width, height: pos!.height },
        existing[0],
      ),
    ).toBe(false)
  })

  it("returned positions are 8px-snapped", () => {
    const pos = findOpenZone({
      ...big,
      widgetWidth: 320,
      widgetHeight: 80,
    })
    expect(pos).not.toBeNull()
    expect(pos!.x % GRID_STEP).toBe(0)
    expect(pos!.y % GRID_STEP).toBe(0)
  })
})

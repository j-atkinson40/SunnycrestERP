/**
 * Canvas geometry — pure-function unit tests. Phase A Session 3.5.
 */

import { describe, expect, it } from "vitest"

import type { WidgetAnchor } from "@/contexts/focus-registry"

import {
  GRID_STEP,
  applyResizeDelta,
  clampPositionOffsets,
  clampRectToCanvas,
  computeCoreRect,
  computeOffsetsForAnchor,
  determineAnchorFromDrop,
  enforceMinRect,
  findOpenZone,
  rectsOverlap,
  resolvePosition,
  snapTo8px,
  type Rect,
} from "./geometry"


describe("snapTo8px", () => {
  it("rounds to nearest 8px multiple", () => {
    expect(snapTo8px(0)).toBe(0)
    expect(snapTo8px(3)).toBe(0)
    expect(snapTo8px(5)).toBe(8)
    expect(snapTo8px(8)).toBe(8)
    expect(snapTo8px(12)).toBe(16)
    expect(snapTo8px(7.3)).toBe(8)
    expect(snapTo8px(100.5)).toBe(104)
  })

  it("normalizes negative-zero to +0", () => {
    // Math.round(-0.375) * 8 = -0 pre-normalization; we add +0 so
    // Object.is(result, 0) holds.
    expect(Object.is(snapTo8px(-3), 0)).toBe(true)
    expect(snapTo8px(-5)).toBe(-8)
    expect(snapTo8px(-8)).toBe(-8)
  })

  it("GRID_STEP constant is 8", () => {
    expect(GRID_STEP).toBe(8)
  })
})


describe("rectsOverlap", () => {
  const a: Rect = { x: 0, y: 0, width: 100, height: 100 }

  it("overlapping rects return true", () => {
    expect(rectsOverlap(a, { x: 50, y: 50, width: 100, height: 100 })).toBe(true)
  })
  it("edge-touching is NOT overlap", () => {
    expect(rectsOverlap(a, { x: 100, y: 0, width: 50, height: 50 })).toBe(false)
  })
  it("disjoint rects return false", () => {
    expect(rectsOverlap(a, { x: 200, y: 200, width: 50, height: 50 })).toBe(false)
  })
  it("contained rect returns true", () => {
    expect(rectsOverlap(a, { x: 25, y: 25, width: 50, height: 50 })).toBe(true)
  })
})


describe("resolvePosition — anchor → absolute rect", () => {
  const VW = 1920
  const VH = 1080
  const size = { width: 320, height: 240 }

  const cases: Array<{
    anchor: WidgetAnchor
    offsetX: number
    offsetY: number
    expected: Rect
  }> = [
    {
      anchor: "top-left",
      offsetX: 32,
      offsetY: 64,
      expected: { x: 32, y: 64, ...size },
    },
    {
      anchor: "top-center",
      offsetX: 0,
      offsetY: 16,
      // center: (1920-320)/2 + 0 = 800; y = 16
      expected: { x: 800, y: 16, ...size },
    },
    {
      anchor: "top-right",
      offsetX: 32,
      offsetY: 64,
      // x = 1920 - 320 - 32 = 1568
      expected: { x: 1568, y: 64, ...size },
    },
    {
      anchor: "left-rail",
      offsetX: 16,
      offsetY: 300,
      expected: { x: 16, y: 300, ...size },
    },
    {
      anchor: "right-rail",
      offsetX: 16,
      offsetY: 300,
      // x = 1920 - 320 - 16 = 1584
      expected: { x: 1584, y: 300, ...size },
    },
    {
      anchor: "bottom-left",
      offsetX: 32,
      offsetY: 48,
      // y = 1080 - 240 - 48 = 792
      expected: { x: 32, y: 792, ...size },
    },
    {
      anchor: "bottom-center",
      offsetX: 0,
      offsetY: 48,
      // x center = 800, y = 792
      expected: { x: 800, y: 792, ...size },
    },
    {
      anchor: "bottom-right",
      offsetX: 32,
      offsetY: 48,
      // x = 1568, y = 792
      expected: { x: 1568, y: 792, ...size },
    },
  ]

  for (const c of cases) {
    it(`resolves ${c.anchor} at (${c.offsetX}, ${c.offsetY})`, () => {
      const rect = resolvePosition(
        { anchor: c.anchor, offsetX: c.offsetX, offsetY: c.offsetY, ...size },
        VW,
        VH,
      )
      expect(rect).toEqual(c.expected)
    })
  }

  it("viewport resize changes absolute position (right-rail example)", () => {
    const pos = {
      anchor: "right-rail" as WidgetAnchor,
      offsetX: 16,
      offsetY: 300,
      width: 320,
      height: 240,
    }
    // Wide viewport: widget lives at x=1584
    expect(resolvePosition(pos, 1920, 1080).x).toBe(1584)
    // Narrower viewport: widget stays anchored to right edge with
    // offsetX=16, so x becomes 1200 - 320 - 16 = 864
    expect(resolvePosition(pos, 1200, 800).x).toBe(864)
  })
})


describe("computeOffsetsForAnchor — inverse-of-resolve", () => {
  const VW = 1920
  const VH = 1080
  const size = { width: 320, height: 240 }

  it("resolve ∘ computeOffsets is identity for every anchor", () => {
    const anchors: WidgetAnchor[] = [
      "top-left",
      "top-center",
      "top-right",
      "left-rail",
      "right-rail",
      "bottom-left",
      "bottom-center",
      "bottom-right",
    ]
    for (const anchor of anchors) {
      const original = {
        anchor,
        offsetX: 64,
        offsetY: 128,
        ...size,
      }
      const rect = resolvePosition(original, VW, VH)
      const recomputed = computeOffsetsForAnchor(anchor, rect, VW, VH)
      expect(recomputed.offsetX).toBeCloseTo(64)
      expect(recomputed.offsetY).toBeCloseTo(128)
    }
  })
})


describe("determineAnchorFromDrop", () => {
  const VW = 1920
  const VH = 1080

  it("near left edge → left-rail", () => {
    expect(determineAnchorFromDrop(50, 500, VW, VH)).toBe("left-rail")
  })
  it("near right edge → right-rail", () => {
    expect(determineAnchorFromDrop(1870, 500, VW, VH)).toBe("right-rail")
  })
  it("top-left third → top-left", () => {
    expect(determineAnchorFromDrop(300, 100, VW, VH)).toBe("top-left")
  })
  it("top-center → top-center", () => {
    expect(determineAnchorFromDrop(960, 100, VW, VH)).toBe("top-center")
  })
  it("top-right third → top-right", () => {
    expect(determineAnchorFromDrop(1500, 100, VW, VH)).toBe("top-right")
  })
  it("bottom-left third → bottom-left", () => {
    expect(determineAnchorFromDrop(300, 900, VW, VH)).toBe("bottom-left")
  })
  it("bottom-center → bottom-center", () => {
    expect(determineAnchorFromDrop(960, 900, VW, VH)).toBe("bottom-center")
  })
  it("bottom-right third → bottom-right", () => {
    expect(determineAnchorFromDrop(1500, 900, VW, VH)).toBe("bottom-right")
  })
  it("rail threshold excludes the top/bottom half buckets", () => {
    // Even a y near top, if x is within 100px of the left edge,
    // rail wins.
    expect(determineAnchorFromDrop(50, 50, VW, VH)).toBe("left-rail")
  })
})


describe("clampPositionOffsets", () => {
  const VW = 1200
  const VH = 800

  it("clamps negative offsets to zero", () => {
    // A position with negative offsetY (e.g. result of a drag that
    // rebased to an anchor with a smaller effective space) → 0.
    const pos = {
      anchor: "top-left" as WidgetAnchor,
      offsetX: -20,
      offsetY: -30,
      width: 200,
      height: 100,
    }
    const clamped = clampPositionOffsets(pos, VW, VH)
    expect(clamped.offsetX).toBeGreaterThanOrEqual(0)
    expect(clamped.offsetY).toBeGreaterThanOrEqual(0)
  })

  it("pulls widget back into viewport when offset pushes it off-screen", () => {
    // top-right with huge offsetX pushes the widget off the LEFT side
    // of the viewport. Clamp should pull it back in so resolve keeps
    // x >= 0.
    const pos = {
      anchor: "top-right" as WidgetAnchor,
      offsetX: 1500,
      offsetY: 32,
      width: 200,
      height: 100,
    }
    const clamped = clampPositionOffsets(pos, VW, VH)
    const resolved = resolvePosition(clamped, VW, VH)
    expect(resolved.x).toBeGreaterThanOrEqual(0)
    expect(resolved.x + resolved.width).toBeLessThanOrEqual(VW)
  })
})


describe("applyResizeDelta — zone math", () => {
  const start: Rect = { x: 100, y: 100, width: 300, height: 200 }

  it("se corner grows width + height", () => {
    expect(applyResizeDelta("se", start, 40, 20)).toEqual({
      x: 100,
      y: 100,
      width: 340,
      height: 220,
    })
  })
  it("nw corner moves x/y + inverts width/height growth", () => {
    expect(applyResizeDelta("nw", start, -40, -20)).toEqual({
      x: 60,
      y: 80,
      width: 340,
      height: 220,
    })
  })
  it("e edge grows width only", () => {
    expect(applyResizeDelta("e", start, 40, 999)).toEqual({
      x: 100,
      y: 100,
      width: 340,
      height: 200,
    })
  })
  it("s edge grows height only", () => {
    expect(applyResizeDelta("s", start, 999, 20)).toEqual({
      x: 100,
      y: 100,
      width: 300,
      height: 220,
    })
  })
  it("w edge shifts x + grows width inversely", () => {
    expect(applyResizeDelta("w", start, -40, 999)).toEqual({
      x: 60,
      y: 100,
      width: 340,
      height: 200,
    })
  })
  it("n edge shifts y + grows height inversely", () => {
    expect(applyResizeDelta("n", start, 999, -20)).toEqual({
      x: 100,
      y: 80,
      width: 300,
      height: 220,
    })
  })
})


describe("clampRectToCanvas + enforceMinRect", () => {
  it("clampRectToCanvas pulls rect within bounds", () => {
    expect(
      clampRectToCanvas({ x: 900, y: 32, width: 200, height: 100 }, 1000, 800),
    ).toEqual({ x: 800, y: 32, width: 200, height: 100 })
  })
  it("enforceMinRect widens undersized rects", () => {
    expect(
      enforceMinRect({ x: 0, y: 0, width: 100, height: 50 }, 200, 100),
    ).toEqual({ x: 0, y: 0, width: 200, height: 100 })
  })
})


describe("computeCoreRect", () => {
  it("caps at 1400x900 on a 1920x1080 viewport", () => {
    const r = computeCoreRect(1920, 1080)
    expect(r.width).toBe(1400)
    expect(r.height).toBe(900)
    expect(r.x).toBe((1920 - 1400) / 2)
    expect(r.y).toBe((1080 - 900) / 2)
  })
})


describe("findOpenZone — anchor-aware smart positioning", () => {
  const big = {
    canvasWidth: 2400,
    canvasHeight: 1400,
    coreRect: computeCoreRect(2400, 1400),
    existing: [] as Rect[],
  }

  it("returns a valid WidgetPosition when space is available", () => {
    const pos = findOpenZone({
      ...big,
      widgetWidth: 320,
      widgetHeight: 240,
    })
    expect(pos).not.toBeNull()
    expect(pos!.width).toBe(320)
    expect(pos!.height).toBe(240)
    // Returned position's resolved rect does NOT overlap the core.
    const resolved = resolvePosition(pos!, big.canvasWidth, big.canvasHeight)
    expect(rectsOverlap(resolved, big.coreRect)).toBe(false)
  })

  it("preferred anchor is top-left (first in preference order)", () => {
    const pos = findOpenZone({
      ...big,
      widgetWidth: 200,
      widgetHeight: 100,
    })
    expect(pos!.anchor).toBe("top-left")
  })

  it("avoids overlapping existing widgets", () => {
    // Seed a widget where the natural top-left slot would land.
    const seedRect = resolvePosition(
      {
        anchor: "top-left",
        offsetX: GRID_STEP,
        offsetY: GRID_STEP,
        width: 200,
        height: 100,
      },
      big.canvasWidth,
      big.canvasHeight,
    )
    const pos = findOpenZone({
      ...big,
      existing: [seedRect],
      widgetWidth: 200,
      widgetHeight: 100,
    })
    expect(pos).not.toBeNull()
    const resolved = resolvePosition(pos!, big.canvasWidth, big.canvasHeight)
    expect(rectsOverlap(resolved, seedRect)).toBe(false)
  })

  it("returns null when widget too big for any zone", () => {
    const pos = findOpenZone({
      ...big,
      widgetWidth: 9999,
      widgetHeight: 80,
    })
    expect(pos).toBeNull()
  })

  it("returned offsets are 8px-snapped", () => {
    const pos = findOpenZone({
      ...big,
      widgetWidth: 320,
      widgetHeight: 240,
    })
    expect(pos!.offsetX % GRID_STEP).toBe(0)
    expect(pos!.offsetY % GRID_STEP).toBe(0)
  })
})

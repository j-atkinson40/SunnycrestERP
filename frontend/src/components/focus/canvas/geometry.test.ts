/**
 * Canvas geometry — pure-function unit tests. Phase A Session 3.5.
 */

import { describe, expect, it } from "vitest"

import type { WidgetAnchor, WidgetState } from "@/contexts/focus-registry"

import {
  GRID_STEP,
  applyResizeDelta,
  clampPositionOffsets,
  clampRectToCanvas,
  computeCoreRect,
  computeOffsetsForAnchor,
  determineAnchorFromDrop,
  determineTier,
  enforceMinRect,
  findOpenZone,
  rectsOverlap,
  resolvePosition,
  snapTo8px,
  stackFitsAlongsideCore,
  widgetsFitInCanvas,
  type Rect,
} from "./geometry"


/** Helper to build a WidgetState for fit-check tests. Session 3.8.1
 *  made the fit check offset-aware, so offsets default to 0 here but
 *  tests that need non-zero offsets can pass them explicitly. */
function widget(
  anchor: WidgetAnchor,
  width: number,
  height: number,
  offsetX: number = 0,
  offsetY: number = 0,
): WidgetState {
  return {
    position: { anchor, offsetX, offsetY, width, height },
  }
}


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


describe("computeCoreRect — Session 3.7 tier-aware", () => {
  it("canvas tier caps at CORE_MAX on wide viewport", () => {
    // Aesthetic Arc Session 1 Commit C — CANVAS_RESERVED_MARGIN
    // 100 → 220. New arithmetic at 1920×1080:
    //   width  = min(1400, max(600, 1920-440)) = min(1400, 1480) = 1400 (capped)
    //   height = min(900, max(400, 1080-440))  = min(900, 640)  = 640
    // Width still hits CORE_MAX cap on wide viewports — that's
    // unchanged. Height now constrained by MARGIN (was constrained
    // by CORE_MAX_HEIGHT pre-Session-1: 1080-200=880 < 900). Top
    // widgets gain vertical band (reservedTop = (1080-640)/2 = 220
    // post-Session-1, was 100 pre-Session-1).
    const r = computeCoreRect("canvas", 1920, 1080)
    expect(r.width).toBe(1400)
    expect(r.height).toBe(640)
  })

  it("canvas tier floors at CORE_MIN on narrow viewport", () => {
    // Aesthetic Arc Session 1 Commit C — CANVAS_RESERVED_MARGIN
    // bumped 100 → 220. New arithmetic at 700×700:
    //   width  = min(1400, max(600, 700-440)) = max(600, 260) = 600
    //   height = min(900, max(400, 700-440))  = max(400, 260) = 400
    // Both clamp to CORE_MIN; pre-Session-1 height was 500 (when
    // 700-200=500 > 400 floor → no floor needed). Post-Session-1 the
    // height ALSO hits the CORE_MIN_HEIGHT floor since reservedTop
    // grew. Same behavior shape (clamp at CORE_MIN); different
    // arithmetic. Real-world impact at this viewport: the canvas
    // tier still wouldn't render here (stack tier kicks in around
    // vw=928 via `stackFitsAlongsideCore`); this test exercises the
    // computeCoreRect formula directly.
    const r = computeCoreRect("canvas", 700, 700)
    expect(r.width).toBe(600)
    expect(r.height).toBe(400)
  })

  it("stack tier reserves right-rail", () => {
    // vw=900, rail=280, gap=16, left margin=16 → core width = 900-296-16 = 588
    // Floors at CORE_MIN_WIDTH=600 (588 < 600 triggers floor).
    const r = computeCoreRect("stack", 900, 800)
    expect(r.width).toBeGreaterThanOrEqual(600)
    expect(r.x).toBe(16)
    // Core height = vh - 32 = 768; under 900 cap.
    expect(r.height).toBe(768)
  })

  it("stack tier caps at CORE_MAX on ultra-wide viewport (Session 3.8)", () => {
    // Session 3.8 added CORE_MAX caps to the stack formula so core
    // doesn't grow unbounded at ultra-wide viewports. At 3840×2160:
    //   width = min(1400, max(600, 3840-312-16)) = min(1400, 3512) = 1400
    //   height = min(900, max(400, 2160-32)) = min(900, 2128) = 900
    const r = computeCoreRect("stack", 3840, 2160)
    expect(r.width).toBe(1400)
    expect(r.height).toBe(900)
    // Centered vertically.
    expect(r.y).toBe((2160 - 900) / 2)
  })

  it("icon tier fills viewport minus small padding", () => {
    const r = computeCoreRect("icon", 390, 844)
    expect(r.width).toBe(390 - 16)
    expect(r.height).toBe(844 - 16)
    expect(r.x).toBe(8)
    expect(r.y).toBe(8)
  })
})


describe("widgetsFitInCanvas — Session 3.8.1 anchor-aware fit logic", () => {
  it("empty widget list fits vacuously", () => {
    expect(widgetsFitInCanvas([], 1920, 1080)).toBe(true)
    expect(widgetsFitInCanvas({}, 1920, 1080)).toBe(true)
  })

  it("accepts WidgetState[] or Record<WidgetId, WidgetState>", () => {
    const w = widget("top-left", 80, 80)
    // Array form.
    expect(widgetsFitInCanvas([w], 1920, 1080)).toBe(true)
    // Record form.
    expect(widgetsFitInCanvas({ "w1": w }, 1920, 1080)).toBe(true)
  })

  it("small top-left widget fits in typical canvas reserved space", () => {
    // 1920x1080 canvas mode: coreRect width=1400, x=260. reservedLeft=260.
    // Session 3.8.1 OR logic — horizontalClears: 0+80+16=96 ≤ 260 ✓ → fits.
    expect(widgetsFitInCanvas([widget("top-left", 80, 80)], 1920, 1080)).toBe(
      true,
    )
  })

  it("seeded 320×240 top-left widget DOES NOT fit at 1920×1080", () => {
    // horizontalClears: 0+320+16=336 > reservedLeft=260 → false
    // verticalClears: 0+240+16=256 > reservedTop=100 → false
    // Neither clears → widget would overlap core → stack required.
    expect(
      widgetsFitInCanvas([widget("top-left", 320, 240)], 1920, 1080),
    ).toBe(false)
  })

  it("seeded 320×240 top-left widget DOES fit at ultra-wide 2560×1440", () => {
    // horizontalClears: 0+320+16=336 ≤ reservedLeft=580 ✓ → fits (OR logic).
    expect(
      widgetsFitInCanvas([widget("top-left", 320, 240)], 2560, 1440),
    ).toBe(true)
  })

  it("corner widget fits via horizontal band alone (Session 3.8.1 OR logic)", () => {
    // Issue 1 regression guard: at 2560×1300 reservedTop=(1300-900)/2=200.
    // A 240-tall top-left widget doesn't fit in reservedTop (256>200), but
    // it DOES fit in reservedLeft (336 ≤ 580). Pre-3.8.1 this returned
    // false (AND logic required both); post-3.8.1 returns true (OR logic —
    // widget sits in left band alongside core, doesn't overlap core).
    expect(
      widgetsFitInCanvas([widget("top-left", 320, 240)], 2560, 1300),
    ).toBe(true)
  })

  it("corner widget fits via vertical band alone (OR logic, other axis)", () => {
    // 2000×1500: reservedLeft=(2000-1400)/2=300, reservedTop=(1500-900)/2=300.
    // Widget 500×200 top-left: horizontalClears 0+500+16=516 > 300 → false.
    // verticalClears 0+200+16=216 ≤ 300 → true. Widget fits in top band.
    expect(
      widgetsFitInCanvas([widget("top-left", 500, 200)], 2000, 1500),
    ).toBe(true)
  })

  it("corner widget fails only when BOTH axes overlap core (OR logic)", () => {
    // Aesthetic Arc Session 1 Commit C — at 1920×1080 the geometry
    // shifted: width capped at 1400 (unchanged) → reservedLeft=260
    // (unchanged); height now constrained by MARGIN=220 not by
    // CORE_MAX_HEIGHT cap → height=640, reservedTop=(1080-640)/2=220
    // (was 100).
    //
    // The original test asserted "300×200 fails because both axes
    // overlap core." Post-Session-1 a 300×200 top-left clears
    // vertically (216 ≤ 220) but not horizontally (316 > 260) → OR
    // logic returns true. Bumped widget dimensions to 300×240 so
    // verticalClears 256 > 220 still fails on both axes → false.
    // Same test intent (BOTH-axes-fail returns false), updated
    // numbers reflecting the new reservedTop.
    expect(
      widgetsFitInCanvas([widget("top-left", 300, 240)], 1920, 1080),
    ).toBe(false)
  })

  it("offset pushes widget toward core — widget that fit at origin fails at inner offset", () => {
    // 2560×1440, reservedLeft=580, top-left widget 320×240:
    // At offset (0, 0): horizontalClears 336 ≤ 580 ✓ → fits.
    // At offset (300, 0): horizontalClears 300+320+16=636 > 580 → fails horiz.
    //   verticalClears: 0+240+16=256 ≤ 270 ✓ → fits vertically → still fits.
    // At offset (300, 100): horizontalClears 636 > 580 → fails.
    //   verticalClears: 100+240+16=356 > 270 → fails → doesn't fit.
    expect(
      widgetsFitInCanvas(
        [widget("top-left", 320, 240, 0, 0)],
        2560,
        1440,
      ),
    ).toBe(true)
    expect(
      widgetsFitInCanvas(
        [widget("top-left", 320, 240, 300, 0)],
        2560,
        1440,
      ),
    ).toBe(true)
    expect(
      widgetsFitInCanvas(
        [widget("top-left", 320, 240, 300, 100)],
        2560,
        1440,
      ),
    ).toBe(false)
  })

  it("right-rail widget fit check uses reservedRight (not left)", () => {
    // 1920x1080: reservedRight=260. width+16=296 > 260 → fails.
    expect(
      widgetsFitInCanvas([widget("right-rail", 280, 300)], 1920, 1080),
    ).toBe(false)
    // 2560x1440: reservedRight=580. 296 ≤ 580 ✓.
    expect(
      widgetsFitInCanvas([widget("right-rail", 280, 300)], 2560, 1440),
    ).toBe(true)
  })

  it("top-center widget only checks vertical fit (spans horizontally)", () => {
    // top-center anchor: no "left"/"right" branch, only "top" branch.
    // Aesthetic Arc Session 1 Commit C — at 1920x1080 reservedTop=
    // 220 (was 100). Large width doesn't matter here. Boundary
    // values bumped to keep "fits" + "doesn't fit" both exercised
    // against the new reservedTop.
    expect(
      widgetsFitInCanvas([widget("top-center", 800, 80)], 1920, 1080),
    ).toBe(true) // 80+16=96 ≤ 220
    expect(
      widgetsFitInCanvas([widget("top-center", 200, 240)], 1920, 1080),
    ).toBe(false) // 240+16=256 > 220
  })

  it("bottom-center widget checks reservedBottom", () => {
    // Aesthetic Arc Session 1 Commit C — at 1920x1080 reservedBottom
    // = (1080-640)/2 = 220 (was 100). Boundary values bumped.
    expect(
      widgetsFitInCanvas([widget("bottom-center", 400, 80)], 1920, 1080),
    ).toBe(true) // 96 ≤ 220
    expect(
      widgetsFitInCanvas([widget("bottom-center", 400, 240)], 1920, 1080),
    ).toBe(false) // 256 > 220
  })

  it("corner anchor — Session 3.8.1 OR logic (either dimension clears core)", () => {
    // top-right at 2560×1440: reservedRight=580, reservedTop=270.
    // horizontalClears 336 ≤ 580 → fits (vertical also clears but
    // either one alone is sufficient under OR logic).
    expect(
      widgetsFitInCanvas([widget("top-right", 320, 240)], 2560, 1440),
    ).toBe(true)
    // At 2560×900: reservedTop=(900-700)/2=100. horizontalClears
    // 336 ≤ 580 ✓. Even though vertical fails (256 > 100), OR logic
    // returns true because the widget can sit in the right band
    // without overlapping core.
    expect(
      widgetsFitInCanvas([widget("top-right", 320, 240)], 2560, 900),
    ).toBe(true)
    // At 1920×900: reservedRight=260, reservedTop=100. Both fail.
    expect(
      widgetsFitInCanvas([widget("top-right", 320, 240)], 1920, 900),
    ).toBe(false)
  })

  it("rail anchors trigger the includes('left')/includes('right') branch", () => {
    // left-rail = includes("left"), so horizontal fit checked.
    expect(
      widgetsFitInCanvas([widget("left-rail", 80, 200)], 1920, 1080),
    ).toBe(true) // 96 ≤ 260 reservedLeft
    expect(
      widgetsFitInCanvas([widget("left-rail", 320, 200)], 1920, 1080),
    ).toBe(false) // 336 > 260 reservedLeft
  })

  it("any widget failing blocks the whole set from fitting", () => {
    const good = widget("top-left", 80, 80)
    const bad = widget("top-left", 500, 400)
    expect(widgetsFitInCanvas([good, bad], 1920, 1080)).toBe(false)
    expect(widgetsFitInCanvas([good], 1920, 1080)).toBe(true)
  })

  it("seeded Kanban fixture (3 widgets) fails at wide 1920×1080", () => {
    // Fixture values from focus-registry.ts Kanban stub.
    const seeded: WidgetState[] = [
      widget("top-left", 320, 240),
      widget("right-rail", 280, 320),
      widget("bottom-right", 280, 200),
    ]
    expect(widgetsFitInCanvas(seeded, 1920, 1080)).toBe(false)
  })

  it("seeded Kanban fixture fits at 3840×2160 (4K)", () => {
    const seeded: WidgetState[] = [
      widget("top-left", 320, 240),
      widget("right-rail", 280, 320),
      widget("bottom-right", 280, 200),
    ]
    // reservedLeft=1220, reservedRight=1220, reservedTop=630, reservedBottom=630.
    // All fits comfortably.
    expect(widgetsFitInCanvas(seeded, 3840, 2160)).toBe(true)
  })

  it("buffer parameter adjusts strictness", () => {
    // With buffer=0, a 260×100 widget exactly fills reservedLeft=260 at 1920x1080 → OK.
    // With buffer=16 (default), it fails (276 > 260).
    expect(
      widgetsFitInCanvas([widget("left-rail", 260, 100)], 1920, 1080, 0),
    ).toBe(true)
    expect(
      widgetsFitInCanvas([widget("left-rail", 260, 100)], 1920, 1080),
    ).toBe(false)
  })
})


describe("determineTier — Session 3.8 continuous geometric cascade", () => {
  // Session 3.8 changed the icon-tier gate from the fixed `vw < 700`
  // pixel threshold to the geometric `stackFitsAlongsideCore` check,
  // which lands at ~928w/432h (CORE_MIN + rail + margins). Tests
  // below encode the new geometric boundaries.

  it("picks icon when stack can't fit alongside a min-sized core", () => {
    // Below the stack-fits floor: canvas & stack both impossible.
    expect(determineTier(699, 844)).toBe("icon")
    expect(determineTier(390, 844)).toBe("icon")
    expect(determineTier(300, 1200)).toBe("icon")
    // Still icon even with widgets — geometric floor wins first.
    expect(determineTier(690, 1200, [widget("top-left", 500, 500)])).toBe("icon")
    // 900×800 is below the 928-wide stack floor (Session 3.7 would
    // have chosen stack here; Session 3.8 correctly picks icon).
    expect(determineTier(900, 800)).toBe("icon")
    // Just-under the floor — still icon.
    expect(determineTier(927, 500)).toBe("icon")
    // Height floor — even at wide viewport, too-short drops to icon.
    expect(determineTier(1920, 400)).toBe("icon")
  })

  it("empty widgets above stack-fits floor → canvas (vacuously fits)", () => {
    // ≥ 928w/432h threshold where stack can fit alongside core.
    expect(determineTier(928, 432)).toBe("canvas")
    expect(determineTier(1000, 500)).toBe("canvas")
    expect(determineTier(1440, 900)).toBe("canvas")
    expect(determineTier(1920, 1080)).toBe("canvas")
  })

  it("widgets that don't fit → stack (content-aware transition)", () => {
    // Exact seeded Kanban fixture; fails canvas fit at narrow viewports.
    // Under Session 3.8.1 OR logic, the narrow-viewport cases still
    // fail because BOTH horizontal AND vertical bands are too small.
    const seeded: WidgetState[] = [
      widget("top-left", 320, 240),
      widget("right-rail", 280, 320),
      widget("bottom-right", 280, 200),
    ]
    expect(determineTier(1920, 1080, seeded)).toBe("stack")
    expect(determineTier(1440, 900, seeded)).toBe("stack")
    expect(determineTier(1100, 800, seeded)).toBe("stack")
  })

  it("widgets that fit → canvas (at ultra-wide viewport)", () => {
    const seeded: WidgetState[] = [
      widget("top-left", 320, 240),
      widget("right-rail", 280, 320),
      widget("bottom-right", 280, 200),
    ]
    expect(determineTier(3840, 2160, seeded)).toBe("canvas")
  })

  it("wide-but-short viewport with corner widgets → canvas (Session 3.8.1 fix)", () => {
    // Issue 1 regression guard. Pre-3.8.1 AND-logic fit check
    // returned "stack" at 2560×1300 because the 240-tall top-left
    // widget didn't fit reservedTop=200, even though reservedLeft=580
    // had plenty of room. Post-3.8.1 OR-logic correctly returns
    // "canvas" — the widget fits in the left band alongside core.
    const seeded: WidgetState[] = [
      widget("top-left", 320, 240),
      widget("right-rail", 280, 320),
      widget("bottom-right", 280, 200),
    ]
    expect(determineTier(2560, 1300, seeded)).toBe("canvas")
    // And at 2560×1100 (typical 27" monitor viewport minus chrome).
    expect(determineTier(2560, 1100, seeded)).toBe("canvas")
  })

  it("small widgets fit at 1920×1080 → canvas", () => {
    // Future-phase saved-view summary widgets might be ~200×150.
    const small = widget("top-left", 80, 80)
    expect(determineTier(1920, 1080, [small])).toBe("canvas")
  })

  it("single oversized widget at wide viewport → stack (stack can still fit)", () => {
    const huge = widget("top-left", 5000, 3000)
    expect(determineTier(1920, 1080, [huge])).toBe("stack")
    // Even at 4K.
    expect(determineTier(3840, 2160, [huge])).toBe("stack")
  })

  it("oversized widget below stack-fits floor → icon (geometric floor wins)", () => {
    // Stack-floor check happens before widget-fit check, so even
    // "widgets could theoretically fit canvas" falls to icon if the
    // viewport can't host a minimum stack.
    const huge = widget("top-left", 5000, 3000)
    expect(determineTier(800, 500, [huge])).toBe("icon")
    expect(determineTier(927, 432, [huge])).toBe("icon")
  })
})


describe("stackFitsAlongsideCore — Session 3.8 stack↔icon geometric gate", () => {
  it("fits exactly at the derived floor (928×432)", () => {
    // Derived: CORE_MIN_WIDTH(600) + STACK_EDGE_MARGIN(16) +
    // STACK_CORE_GAP(16) + STACK_RAIL_WIDTH(280) + STACK_EDGE_MARGIN(16)
    // = 928. Height: CORE_MIN_HEIGHT(400) + STACK_EDGE_MARGIN*2(32)
    // = 432.
    expect(stackFitsAlongsideCore(928, 432)).toBe(true)
  })

  it("rejects one-below-floor viewports", () => {
    expect(stackFitsAlongsideCore(927, 500)).toBe(false)
    expect(stackFitsAlongsideCore(1000, 431)).toBe(false)
    expect(stackFitsAlongsideCore(927, 431)).toBe(false)
  })

  it("accepts above-floor viewports", () => {
    expect(stackFitsAlongsideCore(1024, 768)).toBe(true)
    expect(stackFitsAlongsideCore(1440, 900)).toBe(true)
    expect(stackFitsAlongsideCore(1920, 1080)).toBe(true)
    expect(stackFitsAlongsideCore(3840, 2160)).toBe(true)
  })

  it("typical mobile landscape (iPhone Pro Max) fails the floor", () => {
    // 932×430 is iPhone Pro Max landscape. Width just clears, height
    // does not (< 432). Correctly drops to icon.
    expect(stackFitsAlongsideCore(932, 430)).toBe(false)
  })

  it("typical tablet (iPad mini) passes the floor", () => {
    // 1024×768 — above both threshold dims.
    expect(stackFitsAlongsideCore(1024, 768)).toBe(true)
  })
})


describe("findOpenZone — anchor-aware smart positioning", () => {
  const big = {
    canvasWidth: 2400,
    canvasHeight: 1400,
    coreRect: computeCoreRect("canvas", 2400, 1400),
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

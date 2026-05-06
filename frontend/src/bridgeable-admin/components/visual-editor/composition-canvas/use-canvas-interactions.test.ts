/**
 * Tests for the canvas interactions hook's pure helpers.
 *
 * The state-machine portion of the hook is integration-tested via
 * Playwright (real pointer events on the rendered canvas). At the
 * unit level we cover the grid-snap math + resize-delta translation
 * because they're the load-bearing pure functions that drive every
 * commit.
 */
import { describe, expect, it } from "vitest"
import { _internals } from "./use-canvas-interactions"

const { snapPxToCells, gridDeltaFromPx, resizeDeltaFromPx, DRAG_THRESHOLD_PX } =
  _internals


describe("snapPxToCells", () => {
  it("rounds to nearest cell", () => {
    expect(snapPxToCells(0, 100)).toBe(0)
    expect(snapPxToCells(40, 100)).toBe(0)
    expect(snapPxToCells(60, 100)).toBe(1)
    expect(snapPxToCells(150, 100)).toBe(2) // ties round to even via Math.round
    expect(snapPxToCells(-60, 100)).toBe(-1)
  })

  it("returns 0 when cellSize is 0 or negative (defensive)", () => {
    expect(snapPxToCells(123, 0)).toBe(0)
    expect(snapPxToCells(-123, -50)).toBe(0)
  })
})


describe("gridDeltaFromPx", () => {
  it("translates 2D px delta to 2D grid delta", () => {
    expect(gridDeltaFromPx(120, 60, 100, 50)).toEqual({ dCol: 1, dRow: 1 })
    expect(gridDeltaFromPx(-100, -50, 100, 50)).toEqual({ dCol: -1, dRow: -1 })
    expect(gridDeltaFromPx(0, 0, 100, 50)).toEqual({ dCol: 0, dRow: 0 })
  })

  it("doesn't snap below threshold", () => {
    // 40px < half cellWidth (50px) → rounds to 0
    expect(gridDeltaFromPx(40, 24, 100, 50)).toEqual({ dCol: 0, dRow: 0 })
  })
})


describe("resizeDeltaFromPx", () => {
  const cellW = 100
  const cellH = 50

  it("east handle grows column_span only", () => {
    const d = resizeDeltaFromPx("e", 200, 0, cellW, cellH)
    expect(d).toEqual({ dCol: 0, dRow: 0, dColSpan: 2, dRowSpan: 0 })
  })

  it("south handle grows row_span only", () => {
    const d = resizeDeltaFromPx("s", 0, 100, cellW, cellH)
    expect(d).toEqual({ dCol: 0, dRow: 0, dColSpan: 0, dRowSpan: 2 })
  })

  it("north handle moves row_start AND shrinks row_span", () => {
    // Pull top edge up by one row → row_start -1, row_span +1
    const d = resizeDeltaFromPx("n", 0, -50, cellW, cellH)
    expect(d).toEqual({ dCol: 0, dRow: -1, dColSpan: 0, dRowSpan: 1 })
  })

  it("west handle moves column_start AND shrinks column_span", () => {
    const d = resizeDeltaFromPx("w", -100, 0, cellW, cellH)
    expect(d).toEqual({ dCol: -1, dRow: 0, dColSpan: 1, dRowSpan: 0 })
  })

  it("northwest handle combines both north + west", () => {
    const d = resizeDeltaFromPx("nw", -100, -50, cellW, cellH)
    expect(d).toEqual({ dCol: -1, dRow: -1, dColSpan: 1, dRowSpan: 1 })
  })

  it("southeast handle combines both south + east", () => {
    const d = resizeDeltaFromPx("se", 200, 100, cellW, cellH)
    expect(d).toEqual({ dCol: 0, dRow: 0, dColSpan: 2, dRowSpan: 2 })
  })

  it("northeast handle combines north + east", () => {
    const d = resizeDeltaFromPx("ne", 100, -50, cellW, cellH)
    expect(d).toEqual({ dCol: 0, dRow: -1, dColSpan: 1, dRowSpan: 1 })
  })

  it("southwest handle combines south + west", () => {
    const d = resizeDeltaFromPx("sw", -100, 50, cellW, cellH)
    expect(d).toEqual({ dCol: -1, dRow: 0, dColSpan: 1, dRowSpan: 1 })
  })
})


describe("DRAG_THRESHOLD_PX", () => {
  it("is small enough to prevent accidental drag-on-click but still fires on intentional drags", () => {
    expect(DRAG_THRESHOLD_PX).toBeGreaterThan(0)
    expect(DRAG_THRESHOLD_PX).toBeLessThan(10)
  })
})

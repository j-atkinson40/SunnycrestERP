/**
 * Tests for the canvas interactions hook's pure helpers (R-3.1
 * row-aware shape).
 *
 * The state-machine portion of the hook is integration-tested via
 * Playwright (real pointer events on the rendered canvas). At the
 * unit level we cover the row-hit-test math + per-row cellWidth +
 * resize-delta translation + column-count overflow validation
 * because they're the load-bearing pure functions that drive every
 * commit.
 *
 * R-3.1 changes from R-3.0:
 *   - resizeDeltaFromPx returns column-axis-only delta (dCol +
 *     dColSpan); row-axis resize via right-rail row_height inspector
 *   - new pure helpers: cellWidthFor, pointerToColumnIndex,
 *     pointerToInsertIndex, validateColumnCountChange
 *   - gridDeltaFromPx removed (replaced by per-row cellWidth lookup)
 */
import { describe, expect, it } from "vitest"
import { _internals } from "./use-canvas-interactions"
import type { CompositionRow } from "@/lib/visual-editor/compositions/types"

const {
  snapPxToCells,
  cellWidthFor,
  pointerToColumnIndex,
  pointerToInsertIndex,
  validateColumnCountChange,
  resizeDeltaFromPx,
  DRAG_THRESHOLD_PX,
  CANVAS_PADDING_PX,
} = _internals


function makeRow(
  rowId: string,
  columnCount: number,
  placements: CompositionRow["placements"] = [],
): CompositionRow {
  return {
    row_id: rowId,
    column_count: columnCount,
    row_height: "auto",
    column_widths: null,
    nested_rows: null,
    placements,
  }
}


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


describe("cellWidthFor", () => {
  it("computes per-row cell width from row width + column_count + gap", () => {
    // 1200px wide, 12 cols, 12px gap → (1200 - 12*11) / 12 = (1200 - 132) / 12 = 1068 / 12 = 89
    expect(cellWidthFor(1200, 12, 12)).toBeCloseTo(89, 0)
  })

  it("scales with column_count change (per-row R-3.1 lookup)", () => {
    // Same row width, fewer columns → wider cells
    const w12 = cellWidthFor(1200, 12, 12)
    const w4 = cellWidthFor(1200, 4, 12)
    expect(w4).toBeGreaterThan(w12)
  })

  it("handles 1-column edge case (no gap math needed)", () => {
    expect(cellWidthFor(800, 1, 12)).toBe(800)
  })

  it("returns 0 defensively when column_count < 1", () => {
    expect(cellWidthFor(1200, 0, 12)).toBe(0)
  })
})


describe("pointerToColumnIndex", () => {
  it("returns 0-indexed column for pointer at row's left edge", () => {
    expect(pointerToColumnIndex(0, 1200, 12, 12)).toBe(0)
  })

  it("returns last column index for pointer at row's right edge", () => {
    // At the right edge, offsetXInRow ≈ rowWidth → last column
    expect(pointerToColumnIndex(1199, 1200, 12, 12)).toBe(11)
  })

  it("clamps to [0, column_count - 1]", () => {
    // Way past the right edge — clamp
    expect(pointerToColumnIndex(5000, 1200, 12, 12)).toBe(11)
    // Negative offset (shouldn't happen but defensive)
    expect(pointerToColumnIndex(-100, 1200, 12, 12)).toBe(0)
  })

  it("scales correctly across column_counts (per-row R-3.1 lookup)", () => {
    // Row with column_count=4: pointer at center (~600px) → col 2
    expect(pointerToColumnIndex(600, 1200, 4, 12)).toBeGreaterThanOrEqual(1)
    expect(pointerToColumnIndex(600, 1200, 4, 12)).toBeLessThanOrEqual(2)
  })
})


describe("pointerToInsertIndex", () => {
  const rowRects = [
    { rowId: "r1", top: 0, bottom: 100 },
    { rowId: "r2", top: 100, bottom: 200 },
    { rowId: "r3", top: 200, bottom: 300 },
  ]

  it("returns 0 when pointer is above all rows", () => {
    expect(pointerToInsertIndex(-50, rowRects)).toBe(0)
  })

  it("returns rows.length when pointer is below all rows", () => {
    expect(pointerToInsertIndex(500, rowRects)).toBe(3)
  })

  it("returns row index when pointer is in row's top half", () => {
    // Pointer at y=10, in row 0's top half → insert at 0
    expect(pointerToInsertIndex(10, rowRects)).toBe(0)
  })

  it("returns row index + 1 when pointer is in row's bottom half", () => {
    // Pointer at y=80, in row 0's bottom half → insert at 1
    expect(pointerToInsertIndex(80, rowRects)).toBe(1)
  })

  it("handles insertion in middle row", () => {
    // Pointer at y=120, in row 1's top half → insert at 1
    expect(pointerToInsertIndex(120, rowRects)).toBe(1)
    // Pointer at y=180, in row 1's bottom half → insert at 2
    expect(pointerToInsertIndex(180, rowRects)).toBe(2)
  })

  it("returns 0 for empty rowRects (defensive)", () => {
    expect(pointerToInsertIndex(100, [])).toBe(0)
  })
})


describe("validateColumnCountChange", () => {
  it("permits any column count change for empty row", () => {
    const empty = makeRow("r1", 12)
    expect(validateColumnCountChange(empty, 1)).toEqual({ ok: true })
    expect(validateColumnCountChange(empty, 8)).toEqual({ ok: true })
    expect(validateColumnCountChange(empty, 12)).toEqual({ ok: true })
  })

  it("permits increase always (whitespace appears right of placements)", () => {
    const row = makeRow("r1", 4, [
      {
        placement_id: "p1",
        component_kind: "widget",
        component_name: "today",
        starting_column: 0,
        column_span: 4,
        prop_overrides: {},
        display_config: {},
        nested_rows: null,
      },
    ])
    expect(validateColumnCountChange(row, 8)).toEqual({ ok: true })
    expect(validateColumnCountChange(row, 12)).toEqual({ ok: true })
  })

  it("rejects decrease that would clip a placement", () => {
    const row = makeRow("r1", 12, [
      {
        placement_id: "p1",
        component_kind: "widget",
        component_name: "today",
        starting_column: 8,
        column_span: 4,
        prop_overrides: {},
        display_config: {},
        nested_rows: null,
      },
    ])
    // Reducing to 8: 8 + 4 = 12 > 8 → blocked
    const result = validateColumnCountChange(row, 8)
    expect(result.ok).toBe(false)
    if (!result.ok) {
      expect(result.blockingCount).toBe(1)
    }
  })

  it("permits decrease when no placements would clip", () => {
    const row = makeRow("r1", 12, [
      {
        placement_id: "p1",
        component_kind: "widget",
        component_name: "today",
        starting_column: 0,
        column_span: 4,
        prop_overrides: {},
        display_config: {},
        nested_rows: null,
      },
    ])
    // Reducing to 4: 0 + 4 = 4 <= 4 → permitted
    expect(validateColumnCountChange(row, 4)).toEqual({ ok: true })
  })

  it("counts multiple blocking placements correctly", () => {
    const row = makeRow("r1", 12, [
      {
        placement_id: "p1",
        component_kind: "widget",
        component_name: "today",
        starting_column: 6,
        column_span: 3,
        prop_overrides: {},
        display_config: {},
        nested_rows: null,
      },
      {
        placement_id: "p2",
        component_kind: "widget",
        component_name: "today",
        starting_column: 9,
        column_span: 3,
        prop_overrides: {},
        display_config: {},
        nested_rows: null,
      },
    ])
    // Reducing to 6: both placements would overflow (6+3>6 and 9+3>6)
    const result = validateColumnCountChange(row, 6)
    expect(result.ok).toBe(false)
    if (!result.ok) {
      expect(result.blockingCount).toBe(2)
    }
  })
})


describe("resizeDeltaFromPx (column-axis only in R-3.1)", () => {
  const cellW = 100

  it("east handle grows column_span only", () => {
    const d = resizeDeltaFromPx("e", 200, cellW)
    expect(d).toEqual({ dCol: 0, dColSpan: 2 })
  })

  it("west handle moves starting_column AND shrinks column_span", () => {
    const d = resizeDeltaFromPx("w", -100, cellW)
    expect(d).toEqual({ dCol: -1, dColSpan: 1 })
  })

  it("northwest + southwest handles use west math (column-axis only)", () => {
    const dnw = resizeDeltaFromPx("nw", -100, cellW)
    const dsw = resizeDeltaFromPx("sw", -100, cellW)
    // Both: dCol=-1, dColSpan=+1 (west motion); n/s axis is no-op
    expect(dnw).toEqual({ dCol: -1, dColSpan: 1 })
    expect(dsw).toEqual({ dCol: -1, dColSpan: 1 })
  })

  it("northeast + southeast handles use east math", () => {
    const dne = resizeDeltaFromPx("ne", 200, cellW)
    const dse = resizeDeltaFromPx("se", 200, cellW)
    expect(dne).toEqual({ dCol: 0, dColSpan: 2 })
    expect(dse).toEqual({ dCol: 0, dColSpan: 2 })
  })

  it("north + south handles are no-ops in R-3.1 (column-axis only)", () => {
    expect(resizeDeltaFromPx("n", 0, cellW)).toEqual({ dCol: 0, dColSpan: 0 })
    expect(resizeDeltaFromPx("s", 0, cellW)).toEqual({ dCol: 0, dColSpan: 0 })
  })
})


describe("DRAG_THRESHOLD_PX + CANVAS_PADDING_PX", () => {
  it("DRAG_THRESHOLD_PX is small enough to prevent accidental drag-on-click", () => {
    expect(DRAG_THRESHOLD_PX).toBeGreaterThan(0)
    expect(DRAG_THRESHOLD_PX).toBeLessThan(10)
  })

  it("CANVAS_PADDING_PX matches canvas grid padding (1rem)", () => {
    expect(CANVAS_PADDING_PX).toBe(16)
  })
})

/**
 * The capture grid's two columns: every row placed, exactly once.
 *
 * ⚠️ THE PROTOTYPE HAS NO TWO-COLUMN GROUPING AND I CHECKED BEFORE INVENTING ONE.
 * Measured in `docs/prototypes/2026-10-01-opas-overlay.html` (md5
 * `a52a1e95153bd5c686b88d0acffc31e6`, 93177 bytes): the capture rows are
 * `.caps{display:flex;flex-direction:column;gap:7px}` — a SINGLE column — inside
 * `.win.wide{width:min(440px,calc(100vw - 32px))}`. So the order below is James's
 * direction, not a quotation, and this file says so because "the prototype said" is
 * a claim someone will otherwise inherit.
 *
 * ⚠️ THE RATCHET IS THE POINT. A row the server adds and the column map does not
 * name would be captured and silently not rendered — the same class as the three
 * template fields that had no row at all, found two days earlier by enumerating a
 * source map rather than reading it.
 */
import { describe, expect, it } from "vitest"

import { LEFT_COLUMN, RIGHT_COLUMN, splitIntoColumns } from "./CapturePane"

/** ⚠️ WRITTEN OUT, NOT IMPORTED FROM THE SURFACE. The server owns the row list; this
 *  is the copy a human has to keep in step, and the whole value of the assertion is
 *  that the two are compared rather than derived from each other. */
const EVERY_CAPTURE_ROW: readonly string[] = [
  "funeral_home",
  "contact",
  "deceased_name",
  "dates",
  "service",
  "cemetery",
  "vault",
  "personalization",
  "cemetery_equipment",
  "burial",
]

describe("every row is placed exactly once", () => {
  it("the two columns together name every capture row", () => {
    expect([...LEFT_COLUMN, ...RIGHT_COLUMN].sort()).toEqual(
      [...EVERY_CAPTURE_ROW].sort(),
    )
  })

  it("no row is in both columns", () => {
    const both = LEFT_COLUMN.filter((id) => RIGHT_COLUMN.includes(id))
    expect(both).toEqual([])
  })

  it("the columns are balanced, so neither runs long enough to need a scrollbar", () => {
    // ⚠️ THE WHOLE REASON FOR THE GRID. Ten rows in one column do not fit above the
    // bar at 800px tall; five and five do. A lopsided split would reintroduce the
    // scrollbar the grid exists to remove.
    expect(Math.abs(LEFT_COLUMN.length - RIGHT_COLUMN.length)).toBeLessThanOrEqual(1)
  })

  it("keeps the ruled order within each column", () => {
    // James's direction, 2026-10-13, verbatim: "left column funeral home, deceased,
    // dates, burial, service; right column vault, personalization rows, cemetery,
    // equipment, contact".
    expect(LEFT_COLUMN).toEqual([
      "funeral_home", "deceased_name", "dates", "burial", "service",
    ])
    expect(RIGHT_COLUMN).toEqual([
      "vault", "personalization", "cemetery", "cemetery_equipment", "contact",
    ])
  })
})

describe("splitIntoColumns", () => {
  const rows = EVERY_CAPTURE_ROW.map((row_id) => ({ row_id }))

  it("splits in the ruled order and drops nothing", () => {
    const { left, right } = splitIntoColumns(rows)
    expect(left.map((r) => r.row_id)).toEqual(LEFT_COLUMN)
    expect(right.map((r) => r.row_id)).toEqual(RIGHT_COLUMN)
    expect(left.length + right.length).toBe(rows.length)
  })

  it("omits a row the server did not send, rather than rendering a hole", () => {
    // ⚠️ THE PERSONALIZATION ROW IS ABSENT UNTIL A VAULT RESOLVES — measured
    // behaviour of the surface, not an edge case. The column must close up.
    const without = rows.filter((r) => r.row_id !== "personalization")
    const { right } = splitIntoColumns(without)
    expect(right.map((r) => r.row_id)).toEqual(
      RIGHT_COLUMN.filter((id) => id !== "personalization"),
    )
  })

  it("RENDERS a row neither column names, instead of dropping it", () => {
    // ⚠️ INVISIBLE-AND-CAPTURED IS THE FAILURE THIS ARC KEEPS FINDING, so an
    // unplaced row is shown rather than silently discarded. The ratchet above keeps
    // the set empty; this keeps a non-empty set harmless.
    const { left, right } = splitIntoColumns([...rows, { row_id: "brand_new_row" }])
    const all = [...left, ...right].map((r) => r.row_id)
    expect(all).toContain("brand_new_row")
    expect(all).toHaveLength(EVERY_CAPTURE_ROW.length + 1)
  })

  it("alternates unplaced rows so one column cannot run long", () => {
    const extras = [{ row_id: "x1" }, { row_id: "x2" }, { row_id: "x3" }]
    const { left, right } = splitIntoColumns([...rows, ...extras])
    expect(left.map((r) => r.row_id)).toContain("x1")
    expect(right.map((r) => r.row_id)).toContain("x2")
    expect(left.map((r) => r.row_id)).toContain("x3")
  })
})

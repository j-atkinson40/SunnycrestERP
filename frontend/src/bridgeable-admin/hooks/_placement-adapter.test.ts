/**
 * F-3.1a — placement adapter field-mapping tests.
 *
 * Covers every translation in both directions plus tolerance edges:
 * null/empty chrome, missing optional fields, either-shape input on
 * load (legacy frontend-shaped JSONB still in DB), roundtrip
 * preservation, off-by-one column index translation.
 */
import { describe, expect, it } from "vitest"

import {
  backendToFrontendPlacement,
  backendToFrontendRow,
  backendToFrontendRows,
  frontendToBackendPlacement,
  frontendToBackendRow,
  frontendToBackendRows,
} from "./_placement-adapter"
import type { FocusRow, WidgetPlacement } from "./useFocusTemplateDraft"

describe("frontendToBackendPlacement — field mapping", () => {
  it("maps id → placement_id", () => {
    const p: WidgetPlacement = {
      id: "w-1",
      widget_slug: "day-strip-widget",
      column_start: 1,
      column_span: 4,
      chrome: {},
    }
    expect(frontendToBackendPlacement(p).placement_id).toBe("w-1")
  })

  it("maps widget_slug → component_name + component_kind:widget", () => {
    const p: WidgetPlacement = {
      id: "w-1",
      widget_slug: "today-pin-widget",
      column_start: 1,
      column_span: 4,
      chrome: {},
    }
    const out = frontendToBackendPlacement(p)
    expect(out.component_name).toBe("today-pin-widget")
    expect(out.component_kind).toBe("widget")
  })

  it("translates column_start 1-indexed → starting_column 0-indexed", () => {
    const p: WidgetPlacement = {
      id: "w-1",
      widget_slug: "day-strip-widget",
      column_start: 1,
      column_span: 4,
      chrome: {},
    }
    expect(frontendToBackendPlacement(p).starting_column).toBe(0)
  })

  it("translates column_start=5 → starting_column=4", () => {
    const p: WidgetPlacement = {
      id: "w-1",
      widget_slug: "day-strip-widget",
      column_start: 5,
      column_span: 4,
      chrome: {},
    }
    expect(frontendToBackendPlacement(p).starting_column).toBe(4)
  })

  it("clamps column_start=0 → starting_column=0 (defensive)", () => {
    const p: WidgetPlacement = {
      id: "w-1",
      widget_slug: "day-strip-widget",
      column_start: 0,
      column_span: 4,
      chrome: {},
    }
    expect(frontendToBackendPlacement(p).starting_column).toBe(0)
  })

  it("passes column_span through unchanged", () => {
    const p: WidgetPlacement = {
      id: "w-1",
      widget_slug: "day-strip-widget",
      column_start: 1,
      column_span: 7,
      chrome: {},
    }
    expect(frontendToBackendPlacement(p).column_span).toBe(7)
  })

  it("maps non-empty chrome → prop_overrides", () => {
    const p: WidgetPlacement = {
      id: "w-1",
      widget_slug: "day-strip-widget",
      column_start: 1,
      column_span: 4,
      chrome: { daysVisible: 5, highlightToday: true },
    }
    const out = frontendToBackendPlacement(p)
    expect(out.prop_overrides).toEqual({ daysVisible: 5, highlightToday: true })
  })

  it("omits prop_overrides when chrome is empty", () => {
    const p: WidgetPlacement = {
      id: "w-1",
      widget_slug: "day-strip-widget",
      column_start: 1,
      column_span: 4,
      chrome: {},
    }
    expect("prop_overrides" in frontendToBackendPlacement(p)).toBe(false)
  })
})

describe("backendToFrontendPlacement — field mapping", () => {
  it("maps placement_id → id", () => {
    expect(
      backendToFrontendPlacement({
        placement_id: "w-1",
        component_kind: "widget",
        component_name: "day-strip-widget",
        starting_column: 0,
        column_span: 4,
      }).id,
    ).toBe("w-1")
  })

  it("maps component_name → widget_slug", () => {
    expect(
      backendToFrontendPlacement({
        placement_id: "w-1",
        component_kind: "widget",
        component_name: "today-pin-widget",
        starting_column: 0,
        column_span: 4,
      }).widget_slug,
    ).toBe("today-pin-widget")
  })

  it("translates starting_column 0-indexed → column_start 1-indexed", () => {
    expect(
      backendToFrontendPlacement({
        placement_id: "w-1",
        component_kind: "widget",
        component_name: "x",
        starting_column: 0,
        column_span: 4,
      }).column_start,
    ).toBe(1)
  })

  it("translates starting_column=4 → column_start=5", () => {
    expect(
      backendToFrontendPlacement({
        placement_id: "w-1",
        component_kind: "widget",
        component_name: "x",
        starting_column: 4,
        column_span: 4,
      }).column_start,
    ).toBe(5)
  })

  it("maps prop_overrides → chrome", () => {
    const out = backendToFrontendPlacement({
      placement_id: "w-1",
      component_kind: "widget",
      component_name: "x",
      starting_column: 0,
      column_span: 4,
      prop_overrides: { daysVisible: 5 },
    })
    expect(out.chrome).toEqual({ daysVisible: 5 })
  })

  it("returns empty chrome when prop_overrides absent", () => {
    const out = backendToFrontendPlacement({
      placement_id: "w-1",
      component_kind: "widget",
      component_name: "x",
      starting_column: 0,
      column_span: 4,
    })
    expect(out.chrome).toEqual({})
  })

  it("tolerates legacy frontend-shaped input (id key not placement_id)", () => {
    const out = backendToFrontendPlacement({
      id: "w-legacy",
      widget_slug: "day-strip-widget",
      column_start: 3,
      column_span: 4,
      chrome: { x: 1 },
    })
    expect(out.id).toBe("w-legacy")
    expect(out.widget_slug).toBe("day-strip-widget")
    // legacy column_start was 1-indexed; adapter normalises round-trip.
    expect(out.column_start).toBe(3)
    expect(out.chrome).toEqual({ x: 1 })
  })

  it("falls back to 'unknown' component name when missing", () => {
    const out = backendToFrontendPlacement({
      placement_id: "w-bad",
      starting_column: 0,
      column_span: 4,
    } as unknown as Parameters<typeof backendToFrontendPlacement>[0])
    expect(out.widget_slug).toBe("unknown")
  })
})

describe("roundtrip preserves all fields", () => {
  it("frontend → backend → frontend yields identical placement", () => {
    const original: WidgetPlacement = {
      id: "w-1",
      widget_slug: "day-strip-widget",
      column_start: 3,
      column_span: 6,
      chrome: { daysVisible: 7, highlightToday: false, weekStartsOn: "monday" },
    }
    const out = backendToFrontendPlacement(frontendToBackendPlacement(original))
    expect(out).toEqual(original)
  })

  it("backend → frontend → backend yields identical placement", () => {
    const original = {
      placement_id: "w-2",
      component_kind: "widget" as const,
      component_name: "today-pin-widget",
      starting_column: 4,
      column_span: 4,
      prop_overrides: { showCount: true },
    }
    const out = frontendToBackendPlacement(backendToFrontendPlacement(original))
    expect(out.placement_id).toBe("w-2")
    expect(out.component_kind).toBe("widget")
    expect(out.component_name).toBe("today-pin-widget")
    expect(out.starting_column).toBe(4)
    expect(out.column_span).toBe(4)
    expect(out.prop_overrides).toEqual({ showCount: true })
  })
})

describe("row-level adapters", () => {
  it("frontendToBackendRow preserves row_index + column_count", () => {
    const row: FocusRow = { row_index: 2, column_count: 12, placements: [] }
    const out = frontendToBackendRow(row)
    expect(out.row_index).toBe(2)
    expect(out.column_count).toBe(12)
    expect(out.placements).toEqual([])
  })

  it("frontendToBackendRow translates all placements", () => {
    const row: FocusRow = {
      row_index: 0,
      column_count: 12,
      placements: [
        {
          id: "w-1",
          widget_slug: "day-strip-widget",
          column_start: 1,
          column_span: 4,
          chrome: {},
        },
        {
          id: "w-2",
          widget_slug: "today-pin-widget",
          column_start: 5,
          column_span: 4,
          chrome: { showCount: true },
        },
      ],
    }
    const out = frontendToBackendRow(row)
    expect(out.placements).toHaveLength(2)
    expect(out.placements[0].placement_id).toBe("w-1")
    expect(out.placements[0].starting_column).toBe(0)
    expect(out.placements[1].placement_id).toBe("w-2")
    expect(out.placements[1].starting_column).toBe(4)
    expect(out.placements[1].prop_overrides).toEqual({ showCount: true })
  })

  it("backendToFrontendRow tolerates missing column_count", () => {
    const out = backendToFrontendRow({
      placements: [],
    } as unknown as Parameters<typeof backendToFrontendRow>[0])
    expect(out.column_count).toBe(12)
    expect(out.row_index).toBe(0)
  })

  it("backendToFrontendRows tolerates null/undefined input", () => {
    expect(backendToFrontendRows(null)).toEqual([])
    expect(backendToFrontendRows(undefined)).toEqual([])
    expect(backendToFrontendRows([])).toEqual([])
  })

  it("frontendToBackendRows round-trips identically through backendToFrontendRows", () => {
    const rows = [
      {
        row_index: 0,
        column_count: 12,
        placements: [
          {
            id: "w-1",
            widget_slug: "day-strip-widget",
            column_start: 1,
            column_span: 12,
            chrome: { daysVisible: 5 },
          },
        ],
      },
    ]
    const out = backendToFrontendRows(frontendToBackendRows(rows))
    expect(out).toEqual(rows)
  })
})

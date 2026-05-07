/**
 * CompositionRenderer tests (R-3.0 rows shape).
 *
 * Verifies:
 *   - Renders rows + placements at correct grid positions
 *   - Outer container is flex-col (rows stack vertically)
 *   - Each row's inner CSS Grid uses its own column_count
 *   - 0-indexed starting_column → 1-indexed CSS Grid translation
 *   - Editor mode shows selection affordances
 *   - Empty composition shows the editor-mode empty placeholder
 *   - onPlacementClick fires when placements are clicked in editor mode
 *   - Source attribute reflects composition.source
 */
import { describe, expect, it, vi } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"
import { CompositionRenderer } from "./CompositionRenderer"
import type {
  CompositionRow,
  Placement,
  ResolvedComposition,
} from "./types"
import {
  oneRowOnePlacementFullWidth,
  oneRowFourEqualPlacements,
  twoRowsKanbanPlusWidgets,
  threeRowsMixedColumnCounts,
} from "@/test/fixtures/compositions"


function makeResolved(
  rows: CompositionRow[] = [],
  source: ResolvedComposition["source"] = null,
): ResolvedComposition {
  return {
    focus_type: "scheduling",
    vertical: "funeral_home",
    tenant_id: null,
    source,
    source_id: null,
    source_version: null,
    rows,
    canvas_config: {
      gap_size: 12,
      background_treatment: "surface-base",
    },
  }
}


function makeRow(
  row_id: string,
  column_count: number,
  placements: Placement[],
): CompositionRow {
  return {
    row_id,
    column_count,
    row_height: "auto",
    column_widths: null,
    nested_rows: null,
    placements,
  }
}


function makePlacement(
  placement_id: string,
  opts: {
    starting_column?: number
    column_span?: number
    display_config?: Placement["display_config"]
    component_name?: string
  } = {},
): Placement {
  return {
    placement_id,
    component_kind: "widget",
    component_name: opts.component_name ?? "today",
    starting_column: opts.starting_column ?? 0,
    column_span: opts.column_span ?? 1,
    prop_overrides: {},
    display_config: opts.display_config ?? {},
    nested_rows: null,
  }
}


describe("CompositionRenderer (R-3.0 rows shape)", () => {
  it("renders the renderer + outer grid containers", () => {
    render(<CompositionRenderer composition={makeResolved()} />)
    expect(screen.getByTestId("composition-renderer")).toBeTruthy()
    expect(screen.getByTestId("composition-grid")).toBeTruthy()
  })

  it("data-source reflects the composition source", () => {
    render(
      <CompositionRenderer
        composition={makeResolved([], "vertical_default")}
      />,
    )
    expect(
      screen.getByTestId("composition-renderer").getAttribute("data-source"),
    ).toBe("vertical_default")
  })

  it("editor mode shows the empty-canvas placeholder when no rows", () => {
    render(<CompositionRenderer composition={makeResolved()} editorMode={true} />)
    expect(screen.getByTestId("composition-empty")).toBeTruthy()
  })

  it("non-editor mode does NOT show the empty placeholder", () => {
    render(<CompositionRenderer composition={makeResolved()} editorMode={false} />)
    expect(screen.queryByTestId("composition-empty")).toBeNull()
  })

  it("renders a single row at its declared column_count", () => {
    render(
      <CompositionRenderer composition={oneRowOnePlacementFullWidth} />,
    )
    const row = screen.getByTestId("composition-row-row-solo")
    expect(row.getAttribute("data-column-count")).toBe("1")
    expect(row.style.gridTemplateColumns).toContain("repeat(1")
  })

  it("renders multiple rows + each with its own inner CSS Grid", () => {
    render(<CompositionRenderer composition={twoRowsKanbanPlusWidgets} />)
    const kanban = screen.getByTestId("composition-row-row-kanban")
    const widgets = screen.getByTestId("composition-row-row-widgets")
    expect(kanban.getAttribute("data-column-count")).toBe("4")
    expect(widgets.getAttribute("data-column-count")).toBe("4")
    expect(kanban.style.gridTemplateColumns).toContain("repeat(4")
    expect(widgets.style.gridTemplateColumns).toContain("repeat(4")
  })

  it("renders three rows with mixed column_counts independently", () => {
    render(<CompositionRenderer composition={threeRowsMixedColumnCounts} />)
    const r1 = screen.getByTestId("composition-row-row-1col")
    const r4 = screen.getByTestId("composition-row-row-4col")
    const r12 = screen.getByTestId("composition-row-row-12col")
    expect(r1.getAttribute("data-column-count")).toBe("1")
    expect(r4.getAttribute("data-column-count")).toBe("4")
    expect(r12.getAttribute("data-column-count")).toBe("12")
    expect(r1.style.gridTemplateColumns).toContain("repeat(1")
    expect(r4.style.gridTemplateColumns).toContain("repeat(4")
    expect(r12.style.gridTemplateColumns).toContain("repeat(12")
  })

  it("translates 0-indexed starting_column to 1-indexed CSS Grid position", () => {
    render(<CompositionRenderer composition={oneRowFourEqualPlacements} />)
    const today = screen.getByTestId("composition-placement-today") // sc=0
    const recent = screen.getByTestId("composition-placement-recent") // sc=1
    const anomalies = screen.getByTestId("composition-placement-anomalies") // sc=2
    const operator = screen.getByTestId("composition-placement-operator") // sc=3
    // CSS Grid is 1-indexed: starting_column N → gridColumn N+1
    expect(today.style.gridColumn).toContain("1 / span 1")
    expect(recent.style.gridColumn).toContain("2 / span 1")
    expect(anomalies.style.gridColumn).toContain("3 / span 1")
    expect(operator.style.gridColumn).toContain("4 / span 1")
  })

  it("respects column_span on placements", () => {
    render(<CompositionRenderer composition={twoRowsKanbanPlusWidgets} />)
    const vaultSchedule = screen.getByTestId(
      "composition-placement-vault-schedule",
    )
    // starting_column=0 → grid column 1; column_span=3
    expect(vaultSchedule.style.gridColumn).toContain("1 / span 3")
  })

  it("places all four fixture placements within the same row", () => {
    render(<CompositionRenderer composition={oneRowFourEqualPlacements} />)
    // All placements share one parent row container; verify by
    // inspecting they all render under the row's testid.
    const row = screen.getByTestId("composition-row-row-quad")
    const placementsInRow = row.querySelectorAll(
      "[data-testid^='composition-placement-']",
    )
    expect(placementsInRow.length).toBe(4)
  })

  it("highlights the selected placement in editor mode", () => {
    const composition = makeResolved([
      makeRow("r1", 4, [makePlacement("p1", { column_span: 2 })]),
    ])
    render(
      <CompositionRenderer
        composition={composition}
        editorMode={true}
        selectedPlacementId="p1"
      />,
    )
    const p1 = screen.getByTestId("composition-placement-p1")
    expect(p1.getAttribute("data-selected")).toBe("true")
  })

  it("fires onPlacementClick in editor mode", () => {
    const composition = makeResolved([
      makeRow("r1", 4, [makePlacement("p1", { column_span: 2 })]),
    ])
    const onClick = vi.fn()
    render(
      <CompositionRenderer
        composition={composition}
        editorMode={true}
        onPlacementClick={onClick}
      />,
    )
    fireEvent.click(screen.getByTestId("composition-placement-p1"))
    expect(onClick).toHaveBeenCalledWith("p1")
  })

  it("does not fire onPlacementClick outside editor mode", () => {
    const composition = makeResolved([
      makeRow("r1", 4, [makePlacement("p1", { column_span: 2 })]),
    ])
    const onClick = vi.fn()
    render(
      <CompositionRenderer
        composition={composition}
        editorMode={false}
        onPlacementClick={onClick}
      />,
    )
    fireEvent.click(screen.getByTestId("composition-placement-p1"))
    expect(onClick).not.toHaveBeenCalled()
  })

  it("respects show_header=false on placements", () => {
    // The header div carries `border-b` — absent when show_header=false.
    const composition = makeResolved([
      makeRow("r1", 4, [
        makePlacement("no-header", {
          column_span: 2,
          display_config: { show_header: false },
        }),
      ]),
    ])
    render(<CompositionRenderer composition={composition} editorMode={true} />)
    const card = screen.getByTestId("composition-placement-no-header")
    expect(card.querySelector(".border-b")).toBeNull()
  })

  it("respects per-row row_height when set to a pixel value", () => {
    const composition = makeResolved([
      {
        row_id: "tall",
        column_count: 1,
        row_height: 480,
        column_widths: null,
        nested_rows: null,
        placements: [makePlacement("p1")],
      },
    ])
    render(<CompositionRenderer composition={composition} />)
    const row = screen.getByTestId("composition-row-tall")
    expect(row.style.minHeight).toBe("480px")
  })

  it("respects per-row row_height='auto' (no explicit minHeight)", () => {
    const composition = makeResolved([
      {
        row_id: "auto",
        column_count: 1,
        row_height: "auto",
        column_widths: null,
        nested_rows: null,
        placements: [makePlacement("p1")],
      },
    ])
    render(<CompositionRenderer composition={composition} />)
    const row = screen.getByTestId("composition-row-auto")
    // Either empty string or "auto" — both correct depending on jsdom serialization
    expect(["", "auto", "0px"]).toContain(row.style.minHeight)
  })

  it("uses gap_size from canvas_config for outer flex-col gap", () => {
    const composition: ResolvedComposition = {
      ...makeResolved([makeRow("r1", 1, [makePlacement("p1")])]),
      canvas_config: { gap_size: 24, background_treatment: "surface-base" },
    }
    render(<CompositionRenderer composition={composition} />)
    const grid = screen.getByTestId("composition-grid")
    expect(grid.style.gap).toBe("24px")
  })

  it("falls back to default gap_size when canvas_config is empty", () => {
    const composition = {
      ...makeResolved([makeRow("r1", 1, [makePlacement("p1")])]),
      canvas_config: {},
    }
    render(<CompositionRenderer composition={composition} />)
    const grid = screen.getByTestId("composition-grid")
    expect(grid.style.gap).toBe("12px")
  })
})


describe("Canvas placement helpers (registry introspection)", () => {
  it("getCanvasPlaceableComponents filters out non-canvas-placeable kinds", async () => {
    const { getCanvasPlaceableComponents, getAllRegistered } = await import(
      "@/lib/visual-editor/registry"
    )
    const placeable = getCanvasPlaceableComponents()
    const all = getAllRegistered()
    const allDocBlocks = all.filter((e) => e.metadata.type === "document-block")
    const placeableDocBlocks = placeable.filter(
      (e) => e.metadata.type === "document-block",
    )
    if (allDocBlocks.length > 0) {
      expect(placeableDocBlocks.length).toBe(0)
    }
  })
})

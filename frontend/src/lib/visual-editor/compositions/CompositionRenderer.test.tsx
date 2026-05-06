/**
 * CompositionRenderer tests (May 2026 composition layer).
 *
 * Verifies:
 *   - Renders composition placements at correct grid positions
 *   - Editor mode shows selection affordances
 *   - Empty composition shows the editor-mode empty placeholder
 *   - onPlacementClick fires when placements are clicked in editor mode
 *   - Source attribute reflects composition.source
 */
import { describe, expect, it, vi } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"
import { CompositionRenderer } from "./CompositionRenderer"
import type { ResolvedComposition } from "./types"


function makeResolved(
  placements: ResolvedComposition["placements"] = [],
  source: ResolvedComposition["source"] = null,
): ResolvedComposition {
  return {
    focus_type: "scheduling",
    vertical: "funeral_home",
    tenant_id: null,
    source,
    source_id: null,
    source_version: null,
    placements,
    canvas_config: {
      total_columns: 12,
      row_height: 64,
      gap_size: 12,
      background_treatment: "surface-base",
    },
  }
}


describe("CompositionRenderer", () => {
  it("renders the renderer + grid containers", () => {
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

  it("editor mode shows the empty-canvas placeholder when no placements", () => {
    render(<CompositionRenderer composition={makeResolved()} editorMode={true} />)
    expect(screen.getByTestId("composition-empty")).toBeTruthy()
  })

  it("non-editor mode does NOT show the empty placeholder", () => {
    render(<CompositionRenderer composition={makeResolved()} editorMode={false} />)
    expect(screen.queryByTestId("composition-empty")).toBeNull()
  })

  it("renders placements at their grid positions", () => {
    const composition = makeResolved([
      {
        placement_id: "p1",
        component_kind: "widget",
        component_name: "today",
        grid: { column_start: 1, column_span: 8, row_start: 1, row_span: 4 },
        prop_overrides: {},
        display_config: {},
      },
      {
        placement_id: "p2",
        component_kind: "widget",
        component_name: "anomalies",
        grid: { column_start: 9, column_span: 4, row_start: 1, row_span: 4 },
        prop_overrides: {},
        display_config: {},
      },
    ])
    render(<CompositionRenderer composition={composition} />)
    const p1 = screen.getByTestId("composition-placement-p1")
    const p2 = screen.getByTestId("composition-placement-p2")
    expect(p1.style.gridColumn).toContain("1")
    expect(p1.style.gridColumn).toContain("8")
    expect(p2.style.gridColumn).toContain("9")
  })

  it("highlights the selected placement in editor mode", () => {
    const composition = makeResolved([
      {
        placement_id: "p1",
        component_kind: "widget",
        component_name: "today",
        grid: { column_start: 1, column_span: 4, row_start: 1, row_span: 3 },
        prop_overrides: {},
        display_config: {},
      },
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
      {
        placement_id: "p1",
        component_kind: "widget",
        component_name: "today",
        grid: { column_start: 1, column_span: 4, row_start: 1, row_span: 3 },
        prop_overrides: {},
        display_config: {},
      },
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
      {
        placement_id: "p1",
        component_kind: "widget",
        component_name: "today",
        grid: { column_start: 1, column_span: 4, row_start: 1, row_span: 3 },
        prop_overrides: {},
        display_config: {},
      },
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

  it("falls back to default canvas config when composition.canvas_config is empty", () => {
    const composition = {
      ...makeResolved(),
      canvas_config: {},
    }
    render(<CompositionRenderer composition={composition} />)
    const grid = screen.getByTestId("composition-grid")
    // 12-column default
    expect(grid.style.gridTemplateColumns).toContain("12")
  })

  it("respects show_header=false on placements", () => {
    const composition = makeResolved([
      {
        placement_id: "no-header",
        component_kind: "widget",
        component_name: "today",
        grid: { column_start: 1, column_span: 4, row_start: 1, row_span: 3 },
        prop_overrides: {},
        display_config: { show_header: false },
      },
    ])
    render(<CompositionRenderer composition={composition} />)
    const card = screen.getByTestId("composition-placement-no-header")
    // Header element shows component_name when show_header !== false; absent here.
    expect(card.textContent ?? "").not.toContain("widget")
  })
})


describe("Canvas placement helpers (registry introspection)", () => {
  it("getCanvasPlaceableComponents filters out non-canvas-placeable kinds", async () => {
    // The introspection uses the live registry — at minimum widgets
    // are canvas-placeable, document-blocks are not.
    const { getCanvasPlaceableComponents, getAllRegistered } = await import(
      "@/lib/visual-editor/registry"
    )
    const placeable = getCanvasPlaceableComponents()
    const all = getAllRegistered()
    // Document blocks should be in `all` but not in `placeable`.
    const allDocBlocks = all.filter((e) => e.metadata.type === "document-block")
    const placeableDocBlocks = placeable.filter(
      (e) => e.metadata.type === "document-block",
    )
    if (allDocBlocks.length > 0) {
      expect(placeableDocBlocks.length).toBe(0)
    }
  })
})

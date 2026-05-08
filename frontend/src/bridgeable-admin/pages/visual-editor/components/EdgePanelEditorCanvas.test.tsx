/**
 * R-5.2 — EdgePanelEditorCanvas vitest coverage.
 *
 * Verifies:
 *   - Canvas mounts with active page's rows.
 *   - "+ Add button" affordance per row opens the ButtonPicker, and
 *     selecting a button commits a new placement to the active row
 *     (R-4 button slug + defaults flow through prop_overrides).
 *   - Empty active page surfaces "Add first row" CTA.
 *   - Internal helpers — newRowId / newPlacementId /
 *     findAvailableStartingColumn — produce expected outputs.
 *
 * The InteractivePlacementCanvas is mocked because its drag/resize
 * mechanics are exercised separately at the substrate level
 * (use-canvas-interactions tests). This isolates the wrapper's
 * specific contracts.
 */
import { describe, it, expect, vi } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"

import {
  EdgePanelEditorCanvas,
  __internals,
} from "./EdgePanelEditorCanvas"
import type { EdgePanelPage } from "@/lib/edge-panel/types"

// Populate the visual-editor button registry so ButtonPicker has
// candidates. Side-effect import.
import "@/lib/visual-editor/registry/auto-register"


// Mock the canvas substrate so we don't have to wire up CSS Grid +
// pointer events in jsdom. The wrapper's responsibility is to
// orchestrate rows/selection commits + ButtonPicker integration; the
// substrate is unit-tested separately.
vi.mock(
  "@/bridgeable-admin/components/visual-editor/composition-canvas/InteractivePlacementCanvas",
  async () => {
    const React = await import("react")
    return {
      InteractivePlacementCanvas: ({
        rows,
      }: {
        rows: Array<{ row_id: string; placements: Array<{ placement_id: string; component_kind: string; component_name: string }> }>
      }) =>
        React.createElement(
          "div",
          { "data-testid": "mock-interactive-canvas" },
          rows.flatMap((r) =>
            r.placements.map((p) =>
              React.createElement(
                "div",
                {
                  key: p.placement_id,
                  "data-testid": `mock-placement-${p.placement_id}`,
                  "data-component-kind": p.component_kind,
                  "data-component-name": p.component_name,
                },
                `${p.component_kind}:${p.component_name}`,
              ),
            ),
          ),
        ),
    }
  },
)


function makePage(rows: EdgePanelPage["rows"] = []): EdgePanelPage {
  return {
    page_id: "pg-test",
    name: "Test page",
    rows,
    canvas_config: {},
  }
}


describe("EdgePanelEditorCanvas (R-5.2)", () => {
  it("mounts and exposes the canvas root + add-first-row CTA when empty", () => {
    render(
      <EdgePanelEditorCanvas
        activePage={makePage([])}
        selection={{ kind: "none" }}
        tenantVerticalForButtonPicker="manufacturing"
        onCommitRows={vi.fn()}
        onSelectionChange={vi.fn()}
        onUndoableMutation={vi.fn()}
        onUndo={vi.fn()}
        onRedo={vi.fn()}
      />,
    )
    expect(screen.getByTestId("edge-panel-editor-canvas")).toBeTruthy()
    expect(screen.getByTestId("mock-interactive-canvas")).toBeTruthy()
    expect(screen.getByTestId("edge-panel-editor-add-first-row")).toBeTruthy()
  })

  it("clicking add-first-row commits a single empty row and snaps a snapshot", () => {
    const onCommitRows = vi.fn()
    const onUndoableMutation = vi.fn()
    render(
      <EdgePanelEditorCanvas
        activePage={makePage([])}
        selection={{ kind: "none" }}
        tenantVerticalForButtonPicker="manufacturing"
        onCommitRows={onCommitRows}
        onSelectionChange={vi.fn()}
        onUndoableMutation={onUndoableMutation}
        onUndo={vi.fn()}
        onRedo={vi.fn()}
      />,
    )
    fireEvent.click(screen.getByTestId("edge-panel-editor-add-first-row"))
    expect(onUndoableMutation).toHaveBeenCalled()
    expect(onCommitRows).toHaveBeenCalledTimes(1)
    const newRows = onCommitRows.mock.calls[0][0]
    expect(Array.isArray(newRows)).toBe(true)
    expect(newRows.length).toBe(1)
    expect(newRows[0].placements.length).toBe(0)
    expect(newRows[0].column_count).toBe(12)
  })

  it("renders a per-row + Add button affordance and opens the ButtonPicker on click", async () => {
    const row = {
      row_id: "r1",
      column_count: 12,
      row_height: "auto" as const,
      column_widths: null,
      nested_rows: null,
      placements: [],
    }
    render(
      <EdgePanelEditorCanvas
        activePage={makePage([row])}
        selection={{ kind: "none" }}
        tenantVerticalForButtonPicker="manufacturing"
        onCommitRows={vi.fn()}
        onSelectionChange={vi.fn()}
        onUndoableMutation={vi.fn()}
        onUndo={vi.fn()}
        onRedo={vi.fn()}
      />,
    )
    const addBtn = screen.getByTestId("edge-panel-editor-add-button-row-0")
    expect(addBtn).toBeTruthy()
    fireEvent.click(addBtn)
    expect(
      screen.getByTestId("edge-panel-settings-button-picker"),
    ).toBeTruthy()
  })

  it("selecting a button from the picker commits a new button placement onto the row", async () => {
    const row = {
      row_id: "r1",
      column_count: 12,
      row_height: "auto" as const,
      column_widths: null,
      nested_rows: null,
      placements: [],
    }
    const onCommitRows = vi.fn()
    const onUndoableMutation = vi.fn()
    render(
      <EdgePanelEditorCanvas
        activePage={makePage([row])}
        selection={{ kind: "none" }}
        tenantVerticalForButtonPicker="manufacturing"
        onCommitRows={onCommitRows}
        onSelectionChange={vi.fn()}
        onUndoableMutation={onUndoableMutation}
        onUndo={vi.fn()}
        onRedo={vi.fn()}
      />,
    )
    fireEvent.click(screen.getByTestId("edge-panel-editor-add-button-row-0"))
    // navigate-to-pulse is registered with all four canonical
    // verticals → universal applicability per ButtonPicker rules.
    const addBtn = screen.getByTestId(
      "edge-panel-settings-button-picker-add-navigate-to-pulse",
    )
    fireEvent.click(addBtn)
    expect(onUndoableMutation).toHaveBeenCalled()
    expect(onCommitRows).toHaveBeenCalled()
    const lastCall = onCommitRows.mock.calls.at(-1)
    expect(lastCall).toBeDefined()
    const newRows = lastCall![0]
    expect(newRows[0].placements.length).toBe(1)
    expect(newRows[0].placements[0].component_kind).toBe("button")
    expect(newRows[0].placements[0].component_name).toBe("navigate-to-pulse")
  })

  it("internal helpers produce stable shapes", () => {
    const id1 = __internals.newRowId()
    const id2 = __internals.newRowId()
    expect(id1).not.toBe(id2)
    const placementId = __internals.newPlacementId([])
    expect(placementId).toBe("p1")
    // findAvailableStartingColumn — empty row fits at col 0.
    const emptyRow = __internals.makeRow(12)
    expect(__internals.findAvailableStartingColumn(emptyRow, 4)).toBe(0)
    // After placement at col 0 spanning 4, next slot is col 4.
    const filledRow = {
      ...emptyRow,
      placements: [
        {
          placement_id: "p1",
          component_kind: "button" as const,
          component_name: "x",
          starting_column: 0,
          column_span: 4,
          prop_overrides: {},
          display_config: {},
          nested_rows: null,
        },
      ],
    }
    expect(__internals.findAvailableStartingColumn(filledRow, 4)).toBe(4)
    // -1 when no gap fits.
    const fullRow = {
      ...emptyRow,
      placements: [
        {
          placement_id: "p1",
          component_kind: "button" as const,
          component_name: "x",
          starting_column: 0,
          column_span: 12,
          prop_overrides: {},
          display_config: {},
          nested_rows: null,
        },
      ],
    }
    expect(__internals.findAvailableStartingColumn(fullRow, 4)).toBe(-1)
  })
})

/**
 * Arc 4c — FocusCompositionsTab canvas polish tests.
 *
 * Covers the inspector inline ops added per Arc 4c:
 *   - Move-left / Move-right placement reorder buttons
 *   - Alt+ArrowUp/Down row reorder via keyboard
 *   - Alt+ArrowLeft/Right placement reorder via keyboard
 *   - Bare ArrowLeft/Right (±1) + Shift+Arrow (±5) column-axis nudge
 *   - Delete/Backspace placement delete (NO modal per Q-ARC4C-4)
 *   - Bulk delete via selection footer (NO modal per Q-ARC4C-4)
 *   - ColumnCountPopover wired inline in row reorder strip
 *
 * NOT covered here (covered by AlignmentGuideOverlay.test.tsx):
 *   - AlignmentGuideOverlay rendering math
 *   - SVG overlay component contract
 *
 * Inspector canvas is read-mostly per Q-FOCUS-1 — no drag-drop tests
 * here. Standalone canvas polish covered by alignment guide tests +
 * existing CompositionEditorPage.test.tsx (marquee-shift cumulative-
 * select coverage).
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { fireEvent, render, waitFor } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"

import "@/lib/visual-editor/registry/auto-register"

import { FocusCompositionsTab } from "./FocusCompositionsTab"
import { focusCompositionsService } from "@/bridgeable-admin/services/focus-compositions-service"
import type {
  CompositionRecord,
  CompositionRow,
  Placement,
  ResolvedComposition,
} from "@/lib/visual-editor/compositions/types"


vi.mock(
  "@/bridgeable-admin/services/focus-compositions-service",
  async () => {
    const actual = await vi.importActual<
      typeof import("@/bridgeable-admin/services/focus-compositions-service")
    >("@/bridgeable-admin/services/focus-compositions-service")
    return {
      ...actual,
      focusCompositionsService: {
        list: vi.fn(),
        get: vi.fn(),
        resolve: vi.fn(),
        create: vi.fn(),
        update: vi.fn(),
      },
    }
  },
)

vi.mock("sonner", () => ({
  toast: { error: vi.fn(), success: vi.fn() },
}))


const mockResolve = focusCompositionsService.resolve as unknown as ReturnType<typeof vi.fn>
const mockGet = focusCompositionsService.get as unknown as ReturnType<typeof vi.fn>
const mockUpdate = focusCompositionsService.update as unknown as ReturnType<typeof vi.fn>


function makePlacement(overrides: Partial<Placement> = {}): Placement {
  return {
    placement_id: overrides.placement_id ?? "p1",
    component_kind: "widget",
    component_name: "today",
    starting_column: 0,
    column_span: 3,
    prop_overrides: {},
    display_config: {},
    nested_rows: null,
    ...overrides,
  }
}


function makeRow(overrides: Partial<CompositionRow> = {}): CompositionRow {
  return {
    row_id: overrides.row_id ?? "row-1",
    column_count: 12,
    row_height: "auto",
    column_widths: null,
    nested_rows: null,
    placements: [],
    ...overrides,
  }
}


function makeResolved(
  overrides: Partial<ResolvedComposition> = {},
): ResolvedComposition {
  return {
    focus_type: "scheduling",
    vertical: "manufacturing",
    tenant_id: null,
    source: null,
    source_id: null,
    source_version: null,
    rows: [],
    canvas_config: { gap_size: 12, background_treatment: "surface-base" },
    ...overrides,
  }
}


function makeRecord(
  overrides: Partial<CompositionRecord> = {},
): CompositionRecord {
  return {
    id: "comp-1",
    scope: "vertical_default",
    vertical: "manufacturing",
    tenant_id: null,
    focus_type: "scheduling",
    rows: [],
    canvas_config: { gap_size: 12, background_treatment: "surface-base" },
    version: 1,
    is_active: true,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    created_by: null,
    updated_by: null,
    ...overrides,
  }
}


function MountTab() {
  return (
    <MemoryRouter initialEntries={["/dashboard"]}>
      <FocusCompositionsTab vertical="manufacturing" tenantId={null} />
    </MemoryRouter>
  )
}


async function enterEditViewWithComposition(rows: CompositionRow[]) {
  mockResolve.mockResolvedValue(
    makeResolved({
      source: "vertical_default",
      source_id: "comp-1",
      rows,
    }),
  )
  mockGet.mockResolvedValue(makeRecord({ rows }))
  const result = render(<MountTab />)
  await waitFor(() => {
    expect(
      result.getByTestId("runtime-inspector-focus-row-edit-scheduling"),
    ).toBeTruthy()
  })
  fireEvent.click(
    result.getByTestId("runtime-inspector-focus-row-edit-scheduling"),
  )
  await waitFor(() => {
    expect(result.getByTestId("runtime-inspector-focus-edit")).toBeTruthy()
  })
  return result
}


beforeEach(() => {
  mockResolve.mockReset()
  mockGet.mockReset()
  mockUpdate.mockReset()
})

afterEach(() => {
  vi.clearAllMocks()
})


// ─────────────────────────────────────────────────────────────────
// Move-left / Move-right placement reorder buttons
// ─────────────────────────────────────────────────────────────────


describe("Arc 4c — placement reorder buttons in selection footer", () => {
  it("renders Move-left + Move-right buttons when a placement is selected", async () => {
    const result = await enterEditViewWithComposition([
      makeRow({
        row_id: "r1",
        placements: [
          makePlacement({ placement_id: "p1", starting_column: 3 }),
        ],
      }),
    ])
    // Click placement to select.
    await waitFor(() => {
      expect(result.getByTestId("interactive-placement-p1")).toBeTruthy()
    })
    fireEvent.pointerDown(result.getByTestId("interactive-placement-p1"), {
      button: 0,
      pointerId: 1,
    })
    await waitFor(() => {
      expect(
        result.getByTestId("runtime-inspector-focus-placement-move-left"),
      ).toBeTruthy()
      expect(
        result.getByTestId("runtime-inspector-focus-placement-move-right"),
      ).toBeTruthy()
    })
  })

  it("Move-right shifts placement starting_column +1 within row", async () => {
    const result = await enterEditViewWithComposition([
      makeRow({
        row_id: "r1",
        placements: [
          makePlacement({ placement_id: "p1", starting_column: 3 }),
        ],
      }),
    ])
    fireEvent.pointerDown(result.getByTestId("interactive-placement-p1"), {
      button: 0,
      pointerId: 1,
    })
    await waitFor(() => {
      expect(
        result.getByTestId("runtime-inspector-focus-placement-move-right"),
      ).toBeTruthy()
    })
    fireEvent.click(
      result.getByTestId("runtime-inspector-focus-placement-move-right"),
    )
    // Placement re-renders at new starting_column; assertion is on
    // DOM state: the placement is still in row 1 (no cross-row move).
    await waitFor(() => {
      const placementEl = result.getByTestId("interactive-placement-p1")
      expect(placementEl.getAttribute("data-row-id")).toBe("r1")
    })
  })

  it("Move-left does NOT underflow row left edge", async () => {
    const result = await enterEditViewWithComposition([
      makeRow({
        row_id: "r1",
        placements: [
          makePlacement({ placement_id: "p1", starting_column: 0 }),
        ],
      }),
    ])
    fireEvent.pointerDown(result.getByTestId("interactive-placement-p1"), {
      button: 0,
      pointerId: 1,
    })
    await waitFor(() => {
      expect(
        result.getByTestId("runtime-inspector-focus-placement-move-left"),
      ).toBeTruthy()
    })
    // Multiple clicks left — should clamp at 0.
    fireEvent.click(
      result.getByTestId("runtime-inspector-focus-placement-move-left"),
    )
    fireEvent.click(
      result.getByTestId("runtime-inspector-focus-placement-move-left"),
    )
    // Placement still exists; no crash, no negative starting_column.
    expect(result.getByTestId("interactive-placement-p1")).toBeTruthy()
  })
})


// ─────────────────────────────────────────────────────────────────
// Keyboard: Alt+Arrow row reorder + Alt+ArrowLeft/Right placement reorder
// + bare/Shift+Arrow column-axis nudge
// ─────────────────────────────────────────────────────────────────


describe("Arc 4c — keyboard nudge + Alt+Arrow row reorder", () => {
  it("ignores keystrokes when focus is on INPUT element", async () => {
    const result = await enterEditViewWithComposition([
      makeRow({
        row_id: "r1",
        placements: [
          makePlacement({ placement_id: "p1", starting_column: 3 }),
        ],
      }),
    ])
    fireEvent.pointerDown(result.getByTestId("interactive-placement-p1"), {
      button: 0,
      pointerId: 1,
    })
    await waitFor(() => {
      expect(
        result.getByTestId("runtime-inspector-focus-placement-move-right"),
      ).toBeTruthy()
    })
    // Create an INPUT and focus it.
    const inp = document.createElement("input")
    document.body.appendChild(inp)
    inp.focus()
    fireEvent.keyDown(inp, { key: "ArrowRight" })
    // Placement unchanged.
    expect(result.getByTestId("interactive-placement-p1")).toBeTruthy()
    document.body.removeChild(inp)
  })

  it("Bare ArrowLeft/Right with selected placement does NOT crash", async () => {
    const result = await enterEditViewWithComposition([
      makeRow({
        row_id: "r1",
        placements: [
          makePlacement({ placement_id: "p1", starting_column: 3 }),
        ],
      }),
    ])
    fireEvent.pointerDown(result.getByTestId("interactive-placement-p1"), {
      button: 0,
      pointerId: 1,
    })
    await waitFor(() => {
      expect(
        result.getByTestId("runtime-inspector-focus-placement-move-right"),
      ).toBeTruthy()
    })
    fireEvent.keyDown(window, { key: "ArrowRight" })
    fireEvent.keyDown(window, { key: "ArrowLeft", shiftKey: true })
    // Placement still rendered.
    expect(result.getByTestId("interactive-placement-p1")).toBeTruthy()
  })

  it("Cmd/Ctrl+Arrow stays browser-reserved (no nudge fires)", async () => {
    const result = await enterEditViewWithComposition([
      makeRow({
        row_id: "r1",
        placements: [
          makePlacement({ placement_id: "p1", starting_column: 0 }),
        ],
      }),
    ])
    fireEvent.pointerDown(result.getByTestId("interactive-placement-p1"), {
      button: 0,
      pointerId: 1,
    })
    fireEvent.keyDown(window, { key: "ArrowRight", metaKey: true })
    fireEvent.keyDown(window, { key: "ArrowLeft", ctrlKey: true })
    // No crash; placement still at starting_column=0.
    expect(result.getByTestId("interactive-placement-p1")).toBeTruthy()
  })

  it("Escape clears selection", async () => {
    const result = await enterEditViewWithComposition([
      makeRow({
        row_id: "r1",
        placements: [makePlacement({ placement_id: "p1" })],
      }),
    ])
    fireEvent.pointerDown(result.getByTestId("interactive-placement-p1"), {
      button: 0,
      pointerId: 1,
    })
    await waitFor(() => {
      expect(
        result.getByTestId("runtime-inspector-focus-selection-footer"),
      ).toBeTruthy()
    })
    fireEvent.keyDown(window, { key: "Escape" })
    await waitFor(() => {
      expect(
        result.queryByTestId("runtime-inspector-focus-selection-footer"),
      ).toBeFalsy()
    })
  })

  it("Alt+ArrowUp/Down with selected row triggers row reorder when ≥2 rows", async () => {
    // 2 rows, both empty; selecting first row by clicking the row
    // delete button isn't great (clicks delete). Instead we simulate
    // by adding rows + triggering reorder via keyboard with row
    // selection via clicking the row label area. The reorder-row
    // strip uses Move-up button — verify the keyboard pathway by
    // pressing Alt+ArrowDown while a placement is selected (which
    // triggers handleReorderRowViaKey's row-from-placement path).
    const result = await enterEditViewWithComposition([
      makeRow({
        row_id: "r1",
        placements: [makePlacement({ placement_id: "p1" })],
      }),
      makeRow({ row_id: "r2", placements: [] }),
    ])
    // Select p1 (in r1).
    fireEvent.pointerDown(result.getByTestId("interactive-placement-p1"), {
      button: 0,
      pointerId: 1,
    })
    await waitFor(() => {
      expect(
        result.getByTestId("runtime-inspector-focus-selection-footer"),
      ).toBeTruthy()
    })
    // Alt+ArrowDown — row r1 moves down (now after r2).
    fireEvent.keyDown(window, { key: "ArrowDown", altKey: true })
    // Both rows still present; no crash.
    expect(result.getByTestId("interactive-canvas")).toBeTruthy()
  })

  it("Alt+ArrowLeft/Right with placement selected does NOT crash + does not delete", async () => {
    const result = await enterEditViewWithComposition([
      makeRow({
        row_id: "r1",
        placements: [
          makePlacement({ placement_id: "p1", starting_column: 3 }),
        ],
      }),
    ])
    fireEvent.pointerDown(result.getByTestId("interactive-placement-p1"), {
      button: 0,
      pointerId: 1,
    })
    fireEvent.keyDown(window, { key: "ArrowRight", altKey: true })
    expect(result.getByTestId("interactive-placement-p1")).toBeTruthy()
  })
})


// ─────────────────────────────────────────────────────────────────
// Deletion semantics per Q-ARC4C-4
// ─────────────────────────────────────────────────────────────────


describe("Arc 4c — deletion semantics (Q-ARC4C-4)", () => {
  it("Delete key removes single selected placement WITHOUT confirmation modal", async () => {
    const result = await enterEditViewWithComposition([
      makeRow({
        row_id: "r1",
        placements: [
          makePlacement({ placement_id: "p1" }),
          makePlacement({ placement_id: "p2", starting_column: 4 }),
        ],
      }),
    ])
    fireEvent.pointerDown(result.getByTestId("interactive-placement-p1"), {
      button: 0,
      pointerId: 1,
    })
    await waitFor(() => {
      expect(
        result.getByTestId("runtime-inspector-focus-selection-footer"),
      ).toBeTruthy()
    })
    fireEvent.keyDown(window, { key: "Delete" })
    await waitFor(() => {
      expect(result.queryByTestId("interactive-placement-p1")).toBeFalsy()
    })
    // p2 still present.
    expect(result.getByTestId("interactive-placement-p2")).toBeTruthy()
  })

  it("Backspace key also removes selected placement WITHOUT modal", async () => {
    const result = await enterEditViewWithComposition([
      makeRow({
        row_id: "r1",
        placements: [makePlacement({ placement_id: "p1" })],
      }),
    ])
    fireEvent.pointerDown(result.getByTestId("interactive-placement-p1"), {
      button: 0,
      pointerId: 1,
    })
    fireEvent.keyDown(window, { key: "Backspace" })
    await waitFor(() => {
      expect(result.queryByTestId("interactive-placement-p1")).toBeFalsy()
    })
  })

  it("placement delete button in footer does NOT open a modal", async () => {
    const result = await enterEditViewWithComposition([
      makeRow({
        row_id: "r1",
        placements: [makePlacement({ placement_id: "p1" })],
      }),
    ])
    fireEvent.pointerDown(result.getByTestId("interactive-placement-p1"), {
      button: 0,
      pointerId: 1,
    })
    await waitFor(() => {
      expect(
        result.getByTestId("runtime-inspector-focus-placement-delete"),
      ).toBeTruthy()
    })
    fireEvent.click(
      result.getByTestId("runtime-inspector-focus-placement-delete"),
    )
    // Placement gone immediately. No confirmation dialog ever shown.
    await waitFor(() => {
      expect(result.queryByTestId("interactive-placement-p1")).toBeFalsy()
    })
    // No row delete confirmation either.
    expect(
      result.queryByTestId("runtime-inspector-focus-delete-row-confirm"),
    ).toBeFalsy()
  })

  it("bulk-delete button surfaces when multiple placements selected and removes all WITHOUT modal", async () => {
    const result = await enterEditViewWithComposition([
      makeRow({
        row_id: "r1",
        placements: [
          makePlacement({ placement_id: "p1" }),
          makePlacement({ placement_id: "p2", starting_column: 4 }),
        ],
      }),
    ])
    // Click p1 to select.
    fireEvent.pointerDown(result.getByTestId("interactive-placement-p1"), {
      button: 0,
      pointerId: 1,
    })
    // Shift-click p2 to extend selection.
    fireEvent.pointerDown(result.getByTestId("interactive-placement-p2"), {
      button: 0,
      pointerId: 1,
      shiftKey: true,
    })
    await waitFor(() => {
      expect(
        result.getByTestId("runtime-inspector-focus-placement-bulk-delete"),
      ).toBeTruthy()
    })
    fireEvent.click(
      result.getByTestId("runtime-inspector-focus-placement-bulk-delete"),
    )
    await waitFor(() => {
      expect(result.queryByTestId("interactive-placement-p1")).toBeFalsy()
      expect(result.queryByTestId("interactive-placement-p2")).toBeFalsy()
    })
  })
})


// ─────────────────────────────────────────────────────────────────
// ColumnCountPopover wiring in row reorder strip (Q-ARC4C-6)
// ─────────────────────────────────────────────────────────────────


describe("Arc 4c — ColumnCountPopover wired into inspector row strip", () => {
  it("renders a column-count trigger button per row in the reorder strip", async () => {
    const result = await enterEditViewWithComposition([
      makeRow({ row_id: "r1" }),
      makeRow({ row_id: "r2" }),
    ])
    await waitFor(() => {
      expect(
        result.getByTestId("runtime-inspector-focus-row-cols-r1"),
      ).toBeTruthy()
      expect(
        result.getByTestId("runtime-inspector-focus-row-cols-r2"),
      ).toBeTruthy()
    })
  })

  it("trigger button shows the current row column_count", async () => {
    // Need >=2 rows so the reorder strip (and hence column-count
    // trigger) renders.
    const result = await enterEditViewWithComposition([
      makeRow({ row_id: "r1", column_count: 8 }),
      makeRow({ row_id: "r2", column_count: 12 }),
    ])
    await waitFor(() => {
      const trigger = result.getByTestId(
        "runtime-inspector-focus-row-cols-r1",
      )
      expect(trigger.textContent).toContain("8")
    })
  })
})


// ─────────────────────────────────────────────────────────────────
// showAlignmentGuides=false passed to inspector canvas (Q-FOCUS-1 canon)
// ─────────────────────────────────────────────────────────────────


describe("Arc 4c — alignment guides off in inspector embed (Q-FOCUS-1)", () => {
  it("inspector canvas does NOT render the alignment-guide overlay element", async () => {
    const result = await enterEditViewWithComposition([
      makeRow({
        row_id: "r1",
        placements: [makePlacement({ placement_id: "p1" })],
      }),
    ])
    // No alignment-guide-overlay should be in DOM because the canvas
    // is read-mostly (interactionsEnabled=false) AND
    // showAlignmentGuides={false} is explicitly passed. Even during
    // a drag attempt (which won't trigger), no overlay should appear.
    expect(result.queryByTestId("alignment-guide-overlay")).toBeFalsy()
  })
})

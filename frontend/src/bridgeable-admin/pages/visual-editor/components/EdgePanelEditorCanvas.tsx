/**
 * R-5.2 — EdgePanelEditorCanvas.
 *
 * Wraps the R-3.1 InteractivePlacementCanvas substrate for the
 * active page of an edge panel composition. Third consumer of the
 * canvas substrate (alongside CompositionEditorPage + FocusEditorPage's
 * Composition tab). Reuse validates the canvas substrate's prop-driven
 * design empirically.
 *
 * State model (per Section 3 of the R-5.2 investigation report):
 *   - `pages` IS the canonical state, owned by the parent.
 *   - Per-page selection + per-page undo stack live in the parent
 *     keyed on page_id; this component receives the active page's
 *     selection as a prop and emits selection changes / row commits
 *     back to the parent via callbacks.
 *
 * Edit-time mutations:
 *   - Drag/resize/cross-row commits emit row-shape patches which
 *     parent applies to active page's rows + pushes a snapshot.
 *   - Add-button affordance: per-row "+ Add button" opens
 *     R-5.1's ButtonPicker. On select, a new placement is appended
 *     to the row's last available column with a generated UUID.
 *   - Keyboard shortcuts (Cmd+Z/Y/D/Backspace/arrows) wired here for
 *     active-canvas focus only. Skipped when activeElement is a form
 *     input (matches CompositionEditorPage canonical pattern §12).
 *
 * Save discipline (R-5.2 R2 from investigation): expose
 * `gesture.kind` upstream via `onGestureChange` so parent can
 * disable Save during in-flight drag.
 */
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react"
import { Plus } from "lucide-react"

import { Button } from "@/components/ui/button"
import { ButtonPicker } from "@/components/settings/edge-panel/ButtonPicker"
import {
  InteractivePlacementCanvas,
  type Selection,
} from "@/bridgeable-admin/components/visual-editor/composition-canvas/InteractivePlacementCanvas"
import { getByName, type ComponentKind } from "@/lib/visual-editor/registry"
import type {
  CompositionRow,
  Placement,
} from "@/lib/visual-editor/compositions/types"
import type { EdgePanelPage } from "@/lib/edge-panel/types"


export interface EdgePanelEditorCanvasProps {
  activePage: EdgePanelPage
  selection: Selection
  /** Vertical for ButtonPicker filter. null = platform_default scope
   * (admin authoring a universal panel) — picker shows all buttons. */
  tenantVerticalForButtonPicker: string | null
  /** Called whenever the active page's rows mutate. Parent owns the
   * `pages` state + the per-page undo stack; this signals the
   * canonical mutation. The parent is expected to call
   * `onUndoableMutation()` BEFORE applying, so the new rows replace
   * the next snapshot frame. */
  onCommitRows: (newRows: CompositionRow[]) => void
  /** Selection state changes. Parent owns the per-page selection map. */
  onSelectionChange: (next: Selection) => void
  /** Called BEFORE every mutation that should be undo-able. Parent
   * pushes the current state to the page's undo stack; subsequent
   * `onCommitRows(newRows)` then represents the new frame. */
  onUndoableMutation: () => void
  /** Called when user requests undo via Cmd+Z. */
  onUndo: () => void
  /** Called when user requests redo via Cmd+Shift+Z / Cmd+Y. */
  onRedo: () => void
}


/** Stable enough for editor session; backend assigns canonical UUIDs
 * at save time per service-layer normalization. Mirrors
 * CompositionEditorPage's `newRowId`. */
function newRowId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID()
  }
  return `row-${Math.random().toString(36).slice(2, 10)}-${Date.now()}`
}


/** Generate a placement_id unique within the working row set.
 * Mirrors CompositionEditorPage's `newPlacementId`. */
function newPlacementId(allRows: CompositionRow[]): string {
  let i = allRows.flatMap((r) => r.placements).length + 1
  const existingIds = new Set(
    allRows.flatMap((r) => r.placements.map((p) => p.placement_id)),
  )
  while (existingIds.has(`p${i}`)) i += 1
  return `p${i}`
}


/** Find first available starting_column in a row that fits a span.
 * Returns -1 when no gap fits. Mirrors CompositionEditorPage's
 * `findAvailableStartingColumn`. */
function findAvailableStartingColumn(
  row: CompositionRow,
  span: number,
): number {
  const sorted = [...row.placements].sort(
    (a, b) => a.starting_column - b.starting_column,
  )
  let cursor = 0
  for (const p of sorted) {
    if (p.starting_column - cursor >= span) return cursor
    cursor = Math.max(cursor, p.starting_column + p.column_span)
  }
  if (row.column_count - cursor >= span) return cursor
  return -1
}


function makeRow(columnCount = 12): CompositionRow {
  return {
    row_id: newRowId(),
    column_count: columnCount,
    row_height: "auto",
    column_widths: null,
    nested_rows: null,
    placements: [],
  }
}


export function EdgePanelEditorCanvas({
  activePage,
  selection,
  tenantVerticalForButtonPicker,
  onCommitRows,
  onSelectionChange,
  onUndoableMutation,
  onUndo,
  onRedo,
}: EdgePanelEditorCanvasProps) {
  const rows = activePage.rows
  const gapSize =
    typeof activePage.canvas_config?.gap_size === "number"
      ? activePage.canvas_config.gap_size
      : 12
  const backgroundTreatment = activePage.canvas_config?.background_treatment
  const canvasRef = useRef<HTMLDivElement | null>(null)

  // Picker state — modal opened via per-row "+ Add button" affordance.
  const [pickerOpenForRow, setPickerOpenForRow] = useState<string | null>(null)

  // Selected placement ids — flat set for keyboard ops.
  const selectedPlacementIds = useMemo(
    () => selection.placementIds ?? new Set<string>(),
    [selection],
  )

  // ── Row + placement mutation helpers ─────────────────────────

  const handleAddRowAbove = useCallback(
    (rowIndex: number) => {
      onUndoableMutation()
      const next = [...rows]
      const newRow = makeRow(12)
      next.splice(rowIndex, 0, newRow)
      onCommitRows(next)
      onSelectionChange({ kind: "row", rowId: newRow.row_id })
    },
    [rows, onCommitRows, onSelectionChange, onUndoableMutation],
  )

  const handleAddRowBelow = useCallback(
    (rowIndex: number) => {
      onUndoableMutation()
      const next = [...rows]
      const newRow = makeRow(12)
      next.splice(rowIndex + 1, 0, newRow)
      onCommitRows(next)
      onSelectionChange({ kind: "row", rowId: newRow.row_id })
    },
    [rows, onCommitRows, onSelectionChange, onUndoableMutation],
  )

  const handleAddFirstRow = useCallback(() => {
    onUndoableMutation()
    const newRow = makeRow(12)
    onCommitRows([newRow])
    onSelectionChange({ kind: "row", rowId: newRow.row_id })
  }, [onCommitRows, onSelectionChange, onUndoableMutation])

  const handleDeleteRow = useCallback(
    (rowId: string) => {
      const row = rows.find((r) => r.row_id === rowId)
      if (!row) return
      // For non-empty rows we'd ideally confirm; R-5.2 keeps the v1
      // behavior simple — the row is removed unconditionally because
      // every operation is undoable and the panel surface is tighter
      // than the full Compositions canvas (which has dedicated
      // confirm modal). Per Section 9 R1, page-level confirmations
      // only matter at the page level; row-level mutations are
      // routine + undo-recoverable.
      if (row.placements.length > 0) {
        const confirmed =
          typeof window !== "undefined"
            ? window.confirm(
                `Delete row with ${row.placements.length} placement(s)? You can undo (Cmd+Z) immediately after.`,
              )
            : true
        if (!confirmed) return
      }
      onUndoableMutation()
      const next = rows.filter((r) => r.row_id !== rowId)
      onCommitRows(next)
      onSelectionChange({ kind: "none" })
    },
    [rows, onCommitRows, onSelectionChange, onUndoableMutation],
  )

  const handleChangeColumnCount = useCallback(
    (rowId: string, newColumnCount: number) => {
      onUndoableMutation()
      const next = rows.map((r) =>
        r.row_id === rowId ? { ...r, column_count: newColumnCount } : r,
      )
      onCommitRows(next)
    },
    [rows, onCommitRows, onUndoableMutation],
  )

  const handleCommitPlacementMove = useCallback(
    (input: {
      placementId: string
      sourceRowId: string
      targetRowId: string
      newStartingColumn: number
      siblingMoves: Array<{ placementId: string; newStartingColumn: number }>
    }) => {
      const {
        placementId,
        sourceRowId,
        targetRowId,
        newStartingColumn,
        siblingMoves,
      } = input
      onUndoableMutation()
      let next: CompositionRow[]
      if (sourceRowId === targetRowId) {
        next = rows.map((r) => {
          if (r.row_id !== sourceRowId) return r
          return {
            ...r,
            placements: r.placements.map((p) => {
              if (p.placement_id === placementId) {
                return { ...p, starting_column: newStartingColumn }
              }
              const sib = siblingMoves.find(
                (m) => m.placementId === p.placement_id,
              )
              if (sib) return { ...p, starting_column: sib.newStartingColumn }
              return p
            }),
          }
        })
      } else {
        const moved = rows
          .find((r) => r.row_id === sourceRowId)
          ?.placements.find((p) => p.placement_id === placementId)
        if (!moved) return
        next = rows.map((r) => {
          if (r.row_id === sourceRowId) {
            return {
              ...r,
              placements: r.placements.filter(
                (p) => p.placement_id !== placementId,
              ),
            }
          }
          if (r.row_id === targetRowId) {
            return {
              ...r,
              placements: [
                ...r.placements,
                { ...moved, starting_column: newStartingColumn },
              ],
            }
          }
          return r
        })
      }
      onCommitRows(next)
    },
    [rows, onCommitRows, onUndoableMutation],
  )

  const handleCommitPlacementResize = useCallback(
    (input: {
      placementId: string
      rowId: string
      newStartingColumn: number
      newColumnSpan: number
    }) => {
      onUndoableMutation()
      const next = rows.map((r) => {
        if (r.row_id !== input.rowId) return r
        return {
          ...r,
          placements: r.placements.map((p) =>
            p.placement_id === input.placementId
              ? {
                  ...p,
                  starting_column: input.newStartingColumn,
                  column_span: input.newColumnSpan,
                }
              : p,
          ),
        }
      })
      onCommitRows(next)
    },
    [rows, onCommitRows, onUndoableMutation],
  )

  const handleCommitRowReorder = useCallback(
    ({ fromIndex, toIndex }: { fromIndex: number; toIndex: number }) => {
      if (fromIndex === toIndex) return
      onUndoableMutation()
      const next = [...rows]
      const [moved] = next.splice(fromIndex, 1)
      next.splice(toIndex, 0, moved)
      onCommitRows(next)
    },
    [rows, onCommitRows, onUndoableMutation],
  )

  const handleSelectPlacement = useCallback(
    (id: string, opts: { shift: boolean }) => {
      const prevIds = selection.placementIds ?? new Set<string>()
      if (opts.shift) {
        const next = new Set(prevIds)
        if (next.has(id)) next.delete(id)
        else next.add(id)
        if (next.size === 0) onSelectionChange({ kind: "none" })
        else if (next.size === 1)
          onSelectionChange({ kind: "placement", placementIds: next })
        else onSelectionChange({ kind: "placements-multi", placementIds: next })
      } else {
        onSelectionChange({
          kind: "placement",
          placementIds: new Set([id]),
        })
      }
    },
    [selection, onSelectionChange],
  )

  const handleSelectRow = useCallback(
    (rowId: string) => {
      onSelectionChange({ kind: "row", rowId })
    },
    [onSelectionChange],
  )

  const handleDeselectAll = useCallback(() => {
    onSelectionChange({ kind: "none" })
  }, [onSelectionChange])

  const handleMarqueeSelect = useCallback(
    (ids: string[]) => {
      if (ids.length === 0) onSelectionChange({ kind: "none" })
      else if (ids.length === 1)
        onSelectionChange({
          kind: "placement",
          placementIds: new Set(ids),
        })
      else
        onSelectionChange({
          kind: "placements-multi",
          placementIds: new Set(ids),
        })
    },
    [onSelectionChange],
  )

  // ── Button picker integration ────────────────────────────────

  const handleAddButtonToRow = useCallback(
    (rowId: string, slug: string, defaults: Record<string, unknown>) => {
      const targetIdx = rows.findIndex((r) => r.row_id === rowId)
      if (targetIdx < 0) return
      const targetRow = rows[targetIdx]
      const span = Math.min(3, targetRow.column_count)
      let startingColumn = findAvailableStartingColumn(targetRow, span)
      let next = [...rows]
      if (startingColumn < 0) {
        // Append a new row beneath this one + place the button there.
        const newRow = makeRow(targetRow.column_count)
        next = [
          ...next.slice(0, targetIdx + 1),
          newRow,
          ...next.slice(targetIdx + 1),
        ]
        startingColumn = 0
        const placement: Placement = {
          placement_id: newPlacementId(next),
          component_kind: "button" as ComponentKind,
          component_name: slug,
          starting_column: startingColumn,
          column_span: span,
          prop_overrides: { ...defaults },
          display_config: { show_header: false, show_border: false },
          nested_rows: null,
        }
        onUndoableMutation()
        next = next.map((r) =>
          r.row_id === newRow.row_id
            ? { ...r, placements: [...r.placements, placement] }
            : r,
        )
        onCommitRows(next)
        onSelectionChange({
          kind: "placement",
          placementIds: new Set([placement.placement_id]),
        })
        return
      }
      const placement: Placement = {
        placement_id: newPlacementId(rows),
        component_kind: "button" as ComponentKind,
        component_name: slug,
        starting_column: startingColumn,
        column_span: span,
        prop_overrides: { ...defaults },
        display_config: { show_header: false, show_border: false },
        nested_rows: null,
      }
      onUndoableMutation()
      next = next.map((r) =>
        r.row_id === rowId
          ? { ...r, placements: [...r.placements, placement] }
          : r,
      )
      onCommitRows(next)
      onSelectionChange({
        kind: "placement",
        placementIds: new Set([placement.placement_id]),
      })
    },
    [rows, onCommitRows, onSelectionChange, onUndoableMutation],
  )

  // ── Keyboard shortcuts ───────────────────────────────────────

  const handleDeleteSelected = useCallback(() => {
    if (selectedPlacementIds.size === 0) return
    onUndoableMutation()
    const next = rows.map((r) => ({
      ...r,
      placements: r.placements.filter(
        (p) => !selectedPlacementIds.has(p.placement_id),
      ),
    }))
    onCommitRows(next)
    onSelectionChange({ kind: "none" })
  }, [
    rows,
    selectedPlacementIds,
    onCommitRows,
    onSelectionChange,
    onUndoableMutation,
  ])

  const handleNudgeSelected = useCallback(
    (dx: number) => {
      if (selectedPlacementIds.size === 0) return
      onUndoableMutation()
      const next = rows.map((r) => ({
        ...r,
        placements: r.placements.map((p) => {
          if (!selectedPlacementIds.has(p.placement_id)) return p
          const newStart = Math.max(
            0,
            Math.min(r.column_count - p.column_span, p.starting_column + dx),
          )
          return { ...p, starting_column: newStart }
        }),
      }))
      onCommitRows(next)
    },
    [rows, selectedPlacementIds, onCommitRows, onUndoableMutation],
  )

  const handleDuplicateSelected = useCallback(() => {
    if (selectedPlacementIds.size === 0) return
    let working: CompositionRow[] = rows.map((r) => ({
      ...r,
      placements: [...r.placements],
    }))
    const newIds: string[] = []
    for (const id of selectedPlacementIds) {
      let srcRowIdx = -1
      let src: Placement | null = null
      for (let i = 0; i < working.length; i++) {
        const found = working[i].placements.find((p) => p.placement_id === id)
        if (found) {
          srcRowIdx = i
          src = found
          break
        }
      }
      if (!src || srcRowIdx < 0) continue
      const targetRow = working[srcRowIdx]
      const startingColumn = findAvailableStartingColumn(
        targetRow,
        src.column_span,
      )
      if (startingColumn < 0) continue
      const dup: Placement = {
        ...src,
        placement_id: newPlacementId(working),
        starting_column: startingColumn,
        prop_overrides: { ...src.prop_overrides },
        display_config: src.display_config ? { ...src.display_config } : {},
      }
      newIds.push(dup.placement_id)
      working = working.map((r, i) =>
        i === srcRowIdx ? { ...r, placements: [...r.placements, dup] } : r,
      )
    }
    if (newIds.length === 0) return
    onUndoableMutation()
    onCommitRows(working)
    onSelectionChange({
      kind: newIds.length === 1 ? "placement" : "placements-multi",
      placementIds: new Set(newIds),
    })
  }, [
    rows,
    selectedPlacementIds,
    onCommitRows,
    onSelectionChange,
    onUndoableMutation,
  ])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      // R-5.2 R5 — focus discipline. Skip when active element is a
      // form input so typing in page name / panel key / scope select
      // stays unaffected. Mirrors CompositionEditorPage's pattern
      // verbatim per the build prompt.
      const target = e.target as HTMLElement | null
      if (target) {
        const tag = target.tagName
        if (
          tag === "INPUT" ||
          tag === "TEXTAREA" ||
          tag === "SELECT" ||
          target.isContentEditable
        ) {
          return
        }
      }
      const meta = e.metaKey || e.ctrlKey
      if (meta && e.key.toLowerCase() === "z") {
        e.preventDefault()
        if (e.shiftKey) onRedo()
        else onUndo()
        return
      }
      if (meta && e.key.toLowerCase() === "y") {
        e.preventDefault()
        onRedo()
        return
      }
      if (meta && e.key.toLowerCase() === "d") {
        e.preventDefault()
        handleDuplicateSelected()
        return
      }
      if ((e.key === "Backspace" || e.key === "Delete") && !meta) {
        if (selectedPlacementIds.size > 0) {
          e.preventDefault()
          handleDeleteSelected()
        }
        return
      }
      if (e.key === "ArrowLeft" && !meta && selectedPlacementIds.size > 0) {
        e.preventDefault()
        handleNudgeSelected(e.shiftKey ? -3 : -1)
        return
      }
      if (e.key === "ArrowRight" && !meta && selectedPlacementIds.size > 0) {
        e.preventDefault()
        handleNudgeSelected(e.shiftKey ? 3 : 1)
        return
      }
      if (e.key === "Escape") onSelectionChange({ kind: "none" })
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [
    onUndo,
    onRedo,
    handleDuplicateSelected,
    handleDeleteSelected,
    handleNudgeSelected,
    onSelectionChange,
    selectedPlacementIds.size,
  ])

  // ── Render ───────────────────────────────────────────────────

  return (
    <div
      ref={canvasRef}
      data-testid="edge-panel-editor-canvas"
      data-page-id={activePage.page_id}
      className="flex h-full min-h-[320px] w-full flex-col gap-2 overflow-hidden rounded border border-border-subtle bg-surface-base"
    >
      <div className="flex-1 overflow-hidden">
        <InteractivePlacementCanvas
          rows={rows}
          gapSize={gapSize}
          backgroundTreatment={backgroundTreatment}
          selection={selection}
          showGrid
          interactionsEnabled
          onSelectPlacement={handleSelectPlacement}
          onSelectRow={handleSelectRow}
          onDeselectAll={handleDeselectAll}
          onCommitPlacementMove={handleCommitPlacementMove}
          onCommitPlacementResize={handleCommitPlacementResize}
          onCommitRowReorder={handleCommitRowReorder}
          onMarqueeSelect={handleMarqueeSelect}
          onAddRowAbove={handleAddRowAbove}
          onAddRowBelow={handleAddRowBelow}
          onDeleteRow={handleDeleteRow}
          onChangeRowColumnCount={handleChangeColumnCount}
        />
      </div>

      {/* "+ Add button" affordance per row + first-row CTA */}
      <div className="flex shrink-0 flex-col gap-1 border-t border-border-subtle bg-surface-elevated px-2 py-2">
        {rows.length === 0 && (
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={handleAddFirstRow}
            data-testid="edge-panel-editor-add-first-row"
          >
            <Plus className="h-3 w-3" /> Add first row
          </Button>
        )}
        {rows.map((row, idx) => {
          const buttonCount = row.placements.filter(
            (p) => p.component_kind === "button",
          ).length
          return (
            <div
              key={row.row_id}
              className="flex items-center justify-between gap-2 px-1"
            >
              <span className="text-caption text-content-muted">
                Row {idx + 1} ·{" "}
                {row.placements.length === 0
                  ? "empty"
                  : `${row.placements.length} placement${row.placements.length === 1 ? "" : "s"}${buttonCount > 0 ? ` (${buttonCount} button${buttonCount === 1 ? "" : "s"})` : ""}`}
              </span>
              <Button
                type="button"
                size="xs"
                variant="ghost"
                onClick={() => setPickerOpenForRow(row.row_id)}
                data-testid={`edge-panel-editor-add-button-row-${idx}`}
              >
                <Plus className="h-3 w-3" /> Add button
              </Button>
            </div>
          )
        })}
      </div>

      {pickerOpenForRow !== null && (
        <ButtonPicker
          open={pickerOpenForRow !== null}
          onClose={() => setPickerOpenForRow(null)}
          onSelect={(slug, defaults) => {
            handleAddButtonToRow(pickerOpenForRow, slug, defaults)
          }}
          tenantVertical={tenantVerticalForButtonPicker ?? ""}
        />
      )}
    </div>
  )
}


// Re-export Selection type so consumers don't have to import from
// the canvas substrate directly.
export type { Selection }


// Internal helpers exposed for tests.
export const __internals = {
  newRowId,
  newPlacementId,
  findAvailableStartingColumn,
  makeRow,
}


// Acknowledge unused exports for tree-shaking clarity.
void getByName

/**
 * RowControlsStrip — left-edge per-row icon strip for row management.
 *
 * Renders on row hover via CSS group-hover. Affordances:
 *   - Add row above (Lucide ArrowUpToLine)
 *   - Add row below (Lucide ArrowDownToLine)
 *   - Drag handle for row reorder (Lucide GripVertical; pointer-down
 *     starts the row reorder gesture via onStartRowDrag)
 *   - Column count picker (ColumnCountPopover trigger)
 *   - Delete row (Lucide Trash2; calls onDeleteRow which decides
 *     between instant-delete vs confirmation modal in the parent)
 *
 * The strip lives ABSOLUTELY positioned over the row's left edge.
 * Click handlers stopPropagation to prevent the row from interpreting
 * the click as a row-selection or starting a placement drag.
 *
 * Tokens used: bg-surface-elevated, border-border-subtle, rounded-md,
 * shadow-level-1. Brass focus ring on active selection per
 * DESIGN_LANGUAGE §6.
 */
import {
  ArrowDownToLine,
  ArrowUpToLine,
  GripVertical,
  Trash2,
} from "lucide-react"
import type { CompositionRow } from "@/lib/visual-editor/compositions/types"
import { ColumnCountPopover } from "./ColumnCountPopover"


interface Props {
  row: CompositionRow
  rowIndex: number
  isSelected: boolean
  onAddRowAbove: () => void
  onAddRowBelow: () => void
  onDeleteRow: () => void
  onSelectRow: () => void
  onChangeColumnCount: (newColumnCount: number) => void
  onStartRowDrag: (e: React.PointerEvent) => void
}


export function RowControlsStrip({
  row,
  rowIndex,
  isSelected,
  onAddRowAbove,
  onAddRowBelow,
  onDeleteRow,
  onSelectRow,
  onChangeColumnCount,
  onStartRowDrag,
}: Props) {
  return (
    <div
      data-testid={`row-controls-strip-${row.row_id}`}
      data-row-index={rowIndex}
      className={[
        "absolute left-1 top-1 z-10 flex flex-col gap-1 rounded-md border border-border-subtle bg-surface-elevated p-1 opacity-0 shadow-level-1 transition-opacity duration-quick group-hover:opacity-100",
        isSelected ? "opacity-100 ring-1 ring-accent" : "",
      ].join(" ")}
      onClick={(e) => {
        // Strip clicks select the row; individual button clicks
        // stopPropagation below.
        e.stopPropagation()
        onSelectRow()
      }}
    >
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation()
          onAddRowAbove()
        }}
        title="Add row above"
        aria-label="Add row above"
        data-testid={`row-add-above-${row.row_id}`}
        className="flex h-6 w-6 items-center justify-center rounded-sm text-content-muted hover:bg-accent-subtle/40 hover:text-content-strong focus-ring-accent"
      >
        <ArrowUpToLine size={12} />
      </button>

      <button
        type="button"
        onPointerDown={(e) => {
          e.stopPropagation()
          onStartRowDrag(e)
        }}
        title="Drag to reorder row"
        aria-label="Drag to reorder row"
        data-testid={`row-drag-handle-${row.row_id}`}
        className="flex h-6 w-6 cursor-grab items-center justify-center rounded-sm text-content-muted hover:bg-accent-subtle/40 hover:text-content-strong active:cursor-grabbing focus-ring-accent"
      >
        <GripVertical size={12} />
      </button>

      <ColumnCountPopover
        row={row}
        onChange={onChangeColumnCount}
        triggerTestId={`row-column-count-trigger-${row.row_id}`}
        triggerClassName="flex h-6 w-6 items-center justify-center rounded-sm font-plex-mono text-caption text-content-strong hover:bg-accent-subtle/40 focus-ring-accent"
      />

      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation()
          onAddRowBelow()
        }}
        title="Add row below"
        aria-label="Add row below"
        data-testid={`row-add-below-${row.row_id}`}
        className="flex h-6 w-6 items-center justify-center rounded-sm text-content-muted hover:bg-accent-subtle/40 hover:text-content-strong focus-ring-accent"
      >
        <ArrowDownToLine size={12} />
      </button>

      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation()
          onDeleteRow()
        }}
        title="Delete row"
        aria-label="Delete row"
        data-testid={`row-delete-${row.row_id}`}
        className="flex h-6 w-6 items-center justify-center rounded-sm text-content-muted hover:bg-status-error-muted hover:text-status-error focus-ring-accent"
      >
        <Trash2 size={12} />
      </button>
    </div>
  )
}

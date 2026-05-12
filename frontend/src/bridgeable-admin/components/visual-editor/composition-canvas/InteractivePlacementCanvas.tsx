/**
 * InteractivePlacementCanvas — row-aware composition editor canvas.
 *
 * R-3.1 — outer flex-col container; each row renders as inner CSS Grid
 * with its own per-row column_count. Row controls strip (left edge),
 * empty-row placeholder when no placements, drop preview during cross-
 * row drag and row reorder.
 *
 * Distinct from `CompositionRenderer` (runtime renderer + non-interactive
 * editor preview): this component adds:
 *   - drag/resize/cross-row-drop interactions via use-canvas-interactions
 *   - row controls strip per row (add/delete/reorder/column-count)
 *   - drop preview affordance during gestures
 *   - selection state (placements via shift-click; rows via strip click)
 *
 * Performance: drag updates use CSS `transform` on dragged elements
 * (cheap, GPU-accelerated). Grid coord commits on pointer-up via
 * onCommitPlacementMove / onCommitPlacementResize / onCommitRowReorder.
 */
import { useMemo, useRef, type CSSProperties, type ReactNode } from "react"
import { renderComponentPreview } from "@/lib/visual-editor/components/preview-renderers"
import {
  getCanvasMetadata,
  getByName,
  type ComponentKind,
} from "@/lib/visual-editor/registry"
import type {
  CompositionRow,
  Placement,
} from "@/lib/visual-editor/compositions/types"
import {
  useCanvasInteractions,
  type ResizeHandle,
} from "./use-canvas-interactions"
import { RowControlsStrip } from "./RowControlsStrip"
import { RowDropPreview } from "./RowDropPreview"
import { EmptyRowPlaceholder } from "./EmptyRowPlaceholder"
import {
  AlignmentGuideOverlay,
  computeAlignmentGuides,
  liveDraggedRect,
  resolveReferenceRectsForRow,
  type AlignmentGuide,
  type CanvasRect,
} from "./AlignmentGuideOverlay"


export interface Selection {
  kind: "none" | "placement" | "placements-multi" | "row"
  /** Set when kind === "row". */
  rowId?: string
  /** Set when kind === "placement" or "placements-multi". */
  placementIds?: Set<string>
}


export interface InteractivePlacementCanvasProps {
  rows: CompositionRow[]
  gapSize: number
  backgroundTreatment?: string
  selection: Selection
  showGrid?: boolean
  /** When false, drag/resize/row-reorder don't apply (e.g., during a save). */
  interactionsEnabled?: boolean
  /** When true (default), renders SVG alignment-guide overlay during drag
   * for Figma-shape snap feedback per Arc 4c Q-ARC4C-2 canon. Inspector
   * read-mostly canvas (interactionsEnabled=false) should also pass
   * `showAlignmentGuides={false}` to keep the overlay off, though it would
   * never trigger anyway since no drag is possible. */
  showAlignmentGuides?: boolean
  /** When true (default), shift+marquee adds to current selection
   * (cumulative). When false OR shift not held, marquee replaces. Per
   * Arc 4c marquee-with-shift cumulative-select canon. */
  cumulativeMarqueeOnShift?: boolean
  onSelectPlacement: (id: string, opts: { shift: boolean }) => void
  onSelectRow: (rowId: string) => void
  onDeselectAll: () => void
  /** Cross-row OR within-row placement move commit. */
  onCommitPlacementMove: (input: {
    placementId: string
    sourceRowId: string
    targetRowId: string
    newStartingColumn: number
    siblingMoves: Array<{ placementId: string; newStartingColumn: number }>
  }) => void
  /** Resize commit. Stays within source row in R-3.1. */
  onCommitPlacementResize: (input: {
    placementId: string
    rowId: string
    newStartingColumn: number
    newColumnSpan: number
  }) => void
  /** Row reorder commit. */
  onCommitRowReorder: (input: { fromIndex: number; toIndex: number }) => void
  /** Marquee commit emits placement IDs inside the rect. */
  onMarqueeSelect?: (placementIds: string[]) => void
  /** Row management. */
  onAddRowAbove: (rowIndex: number) => void
  onAddRowBelow: (rowIndex: number) => void
  onDeleteRow: (rowId: string) => void
  /** Column count picker change. */
  onChangeRowColumnCount: (rowId: string, newColumnCount: number) => void
}


function backgroundClassFor(treatment?: string): string {
  switch (treatment) {
    case "surface-base":
      return "bg-surface-base"
    case "surface-elevated":
      return "bg-surface-elevated"
    case "surface-sunken":
      return "bg-surface-sunken"
    default:
      return "bg-surface-base"
  }
}


const RESIZE_HANDLES_HORIZONTAL: ResizeHandle[] = ["e", "w"]


function resizeHandleStyle(handle: ResizeHandle): CSSProperties {
  const size = 8
  const offset = -size / 2
  const style: CSSProperties = {
    position: "absolute",
    width: size,
    height: size,
    background: "var(--accent)",
    border: "1px solid var(--surface-elevated)",
    borderRadius: 2,
    zIndex: 10,
  }
  switch (handle) {
    case "e":
      Object.assign(style, {
        top: "50%",
        right: offset,
        transform: "translateY(-50%)",
        cursor: "ew-resize",
      })
      break
    case "w":
      Object.assign(style, {
        top: "50%",
        left: offset,
        transform: "translateY(-50%)",
        cursor: "ew-resize",
      })
      break
  }
  return style
}


export function InteractivePlacementCanvas({
  rows,
  gapSize,
  backgroundTreatment,
  selection,
  showGrid = true,
  interactionsEnabled = true,
  showAlignmentGuides = true,
  cumulativeMarqueeOnShift: _cumulativeMarqueeOnShift = true,
  onSelectPlacement,
  onSelectRow,
  onDeselectAll,
  onCommitPlacementMove,
  onCommitPlacementResize,
  onCommitRowReorder,
  onMarqueeSelect,
  onAddRowAbove,
  onAddRowBelow,
  onDeleteRow,
  onChangeRowColumnCount,
}: InteractivePlacementCanvasProps) {
  // _cumulativeMarqueeOnShift is the per-canvas opt-out flag for marquee-
  // with-shift cumulative-select. Default true. The canvas surfaces
  // shift state via onMarqueeSelect's second arg; the consumer
  // decides REPLACE vs ADD-TO based on shift. Prefixed `_` because
  // the flag itself isn't consumed inside the canvas — it's a
  // contract signaling intent to upstream test fixtures + future
  // canvas variants (e.g., touch-screen consumers may want false).
  void _cumulativeMarqueeOnShift
  const canvasRef = useRef<HTMLDivElement | null>(null)
  const rowElsRef = useRef<Map<string, HTMLElement>>(new Map())

  const getRowElement = useMemo(
    () => (rowId: string) => rowElsRef.current.get(rowId) ?? null,
    [],
  )

  // Selected placement ids — flat set used by the hook for multi-drag.
  const selectedPlacementIds = useMemo(() => {
    return selection.placementIds ?? new Set<string>()
  }, [selection])

  // Placement DOM refs — used for alignment-guide computation during
  // drag. Each placement registers itself at mount via the
  // `data-testid="interactive-placement-{id}"` attribute reachable
  // via `querySelector` in alignment guide resolution. We avoid a
  // parallel Map ref because the existing data-testid lookup gives
  // us O(N) walk per gesture tick — bounded ~4-8 placements per row
  // in realistic compositions.
  const getPlacementRectFromDOM = (placementId: string): CanvasRect | null => {
    const canvas = canvasRef.current
    if (!canvas) return null
    const el = canvas.querySelector<HTMLElement>(
      `[data-testid="interactive-placement-${placementId}"]`,
    )
    if (!el) return null
    const r = el.getBoundingClientRect()
    const c = canvas.getBoundingClientRect()
    return {
      left: r.left - c.left + canvas.scrollLeft,
      top: r.top - c.top + canvas.scrollTop,
      width: r.width,
      height: r.height,
    }
  }

  const interactions = useCanvasInteractions({
    rows,
    selectedPlacementIds,
    getRowElement,
    gapSize,
    onCommitPlacementMove,
    onCommitPlacementResize,
    onCommitRowReorder,
    onMarqueeSelect,
    getPlacementBounds: (placementId) => {
      const allP = rows.flatMap((r) => r.placements)
      const p = allP.find((x) => x.placement_id === placementId)
      if (!p) return undefined
      const entry = getByName(p.component_kind, p.component_name)
      if (!entry) return undefined
      const meta = getCanvasMetadata(entry)
      return {
        minColumns: meta.minDimensions.columns,
        maxColumns: meta.maxDimensions?.columns,
      }
    },
  })

  // Arc 4c — alignment guides during placement drag. Computed
  // per-render; bounded by source-row placement count (~4-8). When
  // `showAlignmentGuides=false` (inspector embed) OR no active drag,
  // returns empty array → overlay null-renders.
  const alignmentGuides: AlignmentGuide[] = (() => {
    if (!showAlignmentGuides) return []
    const g = interactions.gesture
    if (g.kind !== "dragging-placement") return []
    const sourceRow = rows.find((r) => r.row_id === g.sourceRowId)
    if (!sourceRow) return []
    const startRect = getPlacementRectFromDOM(g.placementId)
    if (!startRect) return []
    // The DOM rect is the LIVE rect (already includes transform); we
    // must undo the live transform to get the start rect.
    const offset = interactions.liveOffset.get(g.placementId)
    const draggedStartRect: CanvasRect = offset
      ? {
          left: startRect.left - offset.dxPx,
          top: startRect.top - offset.dyPx,
          width: startRect.width,
          height: startRect.height,
        }
      : startRect
    const draggedRect = liveDraggedRect(
      draggedStartRect,
      offset ?? { dxPx: 0, dyPx: 0 },
    )
    const rowEl = rowElsRef.current.get(sourceRow.row_id)
    const rowRect: CanvasRect | null = rowEl
      ? (() => {
          const r = rowEl.getBoundingClientRect()
          const c = canvasRef.current?.getBoundingClientRect()
          if (!c) return null
          return {
            left: r.left - c.left + (canvasRef.current?.scrollLeft ?? 0),
            top: r.top - c.top + (canvasRef.current?.scrollTop ?? 0),
            width: r.width,
            height: r.height,
          }
        })()
      : null
    const refs = resolveReferenceRectsForRow(
      sourceRow,
      g.placementId,
      getPlacementRectFromDOM,
      rowRect,
    )
    return computeAlignmentGuides(draggedRect, refs)
  })()

  const canvasDims = (() => {
    const c = canvasRef.current
    if (!c) return { width: 0, height: 0 }
    return {
      width: c.scrollWidth,
      height: c.scrollHeight,
    }
  })()

  return (
    <div
      ref={canvasRef}
      className={`${backgroundClassFor(backgroundTreatment)} relative h-full w-full overflow-auto`}
      data-testid="interactive-canvas"
      data-row-count={rows.length}
      data-alignment-guides={alignmentGuides.length}
      onClick={(e) => {
        if (e.target === e.currentTarget) onDeselectAll()
      }}
    >
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: `${gapSize}px`,
          padding: "1rem",
          minHeight: "100%",
        }}
        data-testid="interactive-canvas-rows-container"
        onPointerDown={(e) => {
          if (
            interactionsEnabled &&
            e.target === e.currentTarget &&
            e.button === 0
          ) {
            interactions.startMarqueeSelect(e)
            // Arc 4c cumulative-marquee canon: shift+drag preserves
            // current selection; consumer's onMarqueeSelect receives
            // (ids, shiftKey=true) and adds-to. Bare drag clears
            // selection first (REPLACE semantics).
            if (!e.shiftKey) {
              onDeselectAll()
            }
          }
        }}
      >
        {rows.length === 0 && (
          <div
            className="flex items-center justify-center py-12 text-content-subtle"
            data-testid="interactive-canvas-empty"
          >
            <span className="text-caption">
              No rows yet. Click "+ Add row" to start composing.
            </span>
          </div>
        )}

        {rows.map((row, rowIndex) => (
          <RowEditor
            key={row.row_id}
            row={row}
            rowIndex={rowIndex}
            isSelectedRow={
              selection.kind === "row" && selection.rowId === row.row_id
            }
            selectedPlacementIds={selectedPlacementIds}
            interactionsEnabled={interactionsEnabled}
            gapSize={gapSize}
            showGrid={showGrid}
            interactions={interactions}
            registerRowEl={(el) => {
              if (el) rowElsRef.current.set(row.row_id, el)
              else rowElsRef.current.delete(row.row_id)
            }}
            onSelectPlacement={onSelectPlacement}
            onSelectRow={() => onSelectRow(row.row_id)}
            onAddRowAbove={() => onAddRowAbove(rowIndex)}
            onAddRowBelow={() => onAddRowBelow(rowIndex)}
            onDeleteRow={() => onDeleteRow(row.row_id)}
            onChangeColumnCount={(n) => onChangeRowColumnCount(row.row_id, n)}
          />
        ))}

        {/* Drop preview during cross-row drag or row reorder */}
        <RowDropPreview
          preview={interactions.dropPreview}
          getRowElement={getRowElement}
          canvasElement={canvasRef.current}
          gapSize={gapSize}
        />

        {/* Marquee rectangle during drag-select. */}
        {interactions.marqueeRect && (
          <div
            data-testid="canvas-marquee"
            style={{
              position: "absolute",
              left: interactions.marqueeRect.x,
              top: interactions.marqueeRect.y,
              width: interactions.marqueeRect.w,
              height: interactions.marqueeRect.h,
              background:
                "color-mix(in oklch, var(--accent) 8%, transparent)",
              border: "1px dashed var(--accent)",
              pointerEvents: "none",
              zIndex: 100,
            }}
          />
        )}

        {/* Arc 4c — alignment guides during placement drag (standalone
            canvas only; inspector embed passes showAlignmentGuides=false). */}
        {alignmentGuides.length > 0 && (
          <AlignmentGuideOverlay
            guides={alignmentGuides}
            canvasWidth={canvasDims.width}
            canvasHeight={canvasDims.height}
          />
        )}
      </div>
    </div>
  )
}


// ─── Per-row editor ─────────────────────────────────────────────


interface RowEditorProps {
  row: CompositionRow
  rowIndex: number
  isSelectedRow: boolean
  selectedPlacementIds: Set<string>
  interactionsEnabled: boolean
  gapSize: number
  showGrid: boolean
  interactions: ReturnType<typeof useCanvasInteractions>
  registerRowEl: (el: HTMLDivElement | null) => void
  onSelectPlacement: (id: string, opts: { shift: boolean }) => void
  onSelectRow: () => void
  onAddRowAbove: () => void
  onAddRowBelow: () => void
  onDeleteRow: () => void
  onChangeColumnCount: (newColumnCount: number) => void
}


function RowEditor({
  row,
  rowIndex,
  isSelectedRow,
  selectedPlacementIds,
  interactionsEnabled,
  gapSize,
  showGrid,
  interactions,
  registerRowEl,
  onSelectPlacement,
  onSelectRow,
  onAddRowAbove,
  onAddRowBelow,
  onDeleteRow,
  onChangeColumnCount,
}: RowEditorProps) {
  const isDraggingRow =
    interactions.gesture.kind === "dragging-row" &&
    interactions.gesture.rowId === row.row_id

  const rowHeight =
    typeof row.row_height === "number" ? `${row.row_height}px` : "auto"

  const rowGridStyle: CSSProperties = {
    display: "grid",
    gridTemplateColumns: `repeat(${row.column_count}, minmax(0, 1fr))`,
    gridAutoRows: typeof row.row_height === "number" ? rowHeight : "auto",
    minHeight: typeof row.row_height === "number" ? rowHeight : "120px",
    gap: `${gapSize}px`,
    paddingLeft: "2.5rem", // 40px to leave room for RowControlsStrip
    paddingRight: "0.5rem",
    paddingTop: "0.5rem",
    paddingBottom: "0.5rem",
    position: "relative",
  }

  const editorChrome: CSSProperties = showGrid
    ? {
        backgroundImage: `linear-gradient(to right, var(--border-subtle) 1px, transparent 1px)`,
        backgroundSize: `calc((100% - ${(row.column_count - 1) * gapSize}px - 2.5rem - 0.5rem) / ${row.column_count} + ${gapSize}px) 100%`,
        backgroundPosition: `2.5rem 0`,
      }
    : {}

  const liveRowOffsetStyle: CSSProperties = isDraggingRow
    ? {
        transform: `translateY(${interactions.gesture.kind === "dragging-row" ? interactions.gesture.dy : 0}px)`,
        opacity: 0.7,
        transition: "none",
      }
    : { transition: "transform 100ms" }

  return (
    <div
      ref={registerRowEl}
      data-testid={`row-editor-${row.row_id}`}
      data-row-id={row.row_id}
      data-row-index={rowIndex}
      data-column-count={row.column_count}
      data-selected-row={isSelectedRow ? "true" : "false"}
      className={[
        "group relative rounded-md border",
        isSelectedRow
          ? "border-accent ring-1 ring-accent"
          : "border-border-subtle/50 hover:border-border-subtle",
      ].join(" ")}
      style={liveRowOffsetStyle}
    >
      <RowControlsStrip
        row={row}
        rowIndex={rowIndex}
        isSelected={isSelectedRow}
        onAddRowAbove={onAddRowAbove}
        onAddRowBelow={onAddRowBelow}
        onDeleteRow={onDeleteRow}
        onSelectRow={onSelectRow}
        onChangeColumnCount={onChangeColumnCount}
        onStartRowDrag={(e) => {
          if (!interactionsEnabled) return
          interactions.startRowDrag(row.row_id, rowIndex, e)
        }}
      />

      <div style={{ ...rowGridStyle, ...editorChrome }}>
        {row.placements.length === 0 && (
          <EmptyRowPlaceholder
            rowId={row.row_id}
            columnCount={row.column_count}
          />
        )}

        {row.placements.map((p) =>
          renderPlacement(
            p,
            row,
            rowIndex,
            selectedPlacementIds,
            interactionsEnabled,
            interactions,
            onSelectPlacement,
          ),
        )}
      </div>
    </div>
  )
}


function renderPlacement(
  p: Placement,
  row: CompositionRow,
  _rowIndex: number,
  selectedPlacementIds: Set<string>,
  interactionsEnabled: boolean,
  interactions: ReturnType<typeof useCanvasInteractions>,
  onSelectPlacement: (id: string, opts: { shift: boolean }) => void,
): ReactNode {
  const isSelected = selectedPlacementIds.has(p.placement_id)
  const offset = interactions.liveOffset.get(p.placement_id)
  const liveResize =
    interactions.liveResize?.placementId === p.placement_id
      ? interactions.liveResize.delta
      : null

  // Apply live resize via grid coord adjustment for visual feedback.
  let liveStartingColumn = p.starting_column
  let liveColumnSpan = p.column_span
  if (liveResize) {
    liveColumnSpan = Math.max(1, p.column_span + liveResize.dColSpan)
    liveStartingColumn = Math.max(
      0,
      Math.min(
        row.column_count - liveColumnSpan,
        p.starting_column + liveResize.dCol,
      ),
    )
  }

  // Arc 4c — drop-shadow lift on active drag for Figma-shape gesture
  // affordance. The dragged placement's z-index also lifts to render
  // above siblings during the gesture; box-shadow flips to shadow-
  // level-3 token for clear "I am being moved" visual feedback.
  const isDragging = !!offset
  const cellStyle: CSSProperties = {
    gridColumn: `${liveStartingColumn + 1} / span ${liveColumnSpan}`,
    zIndex:
      p.display_config?.z_index ??
      (isDragging ? 20 : isSelected ? 5 : 1),
    transform: offset
      ? `translate(${offset.dxPx}px, ${offset.dyPx}px)`
      : undefined,
    position: "relative",
    cursor: interactionsEnabled ? "move" : "default",
    transition: offset || liveResize ? "none" : "box-shadow 120ms",
    boxShadow: isDragging ? "var(--shadow-level-3)" : undefined,
    opacity: isDragging ? 0.92 : undefined,
  }
  const showBorder = p.display_config?.show_border !== false
  const baseRingClass = isSelected
    ? "ring-2 ring-accent ring-offset-2 ring-offset-surface-base"
    : showBorder
      ? "border border-border-subtle"
      : ""

  let placementContent: ReactNode = null
  try {
    placementContent = renderComponentPreview(
      `${p.component_kind}:${p.component_name}`,
      p.prop_overrides ?? {},
      p.component_name,
    )
  } catch {
    placementContent = (
      <div className="p-2 text-caption text-content-muted">
        Preview unavailable
      </div>
    )
  }

  return (
    <div
      key={p.placement_id}
      style={cellStyle}
      data-testid={`interactive-placement-${p.placement_id}`}
      data-component-kind={p.component_kind}
      data-component-name={p.component_name}
      data-selected={isSelected ? "true" : "false"}
      data-row-id={row.row_id}
      className={`overflow-hidden rounded-md bg-surface-elevated shadow-level-1 ${baseRingClass}`}
      onPointerDown={(e) => {
        // Arc 3a Q-CROSS-2: when interactionsEnabled=false (read-mostly
        // mode, e.g. inspector embed at 380px), click-to-select still
        // fires but startPlacementDrag does NOT. Standalone callers
        // pass interactionsEnabled=true (default behavior — drag +
        // select); inspector passes false (select-only).
        e.stopPropagation()
        onSelectPlacement(p.placement_id, { shift: e.shiftKey })
        if (interactionsEnabled) {
          interactions.startPlacementDrag(p.placement_id, row.row_id, e)
        }
      }}
    >
      {p.display_config?.show_header !== false && (
        <div className="flex items-center justify-between border-b border-border-subtle px-3 py-1.5 text-caption">
          <span className="font-medium text-content-strong">
            {p.component_name}
          </span>
          <span className="font-plex-mono text-content-subtle">
            {p.component_kind}
          </span>
        </div>
      )}
      <div className="h-full overflow-hidden p-2">{placementContent}</div>

      {/* Resize handles — column-axis only in R-3.1 (row-axis resize
          via right-rail row_height inspector). Single-select only. */}
      {isSelected &&
        selectedPlacementIds.size === 1 &&
        interactionsEnabled &&
        RESIZE_HANDLES_HORIZONTAL.map((h) => (
          <div
            key={h}
            style={resizeHandleStyle(h)}
            data-testid={`resize-handle-${p.placement_id}-${h}`}
            onPointerDown={(e) =>
              interactions.startResize(p.placement_id, row.row_id, h, e)
            }
          />
        ))}
    </div>
  )
}


export type { ResizeHandle, ComponentKind }

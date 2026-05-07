/**
 * Canvas interaction hook — drag/resize/row-reorder state machine
 * for the row-aware composition editor (R-3.1).
 *
 * Three gesture lineages:
 *
 *   PLACEMENT DRAG: pointer-down on a placement card → maybe-dragging-
 *     placement → dragging-placement (after 3px threshold). Live drop
 *     preview tracks (a) which row the pointer is in (per-row DOM hit-
 *     test) and (b) which column within that row's per-row column_count.
 *     Stays in source row visually until commit (Apple Freeform model).
 *     On pointer-up: emits onCommitPlacementMove with source + target
 *     row + new starting_column.
 *
 *   PLACEMENT RESIZE: pointer-down on a resize handle → maybe-resizing
 *     → resizing. Resize stays WITHIN the source row in R-3.1 (resize
 *     doesn't move placements across rows; that's drag's job). Cross-
 *     row resize deferred to R-3.2 polish.
 *
 *   ROW REORDER: pointer-down on a row's grip handle → maybe-dragging-
 *     row → dragging-row. Live insertion-line preview tracks the gap
 *     between rows where the dragged row would land. On pointer-up:
 *     emits onCommitRowReorder with fromIndex + toIndex.
 *
 * Hit-testing is DOM-driven (NOT math-only): the canvas hands the hook
 * a `getRowElement(rowId): HTMLElement | null` resolver. Per-row
 * cellWidth derives from `rect.width - padding - (col-1)*gap) / col`
 * at gesture time. This keeps the hook agnostic to layout details
 * (the canvas decides per-row column_count + render shape).
 *
 * Multi-placement drag (R-3.1 constraint): when the dragged placement
 * is in selectedPlacementIds AND all selected are in the same row,
 * the whole set moves together within that row. Cross-row drag with
 * multi-select moves only the dragged placement; other selected
 * placements stay put. Cross-row multi-drag deferred to R-3.2 polish.
 */
import { useCallback, useEffect, useRef, useState } from "react"
import type {
  CompositionRow,
  Placement,
} from "@/lib/visual-editor/compositions/types"


// ─── Gesture state machine ──────────────────────────────────────


export type ResizeHandle =
  | "n"
  | "e"
  | "s"
  | "w"
  | "ne"
  | "nw"
  | "se"
  | "sw"


export type CanvasGesture =
  | { kind: "idle" }
  | {
      kind: "maybe-dragging-placement"
      placementId: string
      sourceRowId: string
      pointerId: number
      startX: number
      startY: number
    }
  | {
      kind: "dragging-placement"
      placementId: string
      sourceRowId: string
      pointerId: number
      startX: number
      startY: number
      dx: number
      dy: number
    }
  | {
      kind: "maybe-resizing"
      placementId: string
      sourceRowId: string
      pointerId: number
      startX: number
      startY: number
      handle: ResizeHandle
    }
  | {
      kind: "resizing"
      placementId: string
      sourceRowId: string
      pointerId: number
      startX: number
      startY: number
      dx: number
      dy: number
      handle: ResizeHandle
    }
  | {
      kind: "maybe-dragging-row"
      rowId: string
      sourceIndex: number
      pointerId: number
      startX: number
      startY: number
    }
  | {
      kind: "dragging-row"
      rowId: string
      sourceIndex: number
      pointerId: number
      startX: number
      startY: number
      dx: number
      dy: number
    }


/** Drop preview state — surfaced separately so the canvas can render
 * the inserted-line affordance without re-deriving from gesture state.
 */
export type DropPreview =
  | null
  | {
      kind: "placement-into-row"
      targetRowId: string
      /** 0-indexed target column in the target row. */
      targetStartingColumn: number
    }
  | {
      kind: "row-insert"
      /** Insertion index in rows[] (0 = above first; rows.length = below last). */
      insertIndex: number
    }


const DRAG_THRESHOLD_PX = 3
const CANVAS_PADDING_PX = 16 // 1rem padding on each side of grid


// ─── Pure helpers (test-friendly) ───────────────────────────────


function snapPxToCells(px: number, cellSize: number): number {
  if (cellSize <= 0) return 0
  return Math.round(px / cellSize)
}


/** Per-row cell width in px from the row's DOM width + column_count + gap.
 * `rect.width` is the row container's clientWidth; row's inner grid
 * uses 12 cells with `gap_size` between them. The padding-on-each-side
 * is the canvas-level CANVAS_PADDING_PX value (NOT a per-row padding —
 * each row has its own minor padding which we account for separately).
 */
export function cellWidthFor(
  rowWidthPx: number,
  columnCount: number,
  gapPx: number,
): number {
  if (columnCount < 1) return 0
  const usable = rowWidthPx - gapPx * (columnCount - 1)
  return Math.max(0, usable / columnCount)
}


/** Given a pointer X position relative to a row's left edge + the row's
 * column_count + gap_size + total row width, return the 0-indexed
 * column index the pointer is over. Clamps to [0, columnCount - 1].
 */
export function pointerToColumnIndex(
  offsetXInRow: number,
  rowWidthPx: number,
  columnCount: number,
  gapPx: number,
): number {
  const cellW = cellWidthFor(rowWidthPx, columnCount, gapPx)
  if (cellW <= 0) return 0
  const stride = cellW + gapPx
  const idx = Math.floor(offsetXInRow / stride)
  return Math.max(0, Math.min(columnCount - 1, idx))
}


/** Validate whether a row's column_count change would clip placements.
 *
 * Returns `{ ok: true }` if every placement fits within the proposed
 * column_count (starting_column + column_span <= newColumnCount).
 * Returns `{ ok: false, blockingCount }` otherwise.
 *
 * Used by the column count picker to disable values that would
 * otherwise auto-clip placements (R-3.1 hostile-UX guard).
 */
export function validateColumnCountChange(
  row: CompositionRow,
  newColumnCount: number,
): { ok: true } | { ok: false; blockingCount: number } {
  let blocking = 0
  for (const p of row.placements) {
    if (p.starting_column + p.column_span > newColumnCount) blocking += 1
  }
  if (blocking === 0) return { ok: true }
  return { ok: false, blockingCount: blocking }
}


/** Determine the row insertion-index for a row reorder gesture.
 *
 * Given a pointer Y position + per-row DOM rects, return the index in
 * rows[] where the dragged row would insert (0 = above all, len = below all).
 * The midline of each row is the threshold: if pointer is in row R's
 * top half, insertion is at R; bottom half, insertion is at R+1.
 */
export function pointerToInsertIndex(
  clientY: number,
  rowRects: Array<{ rowId: string; top: number; bottom: number }>,
): number {
  if (rowRects.length === 0) return 0
  if (clientY < rowRects[0].top) return 0
  for (let i = 0; i < rowRects.length; i++) {
    const r = rowRects[i]
    if (clientY >= r.top && clientY <= r.bottom) {
      const mid = (r.top + r.bottom) / 2
      return clientY < mid ? i : i + 1
    }
  }
  return rowRects.length
}


/** Compute resize delta for the canonical 8 handles. Resize stays
 * within source row in R-3.1; only the column axis can change column
 * starting + column_span. The row axis is content-driven via row_height
 * — resize handles n/s adjust starting_column only when row_height is
 * "auto" (default), which is the R-3.1 baseline.
 *
 * For R-3.1 we keep the column-axis-only behavior: handles e/w grow/
 * shrink column_span; ne/nw/se/sw adjust column_start + span. Vertical
 * handles (n/s) and corner handles (ne/se etc) are no-ops on row_height
 * unless explicitly wired — deferred. Functionally R-3.1 supports
 * column-axis resize, which is the canonical "make this widget wider"
 * operation. Row-height adjust via right-rail inspector.
 */
function resizeDeltaFromPx(
  handle: ResizeHandle,
  dxPx: number,
  cellWidth: number,
): { dCol: number; dColSpan: number } {
  const dCol = snapPxToCells(dxPx, cellWidth)
  const out = { dCol: 0, dColSpan: 0 }
  if (handle === "w" || handle === "nw" || handle === "sw") {
    out.dCol = dCol
    out.dColSpan = -dCol
  }
  if (handle === "e" || handle === "ne" || handle === "se") {
    out.dColSpan = dCol
  }
  return out
}


// ─── Hook options + return shape ────────────────────────────────


export interface UseCanvasInteractionsOptions {
  rows: CompositionRow[]
  /** Set of currently-selected placement ids (multi-select drag uses
   * this). Row selection is tracked separately by the parent. */
  selectedPlacementIds: Set<string>
  /** DOM resolver: returns the row's container element OR null. The
   * hook calls getBoundingClientRect on the element at gesture time. */
  getRowElement: (rowId: string) => HTMLElement | null
  /** Row-gap in px (canvas_config.gap_size). Used for column-stride
   * math in hit-testing. */
  gapSize: number
  /** Called on cross-row OR within-row placement drag commit. */
  onCommitPlacementMove: (input: {
    placementId: string
    sourceRowId: string
    targetRowId: string
    newStartingColumn: number
    /** When dragged-anchor is in a multi-select within the SAME
     * source row, also-moved sibling ids. Empty array if no
     * sibling movement. R-3.1 constraint: cross-row drag never
     * moves siblings. */
    siblingMoves: Array<{
      placementId: string
      newStartingColumn: number
    }>
  }) => void
  /** Called on resize commit. Stays within source row in R-3.1. */
  onCommitPlacementResize: (input: {
    placementId: string
    rowId: string
    newStartingColumn: number
    newColumnSpan: number
  }) => void
  /** Called on row-reorder commit. */
  onCommitRowReorder: (input: { fromIndex: number; toIndex: number }) => void
  /** Marquee select commit. */
  onMarqueeSelect?: (placementIds: string[]) => void
  /** Per-placement min/max column-span bounds for resize clamping. */
  getPlacementBounds?: (placementId: string) =>
    | { minColumns?: number; maxColumns?: number }
    | undefined
}


export interface CanvasInteractions {
  gesture: CanvasGesture
  dropPreview: DropPreview
  /** Per-placement-id px offset for live drag transform. */
  liveOffset: Map<string, { dxPx: number; dyPx: number }>
  /** Live row drag offset (the row being reordered). */
  liveRowOffset: { rowId: string; dyPx: number } | null
  /** Live resize delta during a resize gesture. Null otherwise. */
  liveResize: {
    placementId: string
    rowId: string
    delta: { dCol: number; dColSpan: number }
  } | null
  startPlacementDrag: (
    placementId: string,
    sourceRowId: string,
    e: React.PointerEvent,
  ) => void
  startResize: (
    placementId: string,
    sourceRowId: string,
    handle: ResizeHandle,
    e: React.PointerEvent,
  ) => void
  startRowDrag: (
    rowId: string,
    sourceIndex: number,
    e: React.PointerEvent,
  ) => void
  startMarqueeSelect: (e: React.PointerEvent) => void
  marqueeRect: { x: number; y: number; w: number; h: number } | null
}


// ─── Hook implementation ───────────────────────────────────────


export function useCanvasInteractions({
  rows,
  selectedPlacementIds,
  getRowElement,
  gapSize,
  onCommitPlacementMove,
  onCommitPlacementResize,
  onCommitRowReorder,
  onMarqueeSelect,
  getPlacementBounds,
}: UseCanvasInteractionsOptions): CanvasInteractions {
  const [gesture, setGesture] = useState<CanvasGesture>({ kind: "idle" })
  const [dropPreview, setDropPreview] = useState<DropPreview>(null)
  const [marqueeRect, setMarqueeRect] = useState<
    { x: number; y: number; w: number; h: number } | null
  >(null)
  const marqueeStartRef = useRef<{ x: number; y: number } | null>(null)

  // Refs to avoid stale closures in the window-level handlers.
  const rowsRef = useRef(rows)
  rowsRef.current = rows
  const selectedRef = useRef(selectedPlacementIds)
  selectedRef.current = selectedPlacementIds
  const getRowElementRef = useRef(getRowElement)
  getRowElementRef.current = getRowElement
  const gapRef = useRef(gapSize)
  gapRef.current = gapSize

  // ── Gesture starters ─────────────────────────────────────────

  const startPlacementDrag = useCallback(
    (placementId: string, sourceRowId: string, e: React.PointerEvent) => {
      if (e.button !== 0) return
      ;(e.target as Element).setPointerCapture?.(e.pointerId)
      setGesture({
        kind: "maybe-dragging-placement",
        placementId,
        sourceRowId,
        pointerId: e.pointerId,
        startX: e.clientX,
        startY: e.clientY,
      })
    },
    [],
  )

  const startResize = useCallback(
    (
      placementId: string,
      sourceRowId: string,
      handle: ResizeHandle,
      e: React.PointerEvent,
    ) => {
      if (e.button !== 0) return
      e.stopPropagation()
      ;(e.target as Element).setPointerCapture?.(e.pointerId)
      setGesture({
        kind: "maybe-resizing",
        placementId,
        sourceRowId,
        pointerId: e.pointerId,
        startX: e.clientX,
        startY: e.clientY,
        handle,
      })
    },
    [],
  )

  const startRowDrag = useCallback(
    (rowId: string, sourceIndex: number, e: React.PointerEvent) => {
      if (e.button !== 0) return
      e.stopPropagation()
      ;(e.target as Element).setPointerCapture?.(e.pointerId)
      setGesture({
        kind: "maybe-dragging-row",
        rowId,
        sourceIndex,
        pointerId: e.pointerId,
        startX: e.clientX,
        startY: e.clientY,
      })
    },
    [],
  )

  const startMarqueeSelect = useCallback((e: React.PointerEvent) => {
    if (e.button !== 0) return
    const target = e.currentTarget as HTMLElement
    const rect = target.getBoundingClientRect()
    const x = e.clientX - rect.left
    const y = e.clientY - rect.top
    marqueeStartRef.current = { x, y }
    setMarqueeRect({ x, y, w: 0, h: 0 })
  }, [])

  // ── Window-level pointer move + up handlers ─────────────────

  useEffect(() => {
    function hitTestForPlacementDrop(
      clientX: number,
      clientY: number,
    ): DropPreview {
      const currentRows = rowsRef.current
      const getEl = getRowElementRef.current
      const gap = gapRef.current
      for (const row of currentRows) {
        const el = getEl(row.row_id)
        if (!el) continue
        const rect = el.getBoundingClientRect()
        if (
          clientX >= rect.left &&
          clientX <= rect.right &&
          clientY >= rect.top &&
          clientY <= rect.bottom
        ) {
          // Subtract row's left padding (matches `padding: 0 1rem` in
          // canvas grid). Falls back gracefully when padding is 0.
          const offsetX = Math.max(0, clientX - rect.left - 0)
          const innerWidth = rect.width
          const colIndex = pointerToColumnIndex(
            offsetX,
            innerWidth,
            row.column_count,
            gap,
          )
          return {
            kind: "placement-into-row",
            targetRowId: row.row_id,
            targetStartingColumn: colIndex,
          }
        }
      }
      return null
    }

    function hitTestForRowInsert(clientY: number): DropPreview {
      const currentRows = rowsRef.current
      const getEl = getRowElementRef.current
      const rects: Array<{ rowId: string; top: number; bottom: number }> = []
      for (const row of currentRows) {
        const el = getEl(row.row_id)
        if (!el) continue
        const r = el.getBoundingClientRect()
        rects.push({ rowId: row.row_id, top: r.top, bottom: r.bottom })
      }
      const idx = pointerToInsertIndex(clientY, rects)
      return { kind: "row-insert", insertIndex: idx }
    }

    function onMove(e: PointerEvent) {
      const g = gesture

      // Marquee select
      if (marqueeStartRef.current) {
        const start = marqueeStartRef.current
        const w = e.clientX - start.x
        const h = e.clientY - start.y
        setMarqueeRect({
          x: w < 0 ? start.x + w : start.x,
          y: h < 0 ? start.y + h : start.y,
          w: Math.abs(w),
          h: Math.abs(h),
        })
        return
      }

      if (g.kind === "maybe-dragging-placement") {
        const dx = e.clientX - g.startX
        const dy = e.clientY - g.startY
        if (Math.hypot(dx, dy) >= DRAG_THRESHOLD_PX) {
          setGesture({
            kind: "dragging-placement",
            placementId: g.placementId,
            sourceRowId: g.sourceRowId,
            pointerId: g.pointerId,
            startX: g.startX,
            startY: g.startY,
            dx,
            dy,
          })
          setDropPreview(hitTestForPlacementDrop(e.clientX, e.clientY))
        }
        return
      }
      if (g.kind === "dragging-placement") {
        setGesture({
          ...g,
          dx: e.clientX - g.startX,
          dy: e.clientY - g.startY,
        })
        setDropPreview(hitTestForPlacementDrop(e.clientX, e.clientY))
        return
      }

      if (g.kind === "maybe-resizing") {
        const dx = e.clientX - g.startX
        const dy = e.clientY - g.startY
        if (Math.hypot(dx, dy) >= DRAG_THRESHOLD_PX) {
          setGesture({
            kind: "resizing",
            placementId: g.placementId,
            sourceRowId: g.sourceRowId,
            pointerId: g.pointerId,
            startX: g.startX,
            startY: g.startY,
            dx,
            dy,
            handle: g.handle,
          })
        }
        return
      }
      if (g.kind === "resizing") {
        setGesture({
          ...g,
          dx: e.clientX - g.startX,
          dy: e.clientY - g.startY,
        })
        return
      }

      if (g.kind === "maybe-dragging-row") {
        const dx = e.clientX - g.startX
        const dy = e.clientY - g.startY
        if (Math.hypot(dx, dy) >= DRAG_THRESHOLD_PX) {
          setGesture({
            kind: "dragging-row",
            rowId: g.rowId,
            sourceIndex: g.sourceIndex,
            pointerId: g.pointerId,
            startX: g.startX,
            startY: g.startY,
            dx,
            dy,
          })
          setDropPreview(hitTestForRowInsert(e.clientY))
        }
        return
      }
      if (g.kind === "dragging-row") {
        setGesture({
          ...g,
          dx: e.clientX - g.startX,
          dy: e.clientY - g.startY,
        })
        setDropPreview(hitTestForRowInsert(e.clientY))
        return
      }
    }

    function onUp() {
      // Marquee commit
      if (marqueeStartRef.current && marqueeRect) {
        if (onMarqueeSelect && marqueeRect.w > 4 && marqueeRect.h > 4) {
          // Hit-test placements via DOM rects against the marquee rect.
          // Simpler than recomputing grid coords; we walk every row's
          // children and check intersection.
          const inside: string[] = []
          const m = marqueeRect
          for (const row of rowsRef.current) {
            const el = getRowElementRef.current(row.row_id)
            if (!el) continue
            const rowRect = el.getBoundingClientRect()
            // marqueeRect coords are canvas-relative; we don't have
            // the canvas ref here, so approximate via clientRects.
            // For R-3.1, marquee select is best-effort within rows
            // — placements whose row is intersected by the marquee
            // are candidates; refine by per-placement DOM rect.
            for (const p of row.placements) {
              const placementEl = el.querySelector(
                `[data-testid="interactive-placement-${p.placement_id}"]`,
              )
              if (!placementEl) continue
              const pRect = (placementEl as HTMLElement).getBoundingClientRect()
              // Convert pRect to canvas-relative — we approximate by
              // not subtracting canvas offset (marquee was canvas-
              // relative based on its currentTarget). Correctness
              // comes from the canvas passing canvas-relative
              // coordinates to the marquee start ref.
              void rowRect
              const topCanvasRel = pRect.top
              const bottomCanvasRel = pRect.bottom
              const leftCanvasRel = pRect.left
              const rightCanvasRel = pRect.right
              if (
                !(
                  rightCanvasRel < m.x ||
                  m.x + m.w < leftCanvasRel ||
                  bottomCanvasRel < m.y ||
                  m.y + m.h < topCanvasRel
                )
              ) {
                inside.push(p.placement_id)
              }
            }
          }
          onMarqueeSelect(inside)
        }
        marqueeStartRef.current = null
        setMarqueeRect(null)
        return
      }

      const g = gesture

      if (g.kind === "dragging-placement") {
        // Commit drop. Determine target row + target column.
        const target = dropPreview
        if (target && target.kind === "placement-into-row") {
          const sourceRow = rowsRef.current.find(
            (r) => r.row_id === g.sourceRowId,
          )
          const draggedPlacement = sourceRow?.placements.find(
            (p) => p.placement_id === g.placementId,
          )
          // Clamp newStartingColumn so target row's column_count holds.
          let newStartingColumn = target.targetStartingColumn
          const targetRow = rowsRef.current.find(
            (r) => r.row_id === target.targetRowId,
          )
          if (targetRow && draggedPlacement) {
            const span = draggedPlacement.column_span
            newStartingColumn = Math.max(
              0,
              Math.min(targetRow.column_count - span, newStartingColumn),
            )
            if (newStartingColumn < 0) newStartingColumn = 0
          }

          // Sibling moves (multi-select within same source row only).
          const siblingMoves: Array<{
            placementId: string
            newStartingColumn: number
          }> = []
          if (
            target.targetRowId === g.sourceRowId &&
            sourceRow &&
            draggedPlacement
          ) {
            const dragDelta =
              newStartingColumn - draggedPlacement.starting_column
            if (dragDelta !== 0) {
              for (const id of selectedRef.current) {
                if (id === g.placementId) continue
                const sib = sourceRow.placements.find(
                  (p) => p.placement_id === id,
                )
                if (!sib) continue
                let sibNewStart = sib.starting_column + dragDelta
                sibNewStart = Math.max(
                  0,
                  Math.min(
                    sourceRow.column_count - sib.column_span,
                    sibNewStart,
                  ),
                )
                if (sibNewStart !== sib.starting_column) {
                  siblingMoves.push({
                    placementId: id,
                    newStartingColumn: sibNewStart,
                  })
                }
              }
            }
          }

          onCommitPlacementMove({
            placementId: g.placementId,
            sourceRowId: g.sourceRowId,
            targetRowId: target.targetRowId,
            newStartingColumn,
            siblingMoves,
          })
        }
      } else if (g.kind === "resizing") {
        const sourceRow = rowsRef.current.find(
          (r) => r.row_id === g.sourceRowId,
        )
        const p = sourceRow?.placements.find(
          (x) => x.placement_id === g.placementId,
        )
        if (sourceRow && p) {
          const el = getRowElementRef.current(g.sourceRowId)
          const rowWidthPx = el ? el.getBoundingClientRect().width : 0
          const cellW = cellWidthFor(
            rowWidthPx,
            sourceRow.column_count,
            gapRef.current,
          )
          const delta = resizeDeltaFromPx(g.handle, g.dx, cellW)
          if (delta.dCol !== 0 || delta.dColSpan !== 0) {
            const bounds = getPlacementBounds?.(g.placementId)
            const minCols = bounds?.minColumns ?? 1
            const maxCols = bounds?.maxColumns ?? sourceRow.column_count

            let newColSpan = p.column_span + delta.dColSpan
            let newColStart = p.starting_column + delta.dCol

            newColSpan = Math.max(minCols, Math.min(maxCols, newColSpan))
            newColStart = Math.max(
              0,
              Math.min(sourceRow.column_count - newColSpan, newColStart),
            )

            if (
              newColStart !== p.starting_column ||
              newColSpan !== p.column_span
            ) {
              onCommitPlacementResize({
                placementId: g.placementId,
                rowId: g.sourceRowId,
                newStartingColumn: newColStart,
                newColumnSpan: newColSpan,
              })
            }
          }
        }
      } else if (g.kind === "dragging-row") {
        const target = dropPreview
        if (target && target.kind === "row-insert") {
          // Reorder commits when source ≠ target & target ≠ source+1
          // (no-op when dropping at same position).
          if (
            target.insertIndex !== g.sourceIndex &&
            target.insertIndex !== g.sourceIndex + 1
          ) {
            // After splice from sourceIndex, insertion index shifts
            // down by 1 if target > sourceIndex.
            const adjustedTarget =
              target.insertIndex > g.sourceIndex
                ? target.insertIndex - 1
                : target.insertIndex
            onCommitRowReorder({
              fromIndex: g.sourceIndex,
              toIndex: adjustedTarget,
            })
          }
        }
      }

      setGesture({ kind: "idle" })
      setDropPreview(null)
    }

    window.addEventListener("pointermove", onMove)
    window.addEventListener("pointerup", onUp)
    window.addEventListener("pointercancel", onUp)
    return () => {
      window.removeEventListener("pointermove", onMove)
      window.removeEventListener("pointerup", onUp)
      window.removeEventListener("pointercancel", onUp)
    }
  }, [
    gesture,
    dropPreview,
    marqueeRect,
    onCommitPlacementMove,
    onCommitPlacementResize,
    onCommitRowReorder,
    onMarqueeSelect,
    getPlacementBounds,
  ])

  // ── Live offsets for visual feedback during drag ─────────────

  const liveOffset = new Map<string, { dxPx: number; dyPx: number }>()
  if (gesture.kind === "dragging-placement") {
    // Single-placement drag transform (cross-row case): only the
    // dragged placement gets the offset. R-3.1 constraint: cross-row
    // multi-drag deferred to R-3.2 polish.
    liveOffset.set(gesture.placementId, {
      dxPx: gesture.dx,
      dyPx: gesture.dy,
    })
    // Within-row multi-select: also offset siblings if drop preview
    // says the target IS the source row.
    if (
      dropPreview?.kind === "placement-into-row" &&
      dropPreview.targetRowId === gesture.sourceRowId
    ) {
      for (const id of selectedRef.current) {
        if (id === gesture.placementId) continue
        liveOffset.set(id, { dxPx: gesture.dx, dyPx: gesture.dy })
      }
    }
  }

  const liveRowOffset =
    gesture.kind === "dragging-row"
      ? { rowId: gesture.rowId, dyPx: gesture.dy }
      : null

  let liveResize: CanvasInteractions["liveResize"] = null
  if (gesture.kind === "resizing") {
    const el = getRowElementRef.current(gesture.sourceRowId)
    const sourceRow = rows.find((r) => r.row_id === gesture.sourceRowId)
    if (el && sourceRow) {
      const cellW = cellWidthFor(
        el.getBoundingClientRect().width,
        sourceRow.column_count,
        gapSize,
      )
      liveResize = {
        placementId: gesture.placementId,
        rowId: gesture.sourceRowId,
        delta: resizeDeltaFromPx(gesture.handle, gesture.dx, cellW),
      }
    }
  }

  return {
    gesture,
    dropPreview,
    liveOffset,
    liveRowOffset,
    liveResize,
    startPlacementDrag,
    startResize,
    startRowDrag,
    startMarqueeSelect,
    marqueeRect,
  }
}


// ─── Test internals (exposed for unit tests) ─────────────────────


export const _internals = {
  snapPxToCells,
  cellWidthFor,
  pointerToColumnIndex,
  pointerToInsertIndex,
  validateColumnCountChange,
  resizeDeltaFromPx,
  DRAG_THRESHOLD_PX,
  CANVAS_PADDING_PX,
}


// Used by the legacy Placement type assertion in old tests; not exported
// elsewhere. R-3.1 uses canonical Placement from compositions/types.
export type { Placement }

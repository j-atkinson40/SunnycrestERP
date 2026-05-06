/**
 * InteractivePlacementCanvas — composition editor canvas with drag,
 * resize, click/shift-click multi-select.
 *
 * Distinct from `CompositionRenderer` (which is the runtime renderer
 * + non-interactive editor preview): this component adds the
 * interaction layer the composition editor needs while reusing the
 * same grid math + token-based styling.
 *
 * Renders:
 *   - A 12-column CSS grid with subtle dotted background showing
 *     cell boundaries (toggleable via showGrid)
 *   - Each placement positioned at its declared grid coords
 *   - Placements draggable: click + drag to move (grid snap)
 *   - Selected placement(s) show resize handles at corners + edges
 *   - Click placement → select (single); shift-click → toggle in
 *     multi-select
 *   - Click background → deselect all
 *   - Empty canvas state when placements list is empty
 *
 * Performance: drag updates use CSS `transform` on the dragged
 * elements (cheap, GPU-accelerated). The actual grid coord update
 * commits on pointer-up via the parent's onPlacementsChange.
 */
import { useMemo, useRef, type CSSProperties, type ReactNode } from "react"
import { renderComponentPreview } from "@/lib/visual-editor/components/preview-renderers"
import {
  getCanvasMetadata,
  getByName,
  type ComponentKind,
} from "@/lib/visual-editor/registry"
import type { Placement } from "@/lib/visual-editor/compositions/types"
import {
  useCanvasInteractions,
  type ResizeHandle,
} from "./use-canvas-interactions"


export interface InteractivePlacementCanvasProps {
  placements: Placement[]
  totalColumns: number
  rowHeight: number
  gapSize: number
  backgroundTreatment?: string
  selectedIds: Set<string>
  showGrid?: boolean
  /** When false, drag/resize don't apply (e.g., during a save in
   * progress). */
  interactionsEnabled?: boolean
  onSelect: (id: string, opts: { shift: boolean }) => void
  onDeselectAll: () => void
  onPlacementsChange: (next: Placement[]) => void
  /** Called when one or more placements get bulk-moved by the
   * interactions layer. The parent integrates with undo history. */
  onCommitDrag?: (
    updates: Array<{ placementId: string; newGrid: Placement["grid"] }>,
  ) => void
  onCommitResize?: (placementId: string, newGrid: Placement["grid"]) => void
  /** Called by marquee selection commit. */
  onMarqueeSelect?: (ids: string[], opts: { shift: boolean }) => void
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


const RESIZE_HANDLES: ResizeHandle[] = ["n", "e", "s", "w", "ne", "nw", "se", "sw"]


function handleStyle(handle: ResizeHandle): CSSProperties {
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
    case "n":
      Object.assign(style, { top: offset, left: "50%", transform: "translateX(-50%)", cursor: "ns-resize" })
      break
    case "s":
      Object.assign(style, { bottom: offset, left: "50%", transform: "translateX(-50%)", cursor: "ns-resize" })
      break
    case "e":
      Object.assign(style, { top: "50%", right: offset, transform: "translateY(-50%)", cursor: "ew-resize" })
      break
    case "w":
      Object.assign(style, { top: "50%", left: offset, transform: "translateY(-50%)", cursor: "ew-resize" })
      break
    case "ne":
      Object.assign(style, { top: offset, right: offset, cursor: "nesw-resize" })
      break
    case "nw":
      Object.assign(style, { top: offset, left: offset, cursor: "nwse-resize" })
      break
    case "se":
      Object.assign(style, { bottom: offset, right: offset, cursor: "nwse-resize" })
      break
    case "sw":
      Object.assign(style, { bottom: offset, left: offset, cursor: "nesw-resize" })
      break
  }
  return style
}


export function InteractivePlacementCanvas({
  placements,
  totalColumns,
  rowHeight,
  gapSize,
  backgroundTreatment,
  selectedIds,
  showGrid = true,
  interactionsEnabled = true,
  onSelect,
  onDeselectAll,
  onPlacementsChange,
  onCommitDrag,
  onCommitResize,
  onMarqueeSelect,
}: InteractivePlacementCanvasProps) {
  const canvasRef = useRef<HTMLDivElement | null>(null)

  // Cell-size measurement: we measure the rendered grid container and
  // derive cell width from the canvas's actual width. This guarantees
  // grid snap is accurate at the rendered scale.
  const [cellDims, setCellDims] = useMemo<
    [{ cellWidth: number; cellHeight: number }, never]
  >(() => {
    // We compute on-the-fly inside a callback to avoid a re-render
    // loop. Real measurement happens via canvasRef in the layout
    // commit phase below.
    return [{ cellWidth: 0, cellHeight: rowHeight }, undefined as never]
  }, [rowHeight])
  void setCellDims // type-pleaser; we use a ref-based approach

  // We'll compute cellWidth from the canvas's clientWidth at
  // interaction time. For TypeScript we ignore the unused setter.
  const cellWidth =
    canvasRef.current && totalColumns > 0
      ? (canvasRef.current.clientWidth -
          gapSize * (totalColumns - 1) -
          32) /
        totalColumns
      : Math.max(60, cellDims.cellWidth)
  const cellHeight = rowHeight

  const interactions = useCanvasInteractions({
    placements,
    selectedIds,
    cellWidth,
    cellHeight,
    totalColumns,
    onDragCommit: (updates) => {
      // Apply updates to placements + emit to parent.
      const next = placements.map((p) => {
        const u = updates.find((x) => x.placementId === p.placement_id)
        return u ? { ...p, grid: u.newGrid } : p
      })
      onPlacementsChange(next)
      onCommitDrag?.(updates)
    },
    onResizeCommit: (placementId, newGrid) => {
      const next = placements.map((p) =>
        p.placement_id === placementId ? { ...p, grid: newGrid } : p,
      )
      onPlacementsChange(next)
      onCommitResize?.(placementId, newGrid)
    },
    getBounds: (placementId) => {
      const p = placements.find((x) => x.placement_id === placementId)
      if (!p) return undefined
      const entry = getByName(p.component_kind, p.component_name)
      if (!entry) return undefined
      const meta = getCanvasMetadata(entry)
      return {
        minColumns: meta.minDimensions.columns,
        minRows: meta.minDimensions.rows,
        maxColumns: meta.maxDimensions?.columns,
        maxRows: meta.maxDimensions?.rows,
      }
    },
    onDragSelect: (ids) => {
      onMarqueeSelect?.(ids, { shift: false })
    },
  })

  const gridStyle: CSSProperties = {
    display: "grid",
    gridTemplateColumns: `repeat(${totalColumns}, minmax(0, 1fr))`,
    gridAutoRows: `${rowHeight}px`,
    gap: `${gapSize}px`,
    padding: "1rem",
    minHeight: "100%",
    position: "relative",
  }

  const editorChrome: CSSProperties = showGrid
    ? {
        backgroundImage: `linear-gradient(to right, var(--border-subtle) 1px, transparent 1px), linear-gradient(to bottom, var(--border-subtle) 1px, transparent 1px)`,
        backgroundSize: `calc((100% - ${(totalColumns - 1) * gapSize}px - 2rem) / ${totalColumns} + ${gapSize}px) ${rowHeight + gapSize}px`,
        backgroundPosition: `1rem 1rem`,
      }
    : {}

  return (
    <div
      ref={canvasRef}
      className={`${backgroundClassFor(backgroundTreatment)} h-full w-full overflow-auto`}
      data-testid="interactive-canvas"
      onClick={(e) => {
        // Clicking the canvas (not a placement) deselects all.
        if (e.target === e.currentTarget) {
          onDeselectAll()
        }
      }}
    >
      <div
        style={{ ...gridStyle, ...editorChrome }}
        data-testid="interactive-canvas-grid"
        onPointerDown={(e) => {
          // Marquee select: pointer-down on the grid background.
          if (
            interactionsEnabled &&
            e.target === e.currentTarget &&
            e.button === 0
          ) {
            interactions.startMarqueeSelect(e)
            onDeselectAll()
          }
        }}
      >
        {placements.length === 0 && (
          <div
            className="col-span-full flex items-center justify-center py-8 text-content-subtle"
            data-testid="interactive-canvas-empty"
          >
            <span className="text-caption">
              Drag a component from the palette to start composing.
            </span>
          </div>
        )}

        {placements.map((p) => {
          const isSelected = selectedIds.has(p.placement_id)
          const offset = interactions.liveOffset.get(p.placement_id)
          const liveResize =
            interactions.liveResize?.placementId === p.placement_id
              ? interactions.liveResize.delta
              : null

          // Apply live drag offset via transform; live resize via
          // grid coord adjustment for visual feedback.
          let liveGrid = p.grid
          if (liveResize) {
            liveGrid = {
              column_start: Math.max(
                1,
                p.grid.column_start + liveResize.dCol,
              ),
              column_span: Math.max(
                1,
                p.grid.column_span + liveResize.dColSpan,
              ),
              row_start: Math.max(1, p.grid.row_start + liveResize.dRow),
              row_span: Math.max(1, p.grid.row_span + liveResize.dRowSpan),
            }
          }

          const cellStyle: CSSProperties = {
            gridColumn: `${liveGrid.column_start} / span ${liveGrid.column_span}`,
            gridRow: `${liveGrid.row_start} / span ${liveGrid.row_span}`,
            zIndex: p.display_config?.z_index ?? (isSelected ? 5 : 1),
            transform: offset
              ? `translate(${offset.dxPx}px, ${offset.dyPx}px)`
              : undefined,
            position: "relative",
            cursor: interactionsEnabled ? "move" : "default",
            transition: offset || liveResize ? "none" : "box-shadow 120ms",
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
              className={`overflow-hidden rounded-md bg-surface-elevated shadow-level-1 ${baseRingClass}`}
              onPointerDown={(e) => {
                if (!interactionsEnabled) return
                // Stop the marquee from triggering when starting a
                // placement drag/click.
                e.stopPropagation()
                onSelect(p.placement_id, { shift: e.shiftKey })
                interactions.startPlacementDrag(p.placement_id, e)
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
              <div className="h-full overflow-hidden p-2">
                {placementContent}
              </div>

              {/* Resize handles — shown only when this placement is
                  the sole selected one (multi-select disables resize
                  to keep gestures unambiguous). */}
              {isSelected &&
                selectedIds.size === 1 &&
                interactionsEnabled &&
                RESIZE_HANDLES.map((h) => (
                  <div
                    key={h}
                    style={handleStyle(h)}
                    data-testid={`resize-handle-${p.placement_id}-${h}`}
                    onPointerDown={(e) => interactions.startResize(p.placement_id, h, e)}
                  />
                ))}
            </div>
          )
        })}

        {/* Marquee rectangle — visualizes the drag-select rect. */}
        {interactions.marqueeRect && (
          <div
            data-testid="canvas-marquee"
            style={{
              position: "absolute",
              left: interactions.marqueeRect.x,
              top: interactions.marqueeRect.y,
              width: interactions.marqueeRect.w,
              height: interactions.marqueeRect.h,
              background: "color-mix(in oklch, var(--accent) 8%, transparent)",
              border: "1px dashed var(--accent)",
              pointerEvents: "none",
              zIndex: 100,
            }}
          />
        )}
      </div>
    </div>
  )
}


export type { ResizeHandle, ComponentKind }

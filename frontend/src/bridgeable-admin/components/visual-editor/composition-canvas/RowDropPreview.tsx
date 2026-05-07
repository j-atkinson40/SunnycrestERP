/**
 * RowDropPreview — inserted-line affordance during cross-row drag and
 * row reorder gestures.
 *
 * Two visual modes:
 *
 *   placement-into-row: vertical brass line inside the target row at
 *     the column boundary where the dragged placement would land.
 *     Position computed from target row's per-row column_count and
 *     the target_starting_column.
 *
 *   row-insert: horizontal brass line in the gap between rows where
 *     the dragged row would insert. Spans full canvas width.
 *
 * Rendered absolutely-positioned within the canvas; pointer-events:
 * none so it never intercepts gestures.
 *
 * Tokens: brass `--accent` accent for the line itself.
 */
import type { DropPreview } from "./use-canvas-interactions"


interface Props {
  preview: DropPreview
  /** DOM resolver — same as the hook's resolver; returns the row's
   * container element OR null. */
  getRowElement: (rowId: string) => HTMLElement | null
  /** Canvas DOM ref for translating row rects → canvas-relative coords. */
  canvasElement: HTMLElement | null
  gapSize: number
}


export function RowDropPreview({
  preview,
  getRowElement,
  canvasElement,
  gapSize,
}: Props) {
  if (!preview || !canvasElement) return null
  const canvasRect = canvasElement.getBoundingClientRect()

  if (preview.kind === "placement-into-row") {
    const rowEl = getRowElement(preview.targetRowId)
    if (!rowEl) return null
    const rowRect = rowEl.getBoundingClientRect()
    // Compute the X position of the target column boundary (left edge
    // of the target column).
    const cells = parseInt(rowEl.getAttribute("data-column-count") ?? "12", 10)
    const cellW = (rowRect.width - gapSize * (cells - 1)) / cells
    const targetX =
      rowRect.left -
      canvasRect.left +
      preview.targetStartingColumn * (cellW + gapSize)
    const top = rowRect.top - canvasRect.top
    const height = rowRect.height
    return (
      <div
        data-testid="row-drop-preview-placement"
        data-target-row-id={preview.targetRowId}
        data-target-column={preview.targetStartingColumn}
        style={{
          position: "absolute",
          left: targetX,
          top,
          width: 2,
          height,
          background: "var(--accent)",
          pointerEvents: "none",
          zIndex: 50,
          boxShadow: "0 0 6px var(--accent)",
        }}
      />
    )
  }

  if (preview.kind === "row-insert") {
    // Compute Y position: above all rows if insertIndex=0, below all
    // if insertIndex=rows.length, otherwise in the gap between rows.
    // We need ALL row rects to determine this.
    const rowEls: HTMLElement[] = []
    let i = 0
    while (true) {
      // Walk siblings via data-row-index attribute on the canvas children.
      const candidate = canvasElement.querySelector<HTMLElement>(
        `[data-row-index="${i}"]`,
      )
      if (!candidate) break
      rowEls.push(candidate)
      i += 1
    }
    if (rowEls.length === 0) return null

    let lineY: number
    if (preview.insertIndex === 0) {
      lineY = rowEls[0].getBoundingClientRect().top - canvasRect.top
    } else if (preview.insertIndex >= rowEls.length) {
      lineY =
        rowEls[rowEls.length - 1].getBoundingClientRect().bottom -
        canvasRect.top
    } else {
      const above = rowEls[preview.insertIndex - 1].getBoundingClientRect()
      const below = rowEls[preview.insertIndex].getBoundingClientRect()
      lineY = (above.bottom + below.top) / 2 - canvasRect.top
    }

    return (
      <div
        data-testid="row-drop-preview-insert"
        data-insert-index={preview.insertIndex}
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          top: lineY - 1,
          height: 2,
          background: "var(--accent)",
          pointerEvents: "none",
          zIndex: 50,
          boxShadow: "0 0 6px var(--accent)",
        }}
      />
    )
  }

  return null
}

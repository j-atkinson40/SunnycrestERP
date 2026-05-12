/**
 * AlignmentGuideOverlay — Figma-shape alignment-guide rendering for the
 * composition canvas (Arc 4c, demo-supporting).
 *
 * ── Architectural framing ────────────────────────────────────────
 *
 * SVG overlay layer composited above the standalone canvas during an
 * active placement drag gesture. Computes alignment candidates from
 * the dragged placement(s) against the other placements in the same
 * row + the row's edges; renders horizontal + vertical guide lines
 * when alignment is within snap threshold.
 *
 * **Substrate scope — STANDALONE ONLY** per Q-ARC4C-1 Option (d)
 * Arc 4c canon: inspector canvas stays read-mostly (`interactionsEnabled
 * = false`), so no drag → no guides. Alignment guides are a drag-time
 * affordance and only mount where drag is canonical.
 *
 * **Snap threshold — 8px** sourced from DESIGN_LANGUAGE §5 spacing
 * scale (space-2 = 8px = canonical close-spacing unit). Matches the
 * existing `snapPxToCells` 8px-snapped offset canon in
 * `use-canvas-interactions.ts`. Hardcoded; per-tenant override
 * deferred until concrete operator signal warrants.
 *
 * **Co-located, NOT extracted** per shared-authoring-component-canon:
 * "extract when second consumer emerges." Today the canvas substrate
 * is the sole consumer (single canvas surface; inspector skips
 * guides). Pre-flight confirmed no near-term second consumer exists
 * (Workshop canvas + future Workflows canvas redesign are
 * speculative). Future canvas-shape consumers earn extraction.
 *
 * **Bespoke pointer-event state machine canon** (not @dnd-kit) — this
 * is the canon Arc 3a + Arc 4c locks for 2D-grid canvas work. @dnd-kit
 * is canonical for 1D-list reorder (Arc 4b.1b blocks). Two-arc
 * evidence locks the distinction.
 *
 * ── Algorithm ────────────────────────────────────────────────────
 *
 * On each drag-tick (driven by `liveOffset` from the canvas
 * interactions hook), compute the dragged placement's live rect
 * (start-rect + offset). Walk the other placements in the source row
 * + the row's own left/right edges. For each candidate, check if any
 * of three axis alignments fall within `SNAP_THRESHOLD_PX`:
 *
 *   - **left-edge alignment** (dragged.left ≈ candidate.left)
 *   - **center alignment** (dragged.centerX ≈ candidate.centerX)
 *   - **right-edge alignment** (dragged.right ≈ candidate.right)
 *
 * When matched, render a vertical SVG line at the matched X coord
 * spanning the canvas viewport height. Multi-match collapse to single
 * line when threshold-band overlaps. Horizontal alignment (top / mid
 * / bottom) renders similarly when row_height permits.
 *
 * Performance: re-computes on every gesture tick, but the work is
 * O(N placements in source row) which is bounded ~4-8 per row in
 * realistic compositions. SVG re-renders at React render cadence;
 * gestures fire at ~60fps via window pointermove which throttles
 * naturally.
 *
 * ── Pure helpers (test-friendly) ─────────────────────────────────
 *
 * `computeAlignmentGuides` is exported as a pure function (no DOM
 * access) so the alignment math is testable without rendering. The
 * component above is purely presentational; the math is below.
 */
import type { CSSProperties } from "react"
import type { CompositionRow } from "@/lib/visual-editor/compositions/types"


/** Snap threshold in pixels. 8px per DESIGN_LANGUAGE §5 spacing token
 * (space-2). Hardcoded; future per-tenant configurability earns its
 * own dispatch when concrete signal warrants. */
export const SNAP_THRESHOLD_PX = 8


/** A single alignment guide line. */
export interface AlignmentGuide {
  /** Vertical guides span horizontally; horizontal guides span vertically. */
  axis: "vertical" | "horizontal"
  /** Pixel offset in the canvas-local coordinate system. */
  position: number
  /** Optional discriminator for visual debugging / tests. */
  kind?: "edge" | "center"
}


/** A rect in canvas-local coordinates. */
export interface CanvasRect {
  left: number
  top: number
  width: number
  height: number
}


/** Compute alignment guides for a dragged placement against the
 * canonical reference rects (other placements in row + row edges).
 *
 * Pure function — no DOM access. Tests pass canvas-relative rects
 * directly. The component above derives rects from `getBoundingClientRect`
 * + canvas offset; here we just do the math.
 *
 * Returns a deduplicated list of guides. Duplicates at the same
 * (axis, position) are collapsed.
 */
export function computeAlignmentGuides(
  draggedRect: CanvasRect,
  referenceRects: CanvasRect[],
  threshold: number = SNAP_THRESHOLD_PX,
): AlignmentGuide[] {
  const guides: AlignmentGuide[] = []
  const seen = new Set<string>()

  const draggedLeft = draggedRect.left
  const draggedRight = draggedRect.left + draggedRect.width
  const draggedCenterX = draggedRect.left + draggedRect.width / 2
  const draggedTop = draggedRect.top
  const draggedBottom = draggedRect.top + draggedRect.height
  const draggedCenterY = draggedRect.top + draggedRect.height / 2

  function pushGuide(g: AlignmentGuide) {
    const key = `${g.axis}:${Math.round(g.position)}:${g.kind ?? "edge"}`
    if (seen.has(key)) return
    seen.add(key)
    guides.push(g)
  }

  for (const ref of referenceRects) {
    const refLeft = ref.left
    const refRight = ref.left + ref.width
    const refCenterX = ref.left + ref.width / 2
    const refTop = ref.top
    const refBottom = ref.top + ref.height
    const refCenterY = ref.top + ref.height / 2

    // Vertical axis — left edges
    if (Math.abs(draggedLeft - refLeft) <= threshold) {
      pushGuide({ axis: "vertical", position: refLeft, kind: "edge" })
    }
    // Vertical axis — right edges
    if (Math.abs(draggedRight - refRight) <= threshold) {
      pushGuide({ axis: "vertical", position: refRight, kind: "edge" })
    }
    // Vertical axis — center alignment
    if (Math.abs(draggedCenterX - refCenterX) <= threshold) {
      pushGuide({ axis: "vertical", position: refCenterX, kind: "center" })
    }
    // Vertical axis — left-to-right (snap dragged-left to ref-right or vice versa)
    if (Math.abs(draggedLeft - refRight) <= threshold) {
      pushGuide({ axis: "vertical", position: refRight, kind: "edge" })
    }
    if (Math.abs(draggedRight - refLeft) <= threshold) {
      pushGuide({ axis: "vertical", position: refLeft, kind: "edge" })
    }

    // Horizontal axis — top edges
    if (Math.abs(draggedTop - refTop) <= threshold) {
      pushGuide({ axis: "horizontal", position: refTop, kind: "edge" })
    }
    // Horizontal axis — bottom edges
    if (Math.abs(draggedBottom - refBottom) <= threshold) {
      pushGuide({ axis: "horizontal", position: refBottom, kind: "edge" })
    }
    // Horizontal axis — center alignment
    if (Math.abs(draggedCenterY - refCenterY) <= threshold) {
      pushGuide({ axis: "horizontal", position: refCenterY, kind: "center" })
    }
  }

  return guides
}


/** Resolve the list of reference rects for a dragged placement against
 * a row's other placements + the row's edges.
 *
 * Pure function — takes the row + dragged placement id + a per-
 * placement rect resolver (the canvas owns DOM refs). Returns the
 * filtered reference rects ready for `computeAlignmentGuides`.
 */
export function resolveReferenceRectsForRow(
  row: CompositionRow,
  draggedPlacementId: string,
  getPlacementRect: (placementId: string) => CanvasRect | null,
  rowRect: CanvasRect | null,
): CanvasRect[] {
  const rects: CanvasRect[] = []
  for (const p of row.placements) {
    if (p.placement_id === draggedPlacementId) continue
    const r = getPlacementRect(p.placement_id)
    if (r) rects.push(r)
  }
  // Row edges as canonical alignment candidates — top, bottom, left,
  // right. Modeled as a 0-thickness rect at each edge position via
  // a degenerate rect; the math treats edges as point candidates.
  if (rowRect) {
    // Row left + right edges
    rects.push({
      left: rowRect.left,
      top: rowRect.top,
      width: 0,
      height: rowRect.height,
    })
    rects.push({
      left: rowRect.left + rowRect.width,
      top: rowRect.top,
      width: 0,
      height: rowRect.height,
    })
  }
  return rects
}


/** Used by the SVG overlay below to compute the dragged placement's
 * live rect from its grid-coord placement + a live dx/dy pixel
 * offset. Pure function.
 */
export function liveDraggedRect(
  startRect: CanvasRect,
  liveOffset: { dxPx: number; dyPx: number },
): CanvasRect {
  return {
    left: startRect.left + liveOffset.dxPx,
    top: startRect.top + liveOffset.dyPx,
    width: startRect.width,
    height: startRect.height,
  }
}


// ─── Component ──────────────────────────────────────────────────


export interface AlignmentGuideOverlayProps {
  /** Active guides to render. Empty array hides overlay. */
  guides: AlignmentGuide[]
  /** Canvas dimensions in pixels for SVG sizing. */
  canvasWidth: number
  canvasHeight: number
  /** Visual override (defaults to brass accent). */
  guideColorVar?: string
}


/** SVG overlay rendering alignment guides during drag.
 *
 * Compositing approach: position absolute / inset-0 / pointer-events-
 * none above the canvas content. Renders nothing when `guides`
 * is empty. Vertical guides span full canvas height; horizontal
 * guides span full canvas width.
 *
 * Visual treatment: 1px-wide brass-accent dashed line. Brass matches
 * the canonical accent for active-drag affordances (per DESIGN_LANGUAGE
 * §6: brass focus rings + drag-active visual feedback).
 */
export function AlignmentGuideOverlay({
  guides,
  canvasWidth,
  canvasHeight,
  guideColorVar = "var(--accent)",
}: AlignmentGuideOverlayProps) {
  if (guides.length === 0) return null

  const overlayStyle: CSSProperties = {
    position: "absolute",
    left: 0,
    top: 0,
    width: canvasWidth,
    height: canvasHeight,
    pointerEvents: "none",
    zIndex: 200,
  }

  return (
    <svg
      style={overlayStyle}
      data-testid="alignment-guide-overlay"
      data-guide-count={guides.length}
      width={canvasWidth}
      height={canvasHeight}
      viewBox={`0 0 ${canvasWidth} ${canvasHeight}`}
      preserveAspectRatio="none"
    >
      {guides.map((g, i) => {
        if (g.axis === "vertical") {
          return (
            <line
              key={`v-${i}-${g.position}`}
              data-testid={`alignment-guide-vertical-${i}`}
              data-guide-axis="vertical"
              data-guide-kind={g.kind ?? "edge"}
              x1={g.position}
              y1={0}
              x2={g.position}
              y2={canvasHeight}
              stroke={guideColorVar}
              strokeWidth={1}
              strokeDasharray="4 4"
              opacity={0.85}
            />
          )
        }
        return (
          <line
            key={`h-${i}-${g.position}`}
            data-testid={`alignment-guide-horizontal-${i}`}
            data-guide-axis="horizontal"
            data-guide-kind={g.kind ?? "edge"}
            x1={0}
            y1={g.position}
            x2={canvasWidth}
            y2={g.position}
            stroke={guideColorVar}
            strokeWidth={1}
            strokeDasharray="4 4"
            opacity={0.85}
          />
        )
      })}
    </svg>
  )
}


// ─── Test internals (exposed for unit tests) ────────────────────


export const _alignmentInternals = {
  computeAlignmentGuides,
  resolveReferenceRectsForRow,
  liveDraggedRect,
  SNAP_THRESHOLD_PX,
}

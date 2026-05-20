/**
 * MarqueeOverlay — sub-arc FF-7.
 *
 * Absolutely-positioned rubber-band rectangle rendered during a
 * marquee drag on the canvas background. Per Q-16 (a): operators
 * pointer-down on empty canvas, drag 3+px, then pointer-up to
 * capture all placements whose bounding boxes intersect the
 * rectangle.
 *
 * Visual: 1px brass-accent border + ~15% alpha brass-subtle fill.
 * `pointer-events: none` so the marquee never blocks pointer events
 * while the operator is dragging it.
 *
 * Returns null when isActive is false, when points are missing, OR
 * when the rectangle's area is below the 3×3px threshold (matches
 * the 3px drag-activation discipline shared with @dnd-kit + the
 * canonical "tiny drag = treat as click" UX precedent).
 */
export interface MarqueeOverlayProps {
  isActive: boolean
  /** Pointer-down coords (canvas-relative). */
  startPoint: { x: number; y: number } | null
  /** Live pointer-move coords (canvas-relative). */
  currentPoint: { x: number; y: number } | null
}

export function MarqueeOverlay(props: MarqueeOverlayProps) {
  const { isActive, startPoint, currentPoint } = props
  if (!isActive || !startPoint || !currentPoint) return null

  const left = Math.min(startPoint.x, currentPoint.x)
  const top = Math.min(startPoint.y, currentPoint.y)
  const width = Math.abs(startPoint.x - currentPoint.x)
  const height = Math.abs(startPoint.y - currentPoint.y)

  // 3×3 (= 9 sq-px) threshold per Q-16 / 3px drag-activation canon.
  if (width * height < 9) return null

  return (
    <div
      data-testid="marquee-overlay"
      style={{
        position: "absolute",
        left: `${left}px`,
        top: `${top}px`,
        width: `${width}px`,
        height: `${height}px`,
        border: "1px solid var(--accent)",
        backgroundColor: "color-mix(in srgb, var(--accent) 15%, transparent)",
        pointerEvents: "none",
        zIndex: 9998,
      }}
    />
  )
}

export default MarqueeOverlay

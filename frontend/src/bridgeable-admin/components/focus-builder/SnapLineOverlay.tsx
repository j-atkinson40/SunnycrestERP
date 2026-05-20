/**
 * SnapLineOverlay — sub-arc FF-7.
 *
 * Renders SnapLines emitted by `computeSnapAdjustment` as 1px brass-
 * accent-colored overlay lines spanning the canvas. Mounted inside
 * the canvas DOM during a drag; updates live as `snapLines` change.
 * Returns null when the array is empty.
 *
 * Per Q-11: brass accent color (matches selection chrome), 1px
 * thickness, `pointer-events: none` so the operator's drag gesture
 * passes through to whatever is underneath.
 */
import type { SnapLine } from "./computeSnapAdjustment"

export interface SnapLineOverlayProps {
  snapLines: SnapLine[]
  canvasDimensions: { width: number; height: number }
}

export function SnapLineOverlay(props: SnapLineOverlayProps) {
  const { snapLines, canvasDimensions } = props
  if (!snapLines || snapLines.length === 0) return null

  return (
    <>
      {snapLines.map((line, idx) => {
        if (line.axis === "horizontal") {
          // Horizontal 1px line at y=position, full canvas width.
          return (
            <div
              key={`h-${idx}-${line.position}`}
              data-testid="snap-line"
              data-axis="horizontal"
              data-position={String(line.position)}
              style={{
                position: "absolute",
                left: 0,
                top: `${line.position}px`,
                width: `${canvasDimensions.width}px`,
                height: "1px",
                backgroundColor: "var(--accent)",
                pointerEvents: "none",
                zIndex: 10000,
              }}
            />
          )
        }
        // Vertical 1px line at x=position, full canvas height.
        return (
          <div
            key={`v-${idx}-${line.position}`}
            data-testid="snap-line"
            data-axis="vertical"
            data-position={String(line.position)}
            style={{
              position: "absolute",
              left: `${line.position}px`,
              top: 0,
              width: "1px",
              height: `${canvasDimensions.height}px`,
              backgroundColor: "var(--accent)",
              pointerEvents: "none",
              zIndex: 10000,
            }}
          />
        )
      })}
    </>
  )
}

export default SnapLineOverlay

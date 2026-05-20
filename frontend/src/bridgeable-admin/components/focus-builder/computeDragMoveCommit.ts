/**
 * computeDragMoveCommit — sub-arc FF-3.
 *
 * Pure helper that translates a free-form widget's current position +
 * cumulative drag delta into a canvas-bounded next position. Companion
 * to FF-2's `computeFreeFormDropPosition` (palette → canvas drop) but
 * for an EXISTING placement being repositioned via drag.
 *
 * Separated from `computeFreeFormDropPosition` per separation-of-
 * concerns: drop logic centers on cursor (Q-4), drag logic applies a
 * delta to a known position. Same Q-14 clamp semantics on output.
 *
 * Per investigation Q-14: widget positions clamp to canvas bounds
 * during the drag-end commit. The drag visual feedback may overshoot
 * during the gesture (dnd-kit translates via CSS transform on the
 * draggable), but the COMMIT clamps so the persisted x/y are always
 * in [0, canvas - widget].
 *
 * Per Q-40: pure-function shape keeps this unit-testable without
 * dnd-kit pointer gestures (JSDOM weakness). Integration tests at
 * FocusBuilderPage drive @dnd-kit's KeyboardSensor; pointer coverage
 * defers to Playwright at FF-7.
 *
 * Defensive: zero / negative canvas dimensions are treated as a no-op
 * lower bound — `Math.min` against a negative `canvas - widget` is
 * caught by the `Math.max(0, ...)` outer clamp. NaN inputs propagate
 * (callers must supply finite numbers; the registry + canvas config
 * shapes guarantee this in production paths).
 */

export interface DragMoveCommitInput {
  /** Current placement position (the value to commit-update). */
  currentX: number
  currentY: number
  /** Cumulative drag delta from drag-start to drag-end (dnd-kit `delta`). */
  dx: number
  dy: number
  /** Canvas dimensions (from template.canvas_config with defensive fallback). */
  canvasWidth: number
  canvasHeight: number
  /** Widget dimensions (from the placement's width/height). */
  widgetWidth: number
  widgetHeight: number
}

export function computeDragMoveCommit(
  input: DragMoveCommitInput,
): { x: number; y: number } {
  const {
    currentX,
    currentY,
    dx,
    dy,
    canvasWidth,
    canvasHeight,
    widgetWidth,
    widgetHeight,
  } = input
  // Apply delta first.
  const proposedX = currentX + dx
  const proposedY = currentY + dy
  // Q-14 clamp to canvas bounds. Lower bound 0; upper bound canvas -
  // widget. When canvas - widget < 0 (widget larger than canvas; not
  // expected but defensive), the upper bound collapses to a negative
  // value; the `Math.max(0, ...)` outer clamp pulls back to 0.
  const x = Math.max(0, Math.min(proposedX, canvasWidth - widgetWidth))
  const y = Math.max(0, Math.min(proposedY, canvasHeight - widgetHeight))
  return { x, y }
}

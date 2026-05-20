/**
 * computeResizeCommit — sub-arc FF-4.
 *
 * Pure helper that translates an existing free-form widget's
 * current placement (x/y/width/height) + a cumulative drag delta on
 * a specific resize handle into a canvas-bounded next placement that
 * also respects per-widget minimum dimensions.
 *
 * Companion to FF-2's `computeFreeFormDropPosition` (palette drop)
 * and FF-3's `computeDragMoveCommit` (whole-widget move). All three
 * pure helpers share the same Q-14 canvas-bounded clamp idea, but
 * resize math is per-handle: edges move one axis; corners move two.
 * For w/n/nw/sw handles the opposite edge stays anchored, so the
 * helper adjusts x or y inversely as width/height contract.
 *
 * Per investigation Q-10: 8 handles (nw / n / ne / w / e / sw / s /
 * se). Each handle's behavior is documented inline.
 *
 * Per Q-13: per-widget `freeFormMinDimensions` from registry with an
 * 80×40 platform fallback. The caller resolves the registry lookup
 * and passes the resolved `minDimensions` in — this keeps the helper
 * pure (no registry I/O) and easier to unit-test.
 *
 * Per Q-14: canvas-bounded clamp. Resizes that would push an edge
 * past 0 or past canvas.width / canvas.height snap to the bound.
 *
 * Clamping order (matters):
 *   1. Apply per-handle math against the delta.
 *   2. Enforce minimum dimensions. When a min-clamp engages on the
 *      w / n / nw / sw / ne / se side (i.e., x or y is moving and
 *      should anchor the opposite edge), adjust x / y so the
 *      opposite (un-handled) edge stays put.
 *   3. Enforce canvas bounds (0 ≤ x; 0 ≤ y; x + width ≤ canvas.width;
 *      y + height ≤ canvas.height). When a bound engages, snap to
 *      the bound without violating the min constraint.
 *
 * Aspect ratio preservation: NOT supported in FF-4 (deferred to FF-7
 * polish — Shift modifier may add it). Per-handle math is independent
 * per axis.
 *
 * Per Q-40: pure-function shape keeps this unit-testable without
 * dnd-kit pointer gestures. Integration tests at FocusBuilderPage
 * drive @dnd-kit's KeyboardSensor.
 */

export type ResizeHandlePosition =
  | "nw"
  | "n"
  | "ne"
  | "w"
  | "e"
  | "sw"
  | "s"
  | "se"

export interface ResizeCommitInput {
  /** Current placement position + size (the value to commit-update). */
  currentPlacement: { x: number; y: number; width: number; height: number }
  /** Which handle is being dragged. */
  handle: ResizeHandlePosition
  /** Cumulative drag delta from drag-start to drag-end (dnd-kit `delta`). */
  delta: { x: number; y: number }
  /** Canvas dimensions (from template.canvas_config with defensive fallback). */
  canvasDimensions: { width: number; height: number }
  /** Per-widget minimum dimensions (resolved by caller; 80×40 fallback). */
  minDimensions: { width: number; height: number }
}

export interface ResizeCommitResult {
  x: number
  y: number
  width: number
  height: number
}

/**
 * Per-handle bitmask: which edge does the handle move? Used to drive
 * the apply-then-clamp pipeline without per-handle branching at every
 * step.
 */
function affectedAxes(handle: ResizeHandlePosition): {
  moveLeft: boolean // w-side handles: w / nw / sw — x moves with delta.x; width shrinks/grows inversely
  moveRight: boolean // e-side handles: e / ne / se — width grows/shrinks with delta.x; x unchanged
  moveTop: boolean // n-side handles: n / nw / ne — y moves with delta.y; height shrinks/grows inversely
  moveBottom: boolean // s-side handles: s / sw / se — height grows/shrinks with delta.y; y unchanged
} {
  return {
    moveLeft: handle === "w" || handle === "nw" || handle === "sw",
    moveRight: handle === "e" || handle === "ne" || handle === "se",
    moveTop: handle === "n" || handle === "nw" || handle === "ne",
    moveBottom: handle === "s" || handle === "sw" || handle === "se",
  }
}

export function computeResizeCommit(
  input: ResizeCommitInput,
): ResizeCommitResult {
  const { currentPlacement, handle, delta, canvasDimensions, minDimensions } =
    input
  const { moveLeft, moveRight, moveTop, moveBottom } = affectedAxes(handle)

  // ── Step 1: apply per-handle math ───────────────────────────────
  // For w/nw/sw: x grows with delta.x; width shrinks by the same
  // amount so the right edge stays anchored.
  // For e/ne/se: width grows with delta.x; x unchanged.
  // For n/nw/ne: y grows with delta.y; height shrinks so the bottom
  // edge stays anchored.
  // For s/sw/se: height grows with delta.y; y unchanged.
  let nextX = currentPlacement.x
  let nextY = currentPlacement.y
  let nextWidth = currentPlacement.width
  let nextHeight = currentPlacement.height

  if (moveLeft) {
    nextX = currentPlacement.x + delta.x
    nextWidth = currentPlacement.width - delta.x
  } else if (moveRight) {
    nextWidth = currentPlacement.width + delta.x
  }

  if (moveTop) {
    nextY = currentPlacement.y + delta.y
    nextHeight = currentPlacement.height - delta.y
  } else if (moveBottom) {
    nextHeight = currentPlacement.height + delta.y
  }

  // ── Step 2: enforce minimum dimensions ──────────────────────────
  // When the min-clamp engages on a left/top-moving handle, we must
  // also adjust nextX / nextY backward so the opposite (anchored)
  // edge stays at its original position. The original right edge is
  // currentPlacement.x + currentPlacement.width; the original bottom
  // edge is currentPlacement.y + currentPlacement.height.
  if (nextWidth < minDimensions.width) {
    nextWidth = minDimensions.width
    if (moveLeft) {
      // Anchor the right edge at its original position.
      nextX = currentPlacement.x + currentPlacement.width - nextWidth
    }
  }
  if (nextHeight < minDimensions.height) {
    nextHeight = minDimensions.height
    if (moveTop) {
      // Anchor the bottom edge at its original position.
      nextY = currentPlacement.y + currentPlacement.height - nextHeight
    }
  }

  // ── Step 3: enforce canvas bounds ───────────────────────────────
  // Lower bounds first (x ≥ 0; y ≥ 0). When clamping at 0 on a
  // left/top-moving handle, the un-handled edge stays put which means
  // width/height grow to cover the gap. (Operator pulling the w-edge
  // past the canvas-left bound effectively widens the widget to its
  // original right edge.)
  if (nextX < 0) {
    if (moveLeft) {
      // Original right edge is currentPlacement.x + currentPlacement.width.
      // Snapping x to 0 means width = right edge - 0 = original right edge.
      const originalRight = currentPlacement.x + currentPlacement.width
      nextX = 0
      nextWidth = originalRight
    } else {
      // No left-moving handle — should not happen since x only moves
      // with moveLeft handles. Defensive clamp.
      nextX = 0
    }
  }
  if (nextY < 0) {
    if (moveTop) {
      const originalBottom = currentPlacement.y + currentPlacement.height
      nextY = 0
      nextHeight = originalBottom
    } else {
      nextY = 0
    }
  }

  // Upper bounds (x + width ≤ canvas.width; y + height ≤ canvas.height).
  // When the right edge overflows, clamp width (the e/ne/se handles
  // are the only ones that move the right edge); x stays.
  if (nextX + nextWidth > canvasDimensions.width) {
    if (moveRight) {
      nextWidth = canvasDimensions.width - nextX
    } else {
      // Defensive: should only fire if x itself is beyond canvas
      // (caller error). Pull x back so width fits.
      nextX = canvasDimensions.width - nextWidth
    }
  }
  if (nextY + nextHeight > canvasDimensions.height) {
    if (moveBottom) {
      nextHeight = canvasDimensions.height - nextY
    } else {
      nextY = canvasDimensions.height - nextHeight
    }
  }

  // After upper-bound clamp the min-dimension constraint may have
  // been violated (canvas - x < min). The order chosen by the spec is
  // "clamp without violating min" — if the canvas is too small to
  // honor both, the min wins (visually overflows by however much).
  // This is the canonical Figma behavior on undersized artboards.
  if (nextWidth < minDimensions.width) {
    nextWidth = minDimensions.width
  }
  if (nextHeight < minDimensions.height) {
    nextHeight = minDimensions.height
  }

  return { x: nextX, y: nextY, width: nextWidth, height: nextHeight }
}

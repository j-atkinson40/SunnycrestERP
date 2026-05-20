/**
 * computeSnapAdjustment — sub-arc FF-7.
 *
 * Figma-style invisible alignment helpers per investigation Q-11 (b).
 * During a drag, computes whether the dragged placement's reference
 * points (left / right / horizontal-center on the X axis; top /
 * bottom / vertical-center on the Y axis) align with any candidate
 * snap targets — other placements' edges / centers and the canvas
 * centerlines — within a 6px threshold. When a snap fires, the
 * proposed drag position is adjusted so the reference aligns exactly
 * to the target, and a SnapLine is emitted for the overlay to draw.
 *
 * Per Q-11: 6px threshold; Alt-key disables snap during a specific
 * drag (caller passes `altKeyHeld` through). Multiple simultaneous
 * snaps allowed — a widget can snap on BOTH axes at once (e.g., its
 * horizontal-center to one widget AND its top edge to another).
 *
 * The function is pure and policy-agnostic. The caller is responsible
 * for excluding inherited core from `otherPlacements` if structural
 * immutability is desired (matches FF-5 pattern — registry of policy
 * lives at FocusBuilderPage, not in the helper).
 *
 * Per Q-40: pure-function shape keeps this unit-testable without
 * staging an actual drag gesture. Pointer-event coverage in JSDOM
 * is unreliable; FF-7 ships Playwright snap visual coverage as a
 * companion gate.
 */

export interface SnapLine {
  /** Axis of the snap line. `horizontal` = a horizontal 1px line
   * spanning the canvas width at `position`'s y-coord; `vertical` =
   * a vertical 1px line at `position`'s x-coord. */
  axis: "horizontal" | "vertical"
  /** Pixel coordinate on the axis. For `horizontal`, this is the y;
   * for `vertical`, this is the x. */
  position: number
}

export interface SnapTargetPlacement {
  id: string
  x: number
  y: number
  width: number
  height: number
}

export interface SnapAdjustmentInput {
  /** The placement being dragged. Provides its current width / height
   * (used to compute right / bottom edges + centers at the proposed
   * dragPosition). Id used only for self-exclusion clarity. */
  draggedPlacement: {
    id: string
    x: number
    y: number
    width: number
    height: number
  }
  /** Candidate snap targets. Caller is responsible for filtering —
   * pass only placements eligible to snap against (e.g., excluding
   * the dragged placement itself and any structurally-immutable
   * children if policy dictates). */
  otherPlacements: SnapTargetPlacement[]
  /** Canvas dimensions for canvas-centerline snap candidates. */
  canvasDimensions: { width: number; height: number }
  /** Post-clamp candidate position for the dragged placement. Snap
   * runs AFTER canvas-bounds clamp (see FocusBuilderCanvas drag-end
   * dispatch); a snap that would push outside the canvas is rejected
   * for that axis. */
  dragPosition: { x: number; y: number }
  /** When true, snap is disabled entirely; the function returns
   * `dragPosition` unchanged and an empty `snapLines` array. */
  altKeyHeld: boolean
}

export interface SnapAdjustmentResult {
  x: number
  y: number
  snapLines: SnapLine[]
}

const SNAP_THRESHOLD_PX = 6

interface SnapCandidate {
  /** Coordinate on the snap axis. */
  target: number
  /** Distance (signed) between dragged-reference and target. */
  distance: number
  /** Adjustment to apply to dragPosition (added). */
  delta: number
  /** SnapLine emitted on match. */
  line: SnapLine
}

/**
 * Pick the closest snap candidate within threshold, or null. Ties
 * resolve to the first candidate found (stable order from caller).
 */
function pickClosest(candidates: SnapCandidate[]): SnapCandidate | null {
  let best: SnapCandidate | null = null
  let bestDistance = Number.POSITIVE_INFINITY
  for (const c of candidates) {
    const d = Math.abs(c.distance)
    if (d > SNAP_THRESHOLD_PX) continue
    if (d < bestDistance) {
      best = c
      bestDistance = d
    }
  }
  return best
}

export function computeSnapAdjustment(
  input: SnapAdjustmentInput,
): SnapAdjustmentResult {
  const {
    draggedPlacement,
    otherPlacements,
    canvasDimensions,
    dragPosition,
    altKeyHeld,
  } = input

  if (altKeyHeld) {
    return { x: dragPosition.x, y: dragPosition.y, snapLines: [] }
  }

  const { width: dW, height: dH } = draggedPlacement
  const proposedX = dragPosition.x
  const proposedY = dragPosition.y

  // Dragged reference points at the proposed position.
  const draggedLeft = proposedX
  const draggedRight = proposedX + dW
  const draggedCenterX = proposedX + dW / 2
  const draggedTop = proposedY
  const draggedBottom = proposedY + dH
  const draggedCenterY = proposedY + dH / 2

  // Build X-axis snap candidates.
  const xCandidates: SnapCandidate[] = []
  for (const other of otherPlacements) {
    const oLeft = other.x
    const oRight = other.x + other.width
    const oCenterX = other.x + other.width / 2
    // For each of dragged's 3 X references, try snapping to each of
    // other's 3 X targets.
    for (const targetX of [oLeft, oRight, oCenterX]) {
      // dragged left edge → targetX
      xCandidates.push({
        target: targetX,
        distance: draggedLeft - targetX,
        delta: targetX - draggedLeft,
        line: { axis: "vertical", position: targetX },
      })
      // dragged right edge → targetX
      xCandidates.push({
        target: targetX,
        distance: draggedRight - targetX,
        delta: targetX - draggedRight,
        line: { axis: "vertical", position: targetX },
      })
      // dragged center → targetX
      xCandidates.push({
        target: targetX,
        distance: draggedCenterX - targetX,
        delta: targetX - draggedCenterX,
        line: { axis: "vertical", position: targetX },
      })
    }
  }
  // Canvas centerline X.
  const canvasCenterX = canvasDimensions.width / 2
  xCandidates.push(
    {
      target: canvasCenterX,
      distance: draggedLeft - canvasCenterX,
      delta: canvasCenterX - draggedLeft,
      line: { axis: "vertical", position: canvasCenterX },
    },
    {
      target: canvasCenterX,
      distance: draggedRight - canvasCenterX,
      delta: canvasCenterX - draggedRight,
      line: { axis: "vertical", position: canvasCenterX },
    },
    {
      target: canvasCenterX,
      distance: draggedCenterX - canvasCenterX,
      delta: canvasCenterX - draggedCenterX,
      line: { axis: "vertical", position: canvasCenterX },
    },
  )

  // Build Y-axis snap candidates.
  const yCandidates: SnapCandidate[] = []
  for (const other of otherPlacements) {
    const oTop = other.y
    const oBottom = other.y + other.height
    const oCenterY = other.y + other.height / 2
    for (const targetY of [oTop, oBottom, oCenterY]) {
      yCandidates.push({
        target: targetY,
        distance: draggedTop - targetY,
        delta: targetY - draggedTop,
        line: { axis: "horizontal", position: targetY },
      })
      yCandidates.push({
        target: targetY,
        distance: draggedBottom - targetY,
        delta: targetY - draggedBottom,
        line: { axis: "horizontal", position: targetY },
      })
      yCandidates.push({
        target: targetY,
        distance: draggedCenterY - targetY,
        delta: targetY - draggedCenterY,
        line: { axis: "horizontal", position: targetY },
      })
    }
  }
  // Canvas centerline Y.
  const canvasCenterY = canvasDimensions.height / 2
  yCandidates.push(
    {
      target: canvasCenterY,
      distance: draggedTop - canvasCenterY,
      delta: canvasCenterY - draggedTop,
      line: { axis: "horizontal", position: canvasCenterY },
    },
    {
      target: canvasCenterY,
      distance: draggedBottom - canvasCenterY,
      delta: canvasCenterY - draggedBottom,
      line: { axis: "horizontal", position: canvasCenterY },
    },
    {
      target: canvasCenterY,
      distance: draggedCenterY - canvasCenterY,
      delta: canvasCenterY - draggedCenterY,
      line: { axis: "horizontal", position: canvasCenterY },
    },
  )

  const xSnap = pickClosest(xCandidates)
  const ySnap = pickClosest(yCandidates)

  const snapLines: SnapLine[] = []
  let nextX = proposedX
  let nextY = proposedY

  if (xSnap) {
    nextX = proposedX + xSnap.delta
    snapLines.push(xSnap.line)
  }
  if (ySnap) {
    nextY = proposedY + ySnap.delta
    snapLines.push(ySnap.line)
  }

  return { x: nextX, y: nextY, snapLines }
}

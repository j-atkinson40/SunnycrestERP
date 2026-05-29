/**
 * canvas-layout — Phase B sub-arc B-1 (Graph canvas foundation).
 *
 * Pure-function geometry helpers for the workflow graph canvas. The
 * workflow authoring canvas is a DIRECTED GRAPH (DAG): nodes carry an
 * explicit `position: {x, y}` (already in the CanvasNode schema per
 * `workflow-templates-service.ts` + backend `canvas_validator.py:6-39`);
 * edges connect source → target node positions. This module owns the
 * coordinate math so `GraphCanvas.tsx` stays a thin presentational +
 * gesture shell.
 *
 * Mirrors the FF-3 free-form-canvas precedent at
 * `bridgeable-admin/components/focus-builder/computeDragMoveCommit.ts`:
 *   - drag-end commit applies a cumulative delta to a known position
 *     then clamps to canvas bounds (Q-14 clamp semantics)
 *   - pure-function shape keeps every coordinate helper unit-testable
 *     in vitest WITHOUT dnd-kit pointer gestures (Q-40 JSDOM weakness;
 *     pointer-drag coverage defers to Playwright)
 *
 * The workflow canvas differs from the FF free-form widget canvas in
 * one dimension: it ALSO renders edges as SVG paths between node anchor
 * points. `computeEdgePath` owns that geometry. Everything else (node
 * default placement, drag-commit clamp, bounding box) parallels FF-3.
 *
 * Per Entry 11 (WYSIWYG canvas-layout-model constraint): the authoring
 * canvas matches the runtime DAG layout model. This is the third canvas
 * model (DAG) distinct from Monitor (grid) + Decide (free-form).
 *
 * Defensive: NaN inputs propagate (callers supply finite numbers; the
 * canvas-state schema guarantees this in production paths). Zero /
 * negative canvas dimensions collapse the upper clamp bound to a
 * negative value; the `Math.max(0, ...)` outer clamp pulls back to 0.
 */

// ─── Canvas + node geometry constants ───────────────────────────────

/**
 * Default node-box dimensions in canvas pixels. A workflow node renders
 * as a fixed-size card; positions in canvas_state are the TOP-LEFT
 * corner of this box (consistent with FF free-form `placement.x/y`).
 */
export const NODE_WIDTH = 200
export const NODE_HEIGHT = 72

/**
 * Default canvas dimensions. The canvas is a scrollable surface; these
 * are the minimum logical bounds used for drag-clamp + the SVG edge
 * layer's viewBox when the authored graph fits within them. When the
 * graph's bounding box exceeds these, the canvas grows (see `bbox`).
 */
export const CANVAS_MIN_WIDTH = 1600
export const CANVAS_MIN_HEIGHT = 1000

/**
 * Vertical stride between auto-placed nodes (matches the pre-B-1
 * `handleAddNode` stack increment of 120 so existing stacked layouts
 * round-trip unchanged when first opened in the graph canvas).
 */
export const NODE_STACK_STRIDE_Y = 120

/** Default x for auto-placed nodes (left-anchored column). */
export const NODE_DEFAULT_X = 40

/** Padding added around the authored graph's bounding box. */
export const CANVAS_BBOX_PADDING = 120


// ─── Types ──────────────────────────────────────────────────────────

export interface Point {
  x: number
  y: number
}

export interface PositionedNode {
  id: string
  position: Point
}

export interface DragCommitInput {
  /** Current node position (the value being commit-updated). */
  currentX: number
  currentY: number
  /** Cumulative drag delta from drag-start to drag-end (dnd-kit `delta`). */
  dx: number
  dy: number
  /** Canvas bounds for the clamp. */
  canvasWidth: number
  canvasHeight: number
  /** Node-box dimensions. */
  nodeWidth?: number
  nodeHeight?: number
}

export interface EdgePathInput {
  /** Source node top-left position. */
  source: Point
  /** Target node top-left position. */
  target: Point
  /** Node-box dimensions (for anchor-point computation). */
  nodeWidth?: number
  nodeHeight?: number
}

export interface BBox {
  minX: number
  minY: number
  maxX: number
  maxY: number
  width: number
  height: number
}


// ─── computeNodeDefaultPosition ─────────────────────────────────────

/**
 * Compute a default position for a NEW node added from the palette.
 * Stacks vertically below the lowest existing node (matching the
 * pre-B-1 `handleAddNode` behavior of `max(y) + 120`), left-anchored
 * at NODE_DEFAULT_X. Empty canvas → first node at (NODE_DEFAULT_X, 40).
 *
 * Collision-avoidance: the stack-below-lowest rule guarantees the new
 * node never overlaps an existing one on the y axis.
 */
export function computeNodeDefaultPosition(
  existingNodes: readonly PositionedNode[],
  // A3 grow-to-fit (optional): when measured heights are available, stack
  // below the lowest node's REAL bottom so a tall card doesn't overlap the
  // new node. Omitted → the original `max(top) + STRIDE` behavior (a
  // default-height node yields the identical result, since
  // `(y + NODE_HEIGHT) + (STRIDE − NODE_HEIGHT) === y + STRIDE`).
  heightOf?: (n: PositionedNode) => number,
): Point {
  if (existingNodes.length === 0) {
    return { x: NODE_DEFAULT_X, y: 40 }
  }
  if (heightOf) {
    const maxBottom = Math.max(
      ...existingNodes.map((n) => n.position.y + heightOf(n)),
    )
    return { x: NODE_DEFAULT_X, y: maxBottom + (NODE_STACK_STRIDE_Y - NODE_HEIGHT) }
  }
  const maxY = Math.max(...existingNodes.map((n) => n.position.y))
  return { x: NODE_DEFAULT_X, y: maxY + NODE_STACK_STRIDE_Y }
}


// ─── clampToCanvas ──────────────────────────────────────────────────

/**
 * Clamp a proposed top-left position to canvas bounds. Lower bound 0;
 * upper bound canvas − node. When canvas − node < 0 (node larger than
 * canvas; defensive), the upper bound collapses negative and the outer
 * `Math.max(0, ...)` pulls back to 0.
 */
export function clampToCanvas(
  x: number,
  y: number,
  canvasWidth: number,
  canvasHeight: number,
  nodeWidth: number = NODE_WIDTH,
  nodeHeight: number = NODE_HEIGHT,
): Point {
  return {
    x: Math.max(0, Math.min(x, canvasWidth - nodeWidth)),
    y: Math.max(0, Math.min(y, canvasHeight - nodeHeight)),
  }
}


// ─── computeNodeDragCommit ──────────────────────────────────────────

/**
 * Translate a node's current position + cumulative drag delta into a
 * canvas-bounded next position. Companion to FF-3's
 * `computeDragMoveCommit` — applies the delta then clamps (Q-14).
 */
export function computeNodeDragCommit(input: DragCommitInput): Point {
  const {
    currentX,
    currentY,
    dx,
    dy,
    canvasWidth,
    canvasHeight,
    nodeWidth = NODE_WIDTH,
    nodeHeight = NODE_HEIGHT,
  } = input
  return clampToCanvas(
    currentX + dx,
    currentY + dy,
    canvasWidth,
    canvasHeight,
    nodeWidth,
    nodeHeight,
  )
}


// ─── computeEdgePath ────────────────────────────────────────────────

/**
 * Compute an SVG cubic-bezier `d` path string connecting a source node
 * to a target node. The edge departs the source node's bottom-center
 * anchor and arrives at the target node's top-center anchor, with
 * control points pulled vertically so the curve reads as a directed
 * top-down flow (matching the DAG's natural reading order). When the
 * target sits ABOVE the source (back-edge / iteration), the curve still
 * connects the same anchors — the bezier handles the reversal smoothly.
 */
export function computeEdgePath(input: EdgePathInput): string {
  const {
    source,
    target,
    nodeWidth = NODE_WIDTH,
    nodeHeight = NODE_HEIGHT,
  } = input
  const sx = source.x + nodeWidth / 2
  const sy = source.y + nodeHeight
  const tx = target.x + nodeWidth / 2
  const ty = target.y
  // Vertical control-point offset: half the vertical gap, floored so
  // near-horizontal edges still bow rather than collapsing to a line.
  const dy = ty - sy
  const ctrl = Math.max(40, Math.abs(dy) / 2)
  const c1y = sy + ctrl
  const c2y = ty - ctrl
  return `M ${sx} ${sy} C ${sx} ${c1y}, ${tx} ${c2y}, ${tx} ${ty}`
}

/**
 * Compute the midpoint of an edge path (for placing the edge's
 * condition / label text). Approximates the cubic-bezier midpoint as
 * the average of the two anchor points — sufficient for label
 * placement (exact bezier arc-length midpoint is unnecessary).
 */
export function computeEdgeMidpoint(input: EdgePathInput): Point {
  const {
    source,
    target,
    nodeWidth = NODE_WIDTH,
    nodeHeight = NODE_HEIGHT,
  } = input
  const sx = source.x + nodeWidth / 2
  const sy = source.y + nodeHeight
  const tx = target.x + nodeWidth / 2
  const ty = target.y
  return { x: (sx + tx) / 2, y: (sy + ty) / 2 }
}


// ─── bbox ───────────────────────────────────────────────────────────

/**
 * Compute the bounding box of the authored graph (all node boxes) plus
 * padding. Used to size the scrollable canvas surface + SVG edge-layer
 * viewBox so the full graph is reachable. Empty graph → the canvas
 * minimum bounds.
 */
export function bbox(
  nodes: readonly PositionedNode[],
  nodeWidth: number = NODE_WIDTH,
  // A3 grow-to-fit: per-node height resolver. Cards are variable-height
  // (label wraps, card grows down), so the bottom bound must use each
  // node's MEASURED height, not a constant. Default `() => NODE_HEIGHT`
  // preserves the fixed-height behavior for callers/tests that don't
  // measure (e.g. jsdom, where the ResizeObserver stub no-ops).
  heightOf: (n: PositionedNode) => number = () => NODE_HEIGHT,
): BBox {
  if (nodes.length === 0) {
    return {
      minX: 0,
      minY: 0,
      maxX: CANVAS_MIN_WIDTH,
      maxY: CANVAS_MIN_HEIGHT,
      width: CANVAS_MIN_WIDTH,
      height: CANVAS_MIN_HEIGHT,
    }
  }
  let minX = Infinity
  let minY = Infinity
  let maxX = -Infinity
  let maxY = -Infinity
  for (const n of nodes) {
    minX = Math.min(minX, n.position.x)
    minY = Math.min(minY, n.position.y)
    maxX = Math.max(maxX, n.position.x + nodeWidth)
    maxY = Math.max(maxY, n.position.y + heightOf(n))
  }
  // Graph origin is always (0,0) for the scroll surface; pad the far
  // edges so the bottom-right node isn't flush against the boundary.
  const width = Math.max(CANVAS_MIN_WIDTH, maxX + CANVAS_BBOX_PADDING)
  const height = Math.max(CANVAS_MIN_HEIGHT, maxY + CANVAS_BBOX_PADDING)
  return { minX, minY, maxX, maxY, width, height }
}

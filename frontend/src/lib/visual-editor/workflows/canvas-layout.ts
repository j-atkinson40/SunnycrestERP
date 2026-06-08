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

import {
  validateCanvasState,
} from "./canvas-validator"
import type {
  CanvasNode,
  CanvasEdge,
  CanvasState,
  WorkflowContainer,
} from "@/bridgeable-admin/services/workflow-templates-service"

// ─── Canvas + node geometry constants ───────────────────────────────

/**
 * Default node-box dimensions in canvas pixels. A workflow node renders
 * as a fixed-size card; positions in canvas_state are the TOP-LEFT
 * corner of this box (consistent with FF free-form `placement.x/y`).
 */
export const NODE_WIDTH = 200
export const NODE_HEIGHT = 72

/**
 * Container-arc Phase 2a — fixed dimensions of a COLLAPSED container card.
 * When collapsed, member nodes are hidden, so the box is NOT sized to the
 * member bbox (that would defeat the tangle-tidying purpose) — it's a compact
 * fixed-size card positioned at the members' bbox top-left (see
 * `collapsedBoxBounds`). Width matches a node card; height is a touch shorter
 * (the collapsed card shows the label + a member count, not a sentence body).
 */
export const COLLAPSED_CONTAINER_WIDTH = 200
export const COLLAPSED_CONTAINER_HEIGHT = 64

/**
 * Container-arc Phase 3a — padding between an EXPANDED container's member
 * extent and its enclosing frame, used by the recursive `containerBounds`.
 * Mirrors GraphCanvas.tsx's `CONTAINER_PADDING` (18) so the recursive helper
 * produces bounds identical to P1/P2's inline expanded-bbox computation for
 * the flat case; the two constants unify when 3b swaps the inline math for
 * `containerBounds`.
 */
export const CONTAINER_EXPANDED_PADDING = 18

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
  /** Negative-coordinate support — lower clamp bound (the content origin).
   *  Default 0 → pre-support behavior (byte-identical). */
  minX?: number
  minY?: number
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
  /**
   * Negative-coordinate support — the content ORIGIN to SUBTRACT when mapping
   * content coords → on-surface (DOM/SVG) coords: `dom = content - origin`.
   * `originX = min(0, minX)`, `originY = min(0, minY)` — so it is **0 for any
   * canvas whose content is entirely at non-negative coordinates**, making the
   * whole offset a no-op (byte-identical to pre-support rendering). It is < 0
   * only when content extends into negative space (e.g. a node at x=-300),
   * shifting that content back on-surface. Consumers: node/container `left/top`
   * (subtract), the edge-SVG `viewBox` (origin top-left), the pan-clamp bounds,
   * the drag-to-connect hit-test (add back to recover raw content), and the
   * node-drag clamp lower bound.
   */
  originX: number
  originY: number
}

/**
 * Container-arc Phase 2a — a top-left-origin box (matches the
 * GraphCanvasContainer bounds prop shape, so `collapsedBoxBounds` output
 * flows straight into the render in P2b). `boxAnchor` anchors edges on it.
 */
export interface BoxBounds {
  x: number
  y: number
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
  // Negative-coordinate support — the lower clamp bound (the content origin).
  // Defaults to 0 → pre-support behavior (byte-identical); passed the bbox
  // `originX/originY` (< 0) so a node legitimately at negative coords isn't
  // snapped to 0 on drag.
  minX: number = 0,
  minY: number = 0,
): Point {
  return {
    x: Math.max(minX, Math.min(x, canvasWidth - nodeWidth)),
    y: Math.max(minY, Math.min(y, canvasHeight - nodeHeight)),
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
    minX = 0,
    minY = 0,
  } = input
  return clampToCanvas(
    currentX + dx,
    currentY + dy,
    canvasWidth,
    canvasHeight,
    nodeWidth,
    nodeHeight,
    minX,
    minY,
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
  // Container-arc Phase 2a — decomposed into the reusable anchor + curve
  // helpers (OUTPUT-IDENTICAL to the prior inline math; the canvas-layout
  // tests lock the node→node string). Source departs its bottom-center,
  // target arrives at its top-center — exactly what `boxAnchor` computes for
  // a node-sized box.
  return bezierBetween(
    boxAnchor(
      { x: source.x, y: source.y, width: nodeWidth, height: nodeHeight },
      "bottom",
    ),
    boxAnchor(
      { x: target.x, y: target.y, width: nodeWidth, height: nodeHeight },
      "top",
    ),
  )
}


// ─── boxAnchor + bezierBetween (Phase 2a — the anchor split) ────────────

/**
 * The top-center or bottom-center point of a box. Side-bucketed edge
 * rerouting (P2b) anchors crossing-IN edges at a container's "top" and
 * crossing-OUT at its "bottom" — the same top-in/bottom-out convention nodes
 * use, generalized to an arbitrary box (node OR collapsed container).
 *   top    = (x + width/2, y)
 *   bottom = (x + width/2, y + height)
 */
export function boxAnchor(bounds: BoxBounds, side: "top" | "bottom"): Point {
  const cx = bounds.x + bounds.width / 2
  return side === "top"
    ? { x: cx, y: bounds.y }
    : { x: cx, y: bounds.y + bounds.height }
}

/**
 * The cubic-bezier `d` string between two already-resolved anchor points.
 * The curve core extracted (unchanged) from the prior `computeEdgePath` /
 * `computeEdgePreviewPath` inline math: a vertical control offset of half the
 * vertical gap, floored at 40 so near-horizontal edges still bow. Both former
 * callers now compose this — node→node (computeEdgePath), node→cursor
 * (computeEdgePreviewPath), and P2b's box-anchored crossing edges.
 */
export function bezierBetween(src: Point, tgt: Point): string {
  const dy = tgt.y - src.y
  const ctrl = Math.max(40, Math.abs(dy) / 2)
  return `M ${src.x} ${src.y} C ${src.x} ${src.y + ctrl}, ${tgt.x} ${tgt.y - ctrl}, ${tgt.x} ${tgt.y}`
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
      originX: 0,
      originY: 0,
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
  // Negative-coordinate support — the content origin to subtract so negative
  // content maps back on-surface. `min(0, …)` makes it 0 for non-negative
  // content (no-op; byte-identical) and < 0 only when content goes negative.
  const originX = Math.min(0, minX)
  const originY = Math.min(0, minY)
  // The surface spans the full content extent (origin → max) + padding. With a
  // non-negative origin (== 0) this is the pre-support `max(MIN, maxX + pad)`.
  const width = Math.max(CANVAS_MIN_WIDTH, maxX - originX + CANVAS_BBOX_PADDING)
  const height = Math.max(CANVAS_MIN_HEIGHT, maxY - originY + CANVAS_BBOX_PADDING)
  return { minX, minY, maxX, maxY, width, height, originX, originY }
}


// ─── Drag-to-connect geometry (P3b-1a — pure, consumed by P3b-1b) ────
//
// The math drag-to-connect needs, isolated + unit-tested BEFORE the
// gesture is built on it (the screen-vs-world inversion is where a bug
// would otherwise hide inside the pointer gesture). NONE of these touch
// the DOM or pointer events — they are pure coordinate/decision functions.
// The screen→world inverse itself lives in `canvas-pan-zoom.ts`
// (`screenToWorld`), next to the world→screen transform it inverts.


// ─── computeEdgePreviewPath ─────────────────────────────────────────

/**
 * SVG `d` path for the IN-PROGRESS preview edge during a drag-to-connect
 * gesture: from the source node's bottom-center anchor to the live cursor
 * world point. Mirrors `computeEdgePath`'s cubic-bezier curve style, but
 * the endpoint is a BARE POINT (the cursor) — NOT a node box. (Reusing
 * `computeEdgePath` would mis-anchor: it adds `nodeWidth/2` to the target,
 * assuming the target is a node.) The source anchor is height-aware
 * (`sy = sourcePos.y + sourceHeight`) so the preview departs the true
 * bottom of a grow-to-fit card, matching the committed edge's source
 * anchor.
 */
export function computeEdgePreviewPath(
  sourcePos: Point,
  sourceHeight: number,
  cursorWorld: Point,
  nodeWidth: number = NODE_WIDTH,
): string {
  // Container-arc Phase 2a — folded onto the shared curve core (OUTPUT-
  // IDENTICAL to the prior inline math; the preview tests lock the
  // node→cursor string). Source departs its bottom-center; the target is the
  // bare cursor point (NOT a box — no top-center adjustment).
  return bezierBetween(
    boxAnchor(
      { x: sourcePos.x, y: sourcePos.y, width: nodeWidth, height: sourceHeight },
      "bottom",
    ),
    cursorWorld,
  )
}


// ─── nodeAtPoint ────────────────────────────────────────────────────

/**
 * Hit-test: the node whose bbox contains `worldPt`, else `null`. The bbox
 * is `(x, y, NODE_WIDTH, heights.get(id) ?? NODE_HEIGHT)` — the grow-to-fit
 * MEASURED height (so a tall card's lower region is hittable), falling back
 * to the fixed height when unmeasured (jsdom, or a freshly-added node).
 * Iterates in REVERSE so that when bboxes overlap the later-rendered node
 * (visually on top — nodes paint in array order) wins, matching what the
 * operator sees. Pure.
 */
export function nodeAtPoint(
  nodes: readonly CanvasNode[],
  heights: ReadonlyMap<string, number>,
  worldPt: Point,
  nodeWidth: number = NODE_WIDTH,
): CanvasNode | null {
  for (let i = nodes.length - 1; i >= 0; i--) {
    const n = nodes[i]
    const h = heights.get(n.id) ?? NODE_HEIGHT
    if (
      worldPt.x >= n.position.x &&
      worldPt.x <= n.position.x + nodeWidth &&
      worldPt.y >= n.position.y &&
      worldPt.y <= n.position.y + h
    ) {
      return n
    }
  }
  return null
}


// ─── dropDecision ───────────────────────────────────────────────────

export interface DropDecisionInput {
  nodes: readonly CanvasNode[]
  edges: readonly CanvasEdge[]
  heights: ReadonlyMap<string, number>
  /** The node the drag started from (its outgoing handle). */
  sourceId: string
  /** The pointer's world position at drop (via `screenToWorld`). */
  cursorWorld: Point
}

export interface DropDecision {
  action: "create" | "cancel"
  /** Why a "cancel" happened (omitted on "create"). */
  reason?: "empty" | "self" | "duplicate" | "cycle"
  /** The resolved target node id (present on "create"). */
  target?: string
}

/**
 * Decide what a drag-to-connect DROP does, purely from canvas state +
 * geometry. Order: hit-test → no node = cancel/empty; the source itself =
 * cancel/self; an edge (source→target) already exists = cancel/duplicate
 * (the validator only enforces edge-id uniqueness, NOT source/target-pair
 * uniqueness — so this is an explicit check, mirroring the inspector's
 * candidate-target filter); else build the candidate canvas + run the
 * canonical `validateCanvasState` — if it THROWS (cycle, excluding
 * is_iteration back-edges) = cancel/cycle (P3-map decision #8: cycle drops
 * are rejected; legitimate-loop authoring via is_iteration is filed
 * forward). Otherwise = create/target.
 *
 * Pure: `validateCanvasState` is side-effect-free (asserts/throws on a
 * passed canvas). The candidate carries a non-colliding placeholder edge
 * id; `trigger` is omitted (optional + not validated).
 */
export function dropDecision(input: DropDecisionInput): DropDecision {
  const { nodes, edges, heights, sourceId, cursorWorld } = input
  const hit = nodeAtPoint(nodes, heights, cursorWorld)
  if (!hit) return { action: "cancel", reason: "empty" }
  if (hit.id === sourceId) return { action: "cancel", reason: "self" }
  if (edges.some((e) => e.source === sourceId && e.target === hit.id)) {
    return { action: "cancel", reason: "duplicate" }
  }
  const candidate: CanvasState = {
    version: 1,
    nodes: [...nodes],
    edges: [
      ...edges,
      { id: `__candidate__${sourceId}__${hit.id}`, source: sourceId, target: hit.id },
    ],
  }
  try {
    validateCanvasState(candidate)
  } catch {
    return { action: "cancel", reason: "cycle" }
  }
  return { action: "create", target: hit.id }
}


// ─── Collapse helpers (Phase 2a — pure, consumed by P2b) ────────────
//
// The geometry + classification a collapsed container's edge-rerouting needs,
// de-risked + unit-tested in isolation BEFORE P2b wires them into the live
// edge-map + node-map (mirrors the P3b-1a pure-helper precedent). NONE touch
// the DOM or React. Side-bucketed model: crossing-IN → box top, crossing-OUT
// → box bottom (via `boxAnchor`). FLAT only — `kind:"container"` members are
// skipped (P2 produces none; nested membership is Phase 3).


// ─── buildParentMap (Phase 3a — nested containers) ──────────────────

/**
 * Map each MEMBER id (node OR container) → its PARENT container id. Built from
 * every container's members (both kinds), all containers — not just collapsed.
 * The child→parent relation backing the ancestor-chain walk. A top-level
 * container (member of nothing) is absent. Pure.
 */
export function buildParentMap(
  containers: readonly WorkflowContainer[] | undefined,
): Map<string, string> {
  const parent = new Map<string, string>()
  if (!containers) return parent
  for (const container of containers) {
    for (const member of container.members) {
      parent.set(member.id, container.id)
    }
  }
  return parent
}


// ─── outermostCollapsedAncestor (Phase 3a — nested containers) ──────

/**
 * Walk UP the parent chain from `id` (a node or container) and return the
 * HIGHEST (outermost) ancestor that is `collapsed`, or null if none is. The
 * outermost wins because a collapsed outer container hides EVERYTHING inside
 * it regardless of inner collapse-states (A⊃B⊃N: A collapsed → A, even if B
 * is too; only B collapsed → B; neither → null).
 *
 * Cycle-safe by construction (the validator proves the nesting graph is a DAG)
 * AND defensively via a visited-set so a malformed-but-unvalidated input can't
 * loop forever. Pure.
 */
export function outermostCollapsedAncestor(
  id: string,
  parentMap: ReadonlyMap<string, string>,
  containersById: ReadonlyMap<string, WorkflowContainer>,
): string | null {
  let outermost: string | null = null
  const visited = new Set<string>()
  let current = parentMap.get(id)
  while (current !== undefined && !visited.has(current)) {
    visited.add(current)
    const container = containersById.get(current)
    if (container?.collapsed) outermost = current
    current = parentMap.get(current)
  }
  return outermost
}


// ─── buildCollapsedMembership ───────────────────────────────────────

/**
 * Map each hidden node-id → the collapsed container it renders into. Phase 3a
 * REWORK: nesting-aware — a node maps to its OUTERMOST collapsed ancestor (not
 * just its direct container), so a node hidden inside any-level collapsed
 * container is captured. Iterates `kind:"node"` members across all containers
 * (a node must be a member of some container to be hidden) and resolves each
 * via the parent-chain walk; only nodes WITH a collapsed ancestor are mapped.
 *
 * FLAT-CASE OUTPUT-IDENTICAL (the regression guard — P2b consumes this): with
 * no nesting, a node's only ancestor is its direct container, so its outermost
 * collapsed ancestor is that container (if collapsed) else null — exactly the
 * pre-P3 flat result. The P2 collapse render is byte-identical for non-nested
 * canvases. `kind:"container"` members are not nodes → never a node→home entry
 * here (an inner container's hiding is the 3b container-render-filter's job).
 */
export function buildCollapsedMembership(
  containers: readonly WorkflowContainer[] | undefined,
): Map<string, string> {
  const membership = new Map<string, string>()
  if (!containers) return membership
  const parentMap = buildParentMap(containers)
  const containersById = new Map(containers.map((c) => [c.id, c] as const))
  for (const container of containers) {
    for (const member of container.members) {
      if (member.kind !== "node") continue
      const home = outermostCollapsedAncestor(
        member.id,
        parentMap,
        containersById,
      )
      if (home !== null) membership.set(member.id, home)
    }
  }
  return membership
}


// ─── classifyEdge ───────────────────────────────────────────────────

export type EdgeClassKind =
  | "interior"
  | "crossing-in"
  | "crossing-out"
  | "box-to-box"
  | "external"

export interface EdgeClassification {
  kind: EdgeClassKind
  /** The collapsed container the SOURCE is a hidden member of (when it is). */
  sourceContainerId?: string
  /** The collapsed container the TARGET is a hidden member of (when it is). */
  targetContainerId?: string
}

/**
 * Classify an edge against the collapsed-membership map (side-bucketed model):
 *   - both endpoints in the SAME collapsed container → "interior" (P2b hides)
 *   - both in DIFFERENT collapsed containers          → "box-to-box"
 *     (P2b reroutes boxA-bottom → boxB-top)
 *   - only the TARGET is a hidden member              → "crossing-in"
 *     (P2b reroutes the target to its box top)
 *   - only the SOURCE is a hidden member              → "crossing-out"
 *     (P2b reroutes the source from its box bottom)
 *   - neither                                          → "external" (unchanged)
 *
 * A member of a collapsed container connected to a member of an EXPANDED
 * container resolves as crossing (the expanded member isn't in the map → only
 * one endpoint is hidden), NOT box-to-box. Pure.
 */
export function classifyEdge(
  edge: { source: string; target: string },
  collapsedMembership: ReadonlyMap<string, string>,
): EdgeClassification {
  const sourceContainerId = collapsedMembership.get(edge.source)
  const targetContainerId = collapsedMembership.get(edge.target)
  if (sourceContainerId !== undefined && targetContainerId !== undefined) {
    return sourceContainerId === targetContainerId
      ? { kind: "interior", sourceContainerId, targetContainerId }
      : { kind: "box-to-box", sourceContainerId, targetContainerId }
  }
  if (targetContainerId !== undefined) {
    return { kind: "crossing-in", targetContainerId }
  }
  if (sourceContainerId !== undefined) {
    return { kind: "crossing-out", sourceContainerId }
  }
  return { kind: "external" }
}


// ─── collapsedBoxBounds ─────────────────────────────────────────────

/**
 * The bounds of a COLLAPSED container's box: position = the members' bbox
 * top-left (members' positions are still in canvas_state, just unrendered);
 * size = the FIXED `COLLAPSED_CONTAINER_WIDTH/HEIGHT` (NOT the member bbox
 * span — the box is a compact card, not the full footprint). No schema change
 * (no stored container position; draggable-when-collapsed is deferred).
 *
 * Degenerate input: a container with zero resolvable node-members → bbox's
 * empty branch yields (0,0), so this returns a (0,0)-positioned fixed box.
 * P2b never renders a zero-member container (it filters first, mirroring P1),
 * so this fallback keeps the function total without being visually used.
 */
export function collapsedBoxBounds(
  container: WorkflowContainer,
  nodes: readonly CanvasNode[],
  heightOf: (n: PositionedNode) => number = () => NODE_HEIGHT,
): BoxBounds {
  const memberNodes = container.members
    .filter((m) => m.kind === "node")
    .map((m) => nodes.find((n) => n.id === m.id))
    .filter((n): n is CanvasNode => n !== undefined)
  const b = bbox(memberNodes, NODE_WIDTH, heightOf)
  return {
    x: b.minX,
    y: b.minY,
    width: COLLAPSED_CONTAINER_WIDTH,
    height: COLLAPSED_CONTAINER_HEIGHT,
  }
}


// ─── containerBounds (Phase 3a — nested, recursive) ─────────────────

/**
 * The bounds of a container, nesting-aware. COLLAPSED → the fixed compact card
 * (`collapsedBoxBounds`; innards hidden, no recursion). EXPANDED → a frame
 * enclosing its member NODES' rects AND its member CONTAINERS' (recursive)
 * bounds, padded by `CONTAINER_EXPANDED_PADDING` — so an expanded outer box
 * encloses inner boxes (whether the inner is expanded [its own bbox] or
 * collapsed [its fixed card]).
 *
 * FLAT-CASE IDENTICAL: a container with only node-members + expanded produces
 * the SAME bounds as P1/P2's inline `bbox(memberNodes) ± padding` (3b swaps
 * that inline math for this helper). Cycle-safe: the validator proves a DAG,
 * and a defensive `_visited` set breaks any unvalidated cycle. Consumed by
 * NOTHING in 3a (tests only); 3b wires it into the render. Pure.
 */
export function containerBounds(
  container: WorkflowContainer,
  nodes: readonly CanvasNode[],
  containersById: ReadonlyMap<string, WorkflowContainer>,
  heightOf: (n: PositionedNode) => number = () => NODE_HEIGHT,
  _visited: Set<string> = new Set(),
): BoxBounds {
  if (container.collapsed) {
    return collapsedBoxBounds(container, nodes, heightOf)
  }
  // Defensive cycle break (validator guarantees a DAG; this guards against an
  // unvalidated hand-authored cycle so the recursion can't stack-overflow).
  if (_visited.has(container.id)) {
    return {
      x: 0,
      y: 0,
      width: COLLAPSED_CONTAINER_WIDTH,
      height: COLLAPSED_CONTAINER_HEIGHT,
    }
  }
  _visited.add(container.id)

  let minX = Infinity
  let minY = Infinity
  let maxX = -Infinity
  let maxY = -Infinity
  let any = false
  for (const member of container.members) {
    if (member.kind === "node") {
      const n = nodes.find((x) => x.id === member.id)
      if (!n) continue
      any = true
      minX = Math.min(minX, n.position.x)
      minY = Math.min(minY, n.position.y)
      maxX = Math.max(maxX, n.position.x + NODE_WIDTH)
      maxY = Math.max(maxY, n.position.y + heightOf(n))
    } else {
      const inner = containersById.get(member.id)
      if (!inner) continue
      const ib = containerBounds(
        inner,
        nodes,
        containersById,
        heightOf,
        _visited,
      )
      any = true
      minX = Math.min(minX, ib.x)
      minY = Math.min(minY, ib.y)
      maxX = Math.max(maxX, ib.x + ib.width)
      maxY = Math.max(maxY, ib.y + ib.height)
    }
  }
  // No resolvable members → degenerate fixed box (the render filters empty
  // containers, mirroring collapsedBoxBounds — never visually used).
  if (!any) {
    return {
      x: 0,
      y: 0,
      width: COLLAPSED_CONTAINER_WIDTH,
      height: COLLAPSED_CONTAINER_HEIGHT,
    }
  }
  return {
    x: minX - CONTAINER_EXPANDED_PADDING,
    y: minY - CONTAINER_EXPANDED_PADDING,
    width: maxX - minX + CONTAINER_EXPANDED_PADDING * 2,
    height: maxY - minY + CONTAINER_EXPANDED_PADDING * 2,
  }
}

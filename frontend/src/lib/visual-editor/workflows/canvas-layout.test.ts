/**
 * canvas-layout.test — Phase B sub-arc B-1 (Graph canvas foundation).
 *
 * Pure-function coverage for the workflow graph-canvas geometry helpers.
 * Per Q-40: pure-function shape keeps these unit-testable WITHOUT
 * dnd-kit pointer gestures (JSDOM weakness) — drag/edge math is fully
 * exercised here; pointer-drag DOM coverage defers to Playwright.
 */

import { describe, it, expect } from "vitest"

import {
  NODE_WIDTH,
  NODE_HEIGHT,
  CANVAS_MIN_WIDTH,
  CANVAS_MIN_HEIGHT,
  NODE_STACK_STRIDE_Y,
  NODE_DEFAULT_X,
  CANVAS_BBOX_PADDING,
  bbox,
  clampToCanvas,
  computeEdgePath,
  computeEdgeMidpoint,
  computeNodeDefaultPosition,
  computeNodeDragCommit,
  computeEdgePreviewPath,
  nodeAtPoint,
  dropDecision,
  type PositionedNode,
} from "./canvas-layout"
import type {
  CanvasNode,
  CanvasEdge,
} from "@/bridgeable-admin/services/workflow-templates-service"


function pnode(id: string, x: number, y: number): PositionedNode {
  return { id, position: { x, y } }
}

function cnode(id: string, x: number, y: number, type = "action"): CanvasNode {
  return { id, type, position: { x, y }, config: {} }
}


describe("canvas-layout — computeNodeDefaultPosition", () => {
  it("places the first node at the default origin (empty canvas)", () => {
    expect(computeNodeDefaultPosition([])).toEqual({ x: NODE_DEFAULT_X, y: 40 })
  })

  it("stacks a new node below the lowest existing node by the stride", () => {
    const nodes = [pnode("a", 0, 0), pnode("b", 0, 120), pnode("c", 0, 240)]
    expect(computeNodeDefaultPosition(nodes)).toEqual({
      x: NODE_DEFAULT_X,
      y: 240 + NODE_STACK_STRIDE_Y,
    })
  })

  it("uses the MAX y (not the last) so out-of-order positions still avoid overlap", () => {
    const nodes = [pnode("a", 0, 500), pnode("b", 0, 100)]
    expect(computeNodeDefaultPosition(nodes).y).toBe(500 + NODE_STACK_STRIDE_Y)
  })

  it("A3 grow-to-fit: with a heightOf, stacks below the lowest node's REAL bottom", () => {
    const nodes = [pnode("a", 0, 0), pnode("b", 0, 200)]
    // lowest bottom = 200 + 160; gap = STRIDE − NODE_HEIGHT (so a
    // default-height node yields the identical y as the no-resolver path).
    const out = computeNodeDefaultPosition(nodes, () => 160)
    expect(out.y).toBe(200 + 160 + (NODE_STACK_STRIDE_Y - NODE_HEIGHT))
  })

  it("A3 grow-to-fit: a default-height heightOf equals the no-resolver result", () => {
    const nodes = [pnode("a", 0, 0), pnode("b", 0, 240)]
    expect(computeNodeDefaultPosition(nodes, () => NODE_HEIGHT)).toEqual(
      computeNodeDefaultPosition(nodes),
    )
  })
})


describe("canvas-layout — clampToCanvas", () => {
  it("passes through an in-bounds position unchanged", () => {
    expect(clampToCanvas(100, 200, 1600, 1000)).toEqual({ x: 100, y: 200 })
  })

  it("clamps negative coordinates to 0", () => {
    expect(clampToCanvas(-50, -10, 1600, 1000)).toEqual({ x: 0, y: 0 })
  })

  it("clamps to canvas − node on the upper bound", () => {
    expect(clampToCanvas(5000, 5000, 1600, 1000)).toEqual({
      x: 1600 - NODE_WIDTH,
      y: 1000 - NODE_HEIGHT,
    })
  })

  it("collapses to 0 when node is larger than canvas (defensive)", () => {
    expect(clampToCanvas(10, 10, 50, 50, 200, 72)).toEqual({ x: 0, y: 0 })
  })
})


describe("canvas-layout — computeNodeDragCommit", () => {
  it("applies the drag delta to the current position", () => {
    const out = computeNodeDragCommit({
      currentX: 100,
      currentY: 100,
      dx: 50,
      dy: -30,
      canvasWidth: 1600,
      canvasHeight: 1000,
    })
    expect(out).toEqual({ x: 150, y: 70 })
  })

  it("clamps the committed position to canvas bounds (lower)", () => {
    const out = computeNodeDragCommit({
      currentX: 10,
      currentY: 10,
      dx: -100,
      dy: -100,
      canvasWidth: 1600,
      canvasHeight: 1000,
    })
    expect(out).toEqual({ x: 0, y: 0 })
  })

  it("clamps the committed position to canvas bounds (upper)", () => {
    const out = computeNodeDragCommit({
      currentX: 1500,
      currentY: 950,
      dx: 500,
      dy: 500,
      canvasWidth: 1600,
      canvasHeight: 1000,
    })
    expect(out).toEqual({ x: 1600 - NODE_WIDTH, y: 1000 - NODE_HEIGHT })
  })

  it("honors custom node dimensions in the clamp", () => {
    const out = computeNodeDragCommit({
      currentX: 0,
      currentY: 0,
      dx: 2000,
      dy: 0,
      canvasWidth: 1000,
      canvasHeight: 1000,
      nodeWidth: 300,
      nodeHeight: 100,
    })
    expect(out.x).toBe(1000 - 300)
  })
})


describe("canvas-layout — computeEdgePath", () => {
  it("departs source bottom-center and arrives target top-center", () => {
    const d = computeEdgePath({
      source: { x: 0, y: 0 },
      target: { x: 0, y: 200 },
    })
    // source bottom-center = (NODE_WIDTH/2, NODE_HEIGHT); target top-center = (NODE_WIDTH/2, 200)
    expect(d).toContain(`M ${NODE_WIDTH / 2} ${NODE_HEIGHT}`)
    expect(d.trimEnd().endsWith(`${NODE_WIDTH / 2} 200`)).toBe(true)
  })

  it("produces a cubic-bezier command (C) for the curve", () => {
    const d = computeEdgePath({
      source: { x: 0, y: 0 },
      target: { x: 400, y: 300 },
    })
    expect(d).toMatch(/^M [\d.]+ [\d.]+ C /)
  })

  it("handles a back-edge (target above source) without throwing", () => {
    const d = computeEdgePath({
      source: { x: 0, y: 400 },
      target: { x: 0, y: 0 },
    })
    expect(typeof d).toBe("string")
    expect(d.length).toBeGreaterThan(0)
  })

  it("A3 grow-to-fit: source bottom-anchor uses the injected (tall) source height", () => {
    const d = computeEdgePath({
      source: { x: 0, y: 0 },
      target: { x: 0, y: 400 },
      nodeHeight: 160, // a tall, measured source card (not NODE_HEIGHT 72)
    })
    // Departs at source.y + 160 — the REAL bottom of the tall source card.
    expect(d).toContain(`M ${NODE_WIDTH / 2} 160`)
    // Target top-anchor is height-independent (card top).
    expect(d.trimEnd().endsWith(`${NODE_WIDTH / 2} 400`)).toBe(true)
  })
})


describe("canvas-layout — computeEdgeMidpoint", () => {
  it("averages source bottom-center and target top-center", () => {
    const mid = computeEdgeMidpoint({
      source: { x: 0, y: 0 },
      target: { x: 0, y: 200 },
    })
    // sx=tx=NODE_WIDTH/2; sy=NODE_HEIGHT, ty=200 → mid.y = (72+200)/2
    expect(mid.x).toBe(NODE_WIDTH / 2)
    expect(mid.y).toBe((NODE_HEIGHT + 200) / 2)
  })

  it("A3 grow-to-fit: midpoint uses the injected source height for the source anchor", () => {
    const mid = computeEdgeMidpoint({
      source: { x: 0, y: 0 },
      target: { x: 0, y: 400 },
      nodeHeight: 160,
    })
    expect(mid.y).toBe((160 + 400) / 2)
  })
})


describe("canvas-layout — bbox", () => {
  it("returns the canvas minimum bounds for an empty graph", () => {
    expect(bbox([])).toEqual({
      minX: 0,
      minY: 0,
      maxX: CANVAS_MIN_WIDTH,
      maxY: CANVAS_MIN_HEIGHT,
      width: CANVAS_MIN_WIDTH,
      height: CANVAS_MIN_HEIGHT,
    })
  })

  it("keeps the canvas minimum when the graph fits within it", () => {
    const out = bbox([pnode("a", 100, 100)])
    expect(out.width).toBe(CANVAS_MIN_WIDTH)
    expect(out.height).toBe(CANVAS_MIN_HEIGHT)
    expect(out.maxX).toBe(100 + NODE_WIDTH)
    expect(out.maxY).toBe(100 + NODE_HEIGHT)
  })

  it("grows the canvas past the minimum when a node sits beyond it", () => {
    const farX = CANVAS_MIN_WIDTH + 500
    const out = bbox([pnode("a", farX, 0)])
    expect(out.width).toBe(farX + NODE_WIDTH + CANVAS_BBOX_PADDING)
  })

  it("A3 grow-to-fit: bounds a tall node via the injected heightOf resolver", () => {
    const tallY = CANVAS_MIN_HEIGHT + 100
    // Default heightOf would bound maxY = tallY + NODE_HEIGHT; the injected
    // 300 (a measured tall card) bounds the bottom higher.
    const out = bbox([pnode("a", 0, tallY)], NODE_WIDTH, () => 300)
    expect(out.maxY).toBe(tallY + 300)
    expect(out.height).toBe(tallY + 300 + CANVAS_BBOX_PADDING)
  })

  it("A3 grow-to-fit: default heightOf reproduces the fixed-height bound", () => {
    const out = bbox([pnode("a", 100, 100)], NODE_WIDTH)
    expect(out.maxY).toBe(100 + NODE_HEIGHT)
  })
})


// ─── Drag-to-connect geometry (P3b-1a) ──────────────────────────────

describe("canvas-layout — computeEdgePreviewPath", () => {
  it("anchors at source bottom-center; endpoint at the cursor world point", () => {
    // source (x=40,y=40), height 72 → bottom-center = (140, 112).
    const d = computeEdgePreviewPath({ x: 40, y: 40 }, NODE_HEIGHT, { x: 300, y: 500 })
    expect(d.startsWith("M 140 112 C")).toBe(true)
    // cubic bezier ends AT the cursor (300, 500).
    expect(d.endsWith("300 500")).toBe(true)
  })

  it("is height-aware (a tall source departs its real bottom, not y+72)", () => {
    const d = computeEdgePreviewPath({ x: 0, y: 0 }, 200, { x: 0, y: 400 })
    // bottom-center y = 0 + 200 = 200.
    expect(d.startsWith("M 100 200 C")).toBe(true)
  })

  it("emits a valid cubic-bezier path string (M … C …)", () => {
    const d = computeEdgePreviewPath({ x: 10, y: 10 }, NODE_HEIGHT, { x: 50, y: 90 })
    expect(d).toMatch(/^M [\d.-]+ [\d.-]+ C [\d.-]+ [\d.-]+, [\d.-]+ [\d.-]+, [\d.-]+ [\d.-]+$/)
  })
})


describe("canvas-layout — nodeAtPoint", () => {
  const nodes = [cnode("a", 0, 0), cnode("b", 0, 200)]
  const heights = new Map<string, number>()

  it("returns the node whose bbox contains the point", () => {
    // a spans x[0,200] y[0,72] (default height).
    expect(nodeAtPoint(nodes, heights, { x: 100, y: 36 })?.id).toBe("a")
    expect(nodeAtPoint(nodes, heights, { x: 100, y: 230 })?.id).toBe("b")
  })

  it("returns null for empty space", () => {
    expect(nodeAtPoint(nodes, heights, { x: 500, y: 500 })).toBeNull()
  })

  it("returns null in the gap between two stacked nodes", () => {
    // a bottom = 72; b top = 200 → y=120 is in the gap.
    expect(nodeAtPoint(nodes, heights, { x: 100, y: 120 })).toBeNull()
  })

  it("uses the measured height (a tall node's lower region hits)", () => {
    const tall = new Map<string, number>([["a", 300]])
    // a now spans y[0,300]; y=290 is in a's extended region and clear of b
    // (b spans y[200,272]). Without the measured height, y=290 would miss a
    // (default bottom 72); with it, a hits.
    expect(nodeAtPoint(nodes, tall, { x: 100, y: 290 })?.id).toBe("a")
  })

  it("overlap tie-break: the later-rendered (topmost) node wins", () => {
    const overlapping = [cnode("under", 0, 0), cnode("over", 10, 10)]
    // (50,50) is inside both; "over" is later in the array → topmost.
    expect(nodeAtPoint(overlapping, heights, { x: 50, y: 50 })?.id).toBe("over")
  })
})


describe("canvas-layout — dropDecision", () => {
  const nodes = [cnode("a", 0, 0), cnode("b", 0, 200), cnode("c", 0, 400)]
  const heights = new Map<string, number>()
  const inside = (id: "a" | "b" | "c") =>
    ({ a: { x: 100, y: 36 }, b: { x: 100, y: 236 }, c: { x: 100, y: 436 } })[id]

  it("cancel/empty when the drop lands on no node", () => {
    expect(
      dropDecision({ nodes, edges: [], heights, sourceId: "a", cursorWorld: { x: 900, y: 900 } }),
    ).toEqual({ action: "cancel", reason: "empty" })
  })

  it("cancel/self when the drop lands on the source node", () => {
    expect(
      dropDecision({ nodes, edges: [], heights, sourceId: "a", cursorWorld: inside("a") }),
    ).toEqual({ action: "cancel", reason: "self" })
  })

  it("cancel/duplicate when an edge source→target already exists", () => {
    const edges: CanvasEdge[] = [{ id: "e1", source: "a", target: "b" }]
    expect(
      dropDecision({ nodes, edges, heights, sourceId: "a", cursorWorld: inside("b") }),
    ).toEqual({ action: "cancel", reason: "duplicate" })
  })

  it("cancel/cycle when the candidate edge would create a cycle", () => {
    // a → b exists; dropping b → a closes a 2-cycle (validator throws).
    const edges: CanvasEdge[] = [{ id: "e1", source: "a", target: "b" }]
    expect(
      dropDecision({ nodes, edges, heights, sourceId: "b", cursorWorld: inside("a") }),
    ).toEqual({ action: "cancel", reason: "cycle" })
  })

  it("cancel/cycle for a self-loop attempt is caught as self FIRST (self precedes cycle)", () => {
    expect(
      dropDecision({ nodes, edges: [], heights, sourceId: "a", cursorWorld: inside("a") }).reason,
    ).toBe("self")
  })

  it("create/target for a valid acyclic, non-duplicate drop", () => {
    const edges: CanvasEdge[] = [{ id: "e1", source: "a", target: "b" }]
    // a → c is new, acyclic, non-duplicate.
    expect(
      dropDecision({ nodes, edges, heights, sourceId: "a", cursorWorld: inside("c") }),
    ).toEqual({ action: "create", target: "c" })
  })
})

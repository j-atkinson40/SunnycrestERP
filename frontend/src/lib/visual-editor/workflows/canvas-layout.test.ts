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
  // Container-arc Phase 2a — collapse/rerouting pure helpers (de-risk).
  COLLAPSED_CONTAINER_WIDTH,
  COLLAPSED_CONTAINER_HEIGHT,
  boxAnchor,
  bezierBetween,
  buildCollapsedMembership,
  classifyEdge,
  collapsedBoxBounds,
  // Container-arc Phase 3a — nested-container helpers.
  buildParentMap,
  outermostCollapsedAncestor,
  containerBounds,
  CONTAINER_EXPANDED_PADDING,
  type PositionedNode,
} from "./canvas-layout"
import type {
  CanvasNode,
  CanvasEdge,
  WorkflowContainer,
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
      originX: 0,
      originY: 0,
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

  // ── Negative-coordinate support ──
  it("BYTE-IDENTICAL guard: non-negative content yields origin (0,0)", () => {
    // Every node at x>=0,y>=0 → origin 0 → the whole offset is a no-op.
    const out = bbox([pnode("a", 0, 40), pnode("b", 500, 800)])
    expect(out.originX).toBe(0)
    expect(out.originY).toBe(0)
    // …and width/height are the pre-support `max(MIN, maxX/maxY + pad)`.
    expect(out.width).toBe(CANVAS_MIN_WIDTH) // 500+200+pad < MIN
  })

  it("a node entirely at non-negative x but minX>0 still yields originX 0 (no left-shift of positive canvases)", () => {
    const out = bbox([pnode("a", 500, 0)])
    expect(out.originX).toBe(0) // min(0, 500) = 0 — positive content is NOT shifted
  })

  it("negative content yields a negative origin = min(0, minX/minY)", () => {
    const out = bbox([pnode("a", -300, -120), pnode("b", 200, 400)])
    expect(out.originX).toBe(-300)
    expect(out.originY).toBe(-120)
    // The surface spans origin→max + padding: width = maxX - originX + pad.
    expect(out.width).toBe(Math.max(CANVAS_MIN_WIDTH, 200 + NODE_WIDTH - -300 + CANVAS_BBOX_PADDING))
  })
})

describe("canvas-layout — clampToCanvas negative lower bound", () => {
  it("default lower bound is 0 (byte-identical to pre-support)", () => {
    expect(clampToCanvas(-50, -10, 1600, 1000)).toEqual({ x: 0, y: 0 })
  })

  it("honors a negative lower bound (a node legitimately at negative coords isn't snapped to 0)", () => {
    // minX=-300, minY=-120: a node dragged toward -250 stays negative.
    expect(clampToCanvas(-250, -100, 1600, 1000, NODE_WIDTH, NODE_HEIGHT, -300, -120)).toEqual({
      x: -250,
      y: -100,
    })
    // …but still clamps below the (negative) origin.
    expect(clampToCanvas(-400, -200, 1600, 1000, NODE_WIDTH, NODE_HEIGHT, -300, -120)).toEqual({
      x: -300,
      y: -120,
    })
  })

  it("computeNodeDragCommit threads the minX/minY lower bound", () => {
    const out = computeNodeDragCommit({
      currentX: -300,
      currentY: 0,
      dx: 10,
      dy: 0,
      canvasWidth: 2000,
      canvasHeight: 1000,
      minX: -300,
      minY: -120,
    })
    expect(out.x).toBe(-290) // -300 + 10, not snapped to 0
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


// ── Container-arc Phase 2a — collapse/rerouting pure helpers ──────────

function container(
  id: string,
  memberNodeIds: string[],
  collapsed: boolean,
): WorkflowContainer {
  return {
    id,
    members: memberNodeIds.map((nid) => ({ kind: "node" as const, id: nid })),
    collapsed,
  }
}

describe("canvas-layout — boxAnchor", () => {
  it("top = (x + width/2, y)", () => {
    expect(boxAnchor({ x: 10, y: 20, width: 200, height: 64 }, "top")).toEqual({
      x: 110,
      y: 20,
    })
  })

  it("bottom = (x + width/2, y + height)", () => {
    expect(
      boxAnchor({ x: 10, y: 20, width: 200, height: 64 }, "bottom"),
    ).toEqual({ x: 110, y: 84 })
  })
})

describe("canvas-layout — bezierBetween", () => {
  it("reproduces the cubic-bezier curve between two points", () => {
    // ctrl = max(40, |400-72|/2) = 164. M sx sy C sx sy+ctrl, tx ty-ctrl, tx ty
    expect(bezierBetween({ x: 100, y: 72 }, { x: 100, y: 400 })).toBe(
      "M 100 72 C 100 236, 100 236, 100 400",
    )
  })

  it("floors the control offset at 40 for near-horizontal pairs", () => {
    // |10-0|/2 = 5 → floored to 40.
    expect(bezierBetween({ x: 0, y: 0 }, { x: 300, y: 10 })).toBe(
      "M 0 0 C 0 40, 300 -30, 300 10",
    )
  })
})

describe("canvas-layout — computeEdgePath refactor is OUTPUT-IDENTICAL", () => {
  // The Phase 2a decomposition (boxAnchor + bezierBetween) must reproduce the
  // exact prior node→node strings. These pin byte-identical output.
  it("node→node path matches the known string", () => {
    const d = computeEdgePath({ source: { x: 0, y: 0 }, target: { x: 0, y: 200 } })
    // sx=100 sy=72 tx=100 ty=200; ctrl=max(40,128/2)=64.
    expect(d).toBe("M 100 72 C 100 136, 100 136, 100 200")
  })

  it("respects an injected (tall) source height", () => {
    const d = computeEdgePath({
      source: { x: 0, y: 0 },
      target: { x: 0, y: 400 },
      nodeHeight: 160,
    })
    // sy=160; ctrl=max(40,240/2)=120.
    expect(d).toBe("M 100 160 C 100 280, 100 280, 100 400")
  })

  it("preview path (node→cursor) matches the known string", () => {
    const d = computeEdgePreviewPath({ x: 0, y: 0 }, NODE_HEIGHT, { x: 0, y: 400 })
    // sy=72; ctrl=max(40,328/2)=164.
    expect(d).toBe("M 100 72 C 100 236, 0 236, 0 400")
  })
})

describe("canvas-layout — buildCollapsedMembership", () => {
  it("maps members of a collapsed container to its id", () => {
    const m = buildCollapsedMembership([container("c1", ["n_a", "n_b"], true)])
    expect(m.get("n_a")).toBe("c1")
    expect(m.get("n_b")).toBe("c1")
    expect(m.size).toBe(2)
  })

  it("ignores EXPANDED containers (they hide nothing)", () => {
    const m = buildCollapsedMembership([container("c1", ["n_a"], false)])
    expect(m.has("n_a")).toBe(false)
    expect(m.size).toBe(0)
  })

  it("a node in no collapsed container is absent", () => {
    const m = buildCollapsedMembership([container("c1", ["n_a"], true)])
    expect(m.has("n_other")).toBe(false)
  })

  it("undefined / empty containers → empty map", () => {
    expect(buildCollapsedMembership(undefined).size).toBe(0)
    expect(buildCollapsedMembership([]).size).toBe(0)
  })

  it("skips kind:'container' members (flat — P2 produces none)", () => {
    const c: WorkflowContainer = {
      id: "c1",
      members: [
        { kind: "node", id: "n_a" },
        { kind: "container", id: "c_inner" },
      ],
      collapsed: true,
    }
    const m = buildCollapsedMembership([c])
    expect(m.get("n_a")).toBe("c1")
    expect(m.has("c_inner")).toBe(false)
    expect(m.size).toBe(1)
  })
})

describe("canvas-layout — classifyEdge", () => {
  const membership = buildCollapsedMembership([
    container("c1", ["n_a", "n_b"], true),
    container("c2", ["n_c"], true),
    container("c3", ["n_exp"], false), // expanded — members NOT hidden
  ])

  it("interior: both endpoints in the SAME collapsed container", () => {
    const r = classifyEdge({ source: "n_a", target: "n_b" }, membership)
    expect(r.kind).toBe("interior")
    expect(r.sourceContainerId).toBe("c1")
    expect(r.targetContainerId).toBe("c1")
  })

  it("box-to-box: endpoints in DIFFERENT collapsed containers", () => {
    const r = classifyEdge({ source: "n_a", target: "n_c" }, membership)
    expect(r.kind).toBe("box-to-box")
    expect(r.sourceContainerId).toBe("c1")
    expect(r.targetContainerId).toBe("c2")
  })

  it("crossing-in: only the TARGET is a hidden member", () => {
    const r = classifyEdge({ source: "n_out", target: "n_a" }, membership)
    expect(r.kind).toBe("crossing-in")
    expect(r.targetContainerId).toBe("c1")
    expect(r.sourceContainerId).toBeUndefined()
  })

  it("crossing-out: only the SOURCE is a hidden member", () => {
    const r = classifyEdge({ source: "n_a", target: "n_out" }, membership)
    expect(r.kind).toBe("crossing-out")
    expect(r.sourceContainerId).toBe("c1")
    expect(r.targetContainerId).toBeUndefined()
  })

  it("external: neither endpoint is a hidden member", () => {
    expect(classifyEdge({ source: "n_x", target: "n_y" }, membership).kind).toBe(
      "external",
    )
  })

  it("collapsed-A member → EXPANDED-B member = crossing (NOT box-to-box)", () => {
    // n_exp is in an expanded container → not in the collapsed-membership map,
    // so only one endpoint (n_a) is hidden → crossing-out.
    const r = classifyEdge({ source: "n_a", target: "n_exp" }, membership)
    expect(r.kind).toBe("crossing-out")
    expect(r.sourceContainerId).toBe("c1")
  })

  it("a self-contained collapsed container's edges are all interior", () => {
    const r = classifyEdge({ source: "n_a", target: "n_b" }, membership)
    expect(r.kind).toBe("interior")
  })
})

describe("canvas-layout — collapsedBoxBounds", () => {
  const nodes = [
    cnode("n_a", 100, 200),
    cnode("n_b", 400, 500),
    cnode("n_c", 50, 50),
  ]

  it("position = members' bbox top-left; size = the fixed collapsed dims", () => {
    const c = container("c1", ["n_a", "n_b"], true)
    const b = collapsedBoxBounds(c, nodes)
    expect(b).toEqual({
      x: 100, // min member x
      y: 200, // min member y
      width: COLLAPSED_CONTAINER_WIDTH,
      height: COLLAPSED_CONTAINER_HEIGHT,
    })
  })

  it("size is fixed regardless of how spread the members are", () => {
    const c = container("c1", ["n_a", "n_b", "n_c"], true)
    const b = collapsedBoxBounds(c, nodes)
    expect(b.width).toBe(COLLAPSED_CONTAINER_WIDTH)
    expect(b.height).toBe(COLLAPSED_CONTAINER_HEIGHT)
    expect(b.x).toBe(50) // min of 100/400/50
    expect(b.y).toBe(50)
  })

  it("empty-member container → degenerate (0,0) fixed box (P2b filters first)", () => {
    const c = container("c_empty", [], true)
    const b = collapsedBoxBounds(c, nodes)
    expect(b).toEqual({
      x: 0,
      y: 0,
      width: COLLAPSED_CONTAINER_WIDTH,
      height: COLLAPSED_CONTAINER_HEIGHT,
    })
  })
})


// ── Container-arc Phase 3a — nested-container helpers ─────────────────

// A container with mixed members (node + container) — flat `container()`
// above only builds node-members.
function nested(
  id: string,
  members: Array<{ kind: "node" | "container"; id: string }>,
  collapsed: boolean,
): WorkflowContainer {
  return { id, members, collapsed }
}

describe("canvas-layout — buildParentMap", () => {
  it("maps node-members AND container-members to their parent container", () => {
    const containers = [
      nested("A", [{ kind: "container", id: "B" }, { kind: "node", id: "n_x" }], false),
      nested("B", [{ kind: "node", id: "n_y" }], false),
    ]
    const p = buildParentMap(containers)
    expect(p.get("B")).toBe("A") // container-member → parent
    expect(p.get("n_x")).toBe("A") // node-member → parent
    expect(p.get("n_y")).toBe("B")
  })

  it("a top-level container (member of nothing) is absent", () => {
    const p = buildParentMap([nested("A", [{ kind: "node", id: "n_x" }], false)])
    expect(p.has("A")).toBe(false)
  })

  it("undefined / empty → empty map", () => {
    expect(buildParentMap(undefined).size).toBe(0)
    expect(buildParentMap([]).size).toBe(0)
  })
})

describe("canvas-layout — outermostCollapsedAncestor", () => {
  // A ⊃ B ⊃ N (A contains B, B contains node n).
  function chain(aCollapsed: boolean, bCollapsed: boolean) {
    const containers = [
      nested("A", [{ kind: "container", id: "B" }], aCollapsed),
      nested("B", [{ kind: "node", id: "n" }], bCollapsed),
    ]
    return {
      parentMap: buildParentMap(containers),
      containersById: new Map(containers.map((c) => [c.id, c] as const)),
    }
  }

  it("A collapsed → A (outermost wins, even if B is too)", () => {
    const { parentMap, containersById } = chain(true, true)
    expect(outermostCollapsedAncestor("n", parentMap, containersById)).toBe("A")
  })

  it("A collapsed, B expanded → A", () => {
    const { parentMap, containersById } = chain(true, false)
    expect(outermostCollapsedAncestor("n", parentMap, containersById)).toBe("A")
  })

  it("only B collapsed → B (the inner collapsed home)", () => {
    const { parentMap, containersById } = chain(false, true)
    expect(outermostCollapsedAncestor("n", parentMap, containersById)).toBe("B")
  })

  it("neither collapsed → null", () => {
    const { parentMap, containersById } = chain(false, false)
    expect(outermostCollapsedAncestor("n", parentMap, containersById)).toBeNull()
  })

  it("a node with no ancestors → null", () => {
    expect(
      outermostCollapsedAncestor("orphan", new Map(), new Map()),
    ).toBeNull()
  })

  it("terminates safely on a cyclic parent map (defensive visited-set)", () => {
    // Malformed (the validator would reject this) — A→B→A. Must not loop.
    const parentMap = new Map([
      ["A", "B"],
      ["B", "A"],
    ])
    const containersById = new Map([
      ["A", nested("A", [], false)],
      ["B", nested("B", [], false)],
    ])
    expect(
      outermostCollapsedAncestor("A", parentMap, containersById),
    ).toBeNull()
  })
})

describe("canvas-layout — buildCollapsedMembership (nesting-aware)", () => {
  // The FLAT-case tests above (the prior describe) are the regression guard —
  // they must stay green unchanged. These add the nested cases.
  it("a node hidden in a COLLAPSED OUTER (expanded inner) maps to the OUTER", () => {
    const containers = [
      nested("A", [{ kind: "container", id: "B" }], true), // outer collapsed
      nested("B", [{ kind: "node", id: "n" }], false), // inner expanded
    ]
    const m = buildCollapsedMembership(containers)
    expect(m.get("n")).toBe("A")
  })

  it("a node hidden in only a COLLAPSED INNER (expanded outer) maps to the INNER", () => {
    const containers = [
      nested("A", [{ kind: "container", id: "B" }], false), // outer expanded
      nested("B", [{ kind: "node", id: "n" }], true), // inner collapsed
    ]
    const m = buildCollapsedMembership(containers)
    expect(m.get("n")).toBe("B")
  })

  it("neither collapsed → the node is not hidden (absent)", () => {
    const containers = [
      nested("A", [{ kind: "container", id: "B" }], false),
      nested("B", [{ kind: "node", id: "n" }], false),
    ]
    expect(buildCollapsedMembership(containers).has("n")).toBe(false)
  })
})

describe("canvas-layout — containerBounds (recursive)", () => {
  const nodes = [cnode("n_x", 100, 100), cnode("n_y", 400, 500)]

  it("collapsed → the fixed compact card (delegates to collapsedBoxBounds)", () => {
    const b = containerBounds(
      nested("A", [{ kind: "node", id: "n_x" }], true),
      nodes,
      new Map(),
    )
    expect(b.width).toBe(COLLAPSED_CONTAINER_WIDTH)
    expect(b.height).toBe(COLLAPSED_CONTAINER_HEIGHT)
  })

  it("expanded node-only → bbox over node rects + padding (flat-identical)", () => {
    const b = containerBounds(
      nested("A", [{ kind: "node", id: "n_x" }, { kind: "node", id: "n_y" }], false),
      nodes,
      new Map(),
    )
    // minX=100,minY=100; maxX=400+200=600, maxY=500+72=572.
    expect(b.x).toBe(100 - CONTAINER_EXPANDED_PADDING)
    expect(b.y).toBe(100 - CONTAINER_EXPANDED_PADDING)
    expect(b.width).toBe(600 - 100 + CONTAINER_EXPANDED_PADDING * 2)
    expect(b.height).toBe(572 - 100 + CONTAINER_EXPANDED_PADDING * 2)
  })

  it("expanded outer ENCLOSES an expanded inner container's bounds", () => {
    const A = nested("A", [{ kind: "container", id: "B" }, { kind: "node", id: "n_x" }], false)
    const B = nested("B", [{ kind: "node", id: "n_y" }], false)
    const containersById = new Map([["A", A], ["B", B]] as const)
    const inner = containerBounds(B, nodes, containersById)
    const outer = containerBounds(A, nodes, containersById)
    // The outer frame fully contains the inner frame.
    expect(outer.x).toBeLessThanOrEqual(inner.x)
    expect(outer.y).toBeLessThanOrEqual(inner.y)
    expect(outer.x + outer.width).toBeGreaterThanOrEqual(inner.x + inner.width)
    expect(outer.y + outer.height).toBeGreaterThanOrEqual(inner.y + inner.height)
  })

  it("expanded outer encloses a COLLAPSED inner's fixed card", () => {
    const A = nested("A", [{ kind: "container", id: "B" }], false)
    const B = nested("B", [{ kind: "node", id: "n_y" }], true) // collapsed inner
    const containersById = new Map([["A", A], ["B", B]] as const)
    const inner = containerBounds(B, nodes, containersById)
    const outer = containerBounds(A, nodes, containersById)
    expect(inner.width).toBe(COLLAPSED_CONTAINER_WIDTH)
    expect(outer.width).toBeGreaterThanOrEqual(inner.width)
    expect(outer.x + outer.width).toBeGreaterThanOrEqual(inner.x + inner.width)
  })
})

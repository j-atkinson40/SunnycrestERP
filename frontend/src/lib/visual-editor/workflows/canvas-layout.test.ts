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
  type PositionedNode,
} from "./canvas-layout"


function pnode(id: string, x: number, y: number): PositionedNode {
  return { id, position: { x, y } }
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
})

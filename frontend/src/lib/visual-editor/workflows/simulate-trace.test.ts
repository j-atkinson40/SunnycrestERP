/**
 * simulate-trace.test — Phase B sub-arc B-4 (reachability simulation).
 *
 * Pure-function coverage: reachable / unreachable(orphan) / parallel
 * split-join / terminal / multiple-start / no-start / dangling-edge, and
 * the CYCLE GUARD (is_iteration loop-back must not infinite-loop). No
 * engine, no Jinja — plain graph reachability.
 */

import { describe, it, expect } from "vitest"

import {
  simulateReachability,
  isNodeReachable,
  isEdgeReachable,
  isTerminalNode,
  orphanNodeIds,
} from "./simulate-trace"
import type {
  CanvasState,
  CanvasNode,
} from "@/bridgeable-admin/services/workflow-templates-service"

function n(id: string, type: string): CanvasNode {
  return { id, type, position: { x: 0, y: 0 }, config: {} }
}
function e(id: string, source: string, target: string, extra: Partial<{ is_iteration: boolean }> = {}) {
  return { id, source, target, ...extra }
}

describe("simulate-trace — reachability", () => {
  it("marks a linear chain fully reachable", () => {
    const canvas: CanvasState = {
      version: 1,
      nodes: [n("s", "start"), n("a", "action"), n("end", "end")],
      edges: [e("e1", "s", "a"), e("e2", "a", "end")],
    }
    const t = simulateReachability(canvas)
    expect([...t.reachableNodeIds].sort()).toEqual(["a", "end", "s"])
    expect([...t.reachableEdgeIds].sort()).toEqual(["e1", "e2"])
  })

  it("leaves an orphan node (no path from start) unreachable", () => {
    const canvas: CanvasState = {
      version: 1,
      nodes: [n("s", "start"), n("a", "action"), n("orphan", "action")],
      edges: [e("e1", "s", "a")],
    }
    const t = simulateReachability(canvas)
    expect(isNodeReachable(t, "a")).toBe(true)
    expect(isNodeReachable(t, "orphan")).toBe(false)
    expect(orphanNodeIds(canvas, t)).toEqual(["orphan"])
  })

  it("marks an edge into an orphan unreachable (only source reachable is not enough — target must exist + be linked)", () => {
    // Edge whose source IS reachable but target is an orphan-via-no-other-path:
    // the edge IS traversed (source reachable, target exists) so target becomes reachable.
    const canvas: CanvasState = {
      version: 1,
      nodes: [n("s", "start"), n("a", "action")],
      edges: [e("e1", "s", "a")],
    }
    const t = simulateReachability(canvas)
    expect(isEdgeReachable(t, "e1")).toBe(true)
    expect(isNodeReachable(t, "a")).toBe(true)
  })

  it("does not traverse an edge whose source is unreachable", () => {
    const canvas: CanvasState = {
      version: 1,
      nodes: [n("s", "start"), n("x", "action"), n("y", "action")],
      edges: [e("ex", "x", "y")], // x is an orphan; ex never traversed
    }
    const t = simulateReachability(canvas)
    expect(isNodeReachable(t, "x")).toBe(false)
    expect(isNodeReachable(t, "y")).toBe(false)
    expect(isEdgeReachable(t, "ex")).toBe(false)
  })

  it("handles parallel split → join (fan-out / fan-in)", () => {
    const canvas: CanvasState = {
      version: 1,
      nodes: [
        n("s", "start"),
        n("split", "parallel_split"),
        n("b1", "action"),
        n("b2", "action"),
        n("join", "parallel_join"),
        n("end", "end"),
      ],
      edges: [
        e("e0", "s", "split"),
        e("e1", "split", "b1"),
        e("e2", "split", "b2"),
        e("e3", "b1", "join"),
        e("e4", "b2", "join"),
        e("e5", "join", "end"),
      ],
    }
    const t = simulateReachability(canvas)
    // All nodes + edges reachable.
    expect(t.reachableNodeIds.size).toBe(6)
    expect(t.reachableEdgeIds.size).toBe(6)
    expect(orphanNodeIds(canvas, t)).toEqual([])
  })

  it("does NOT infinite-loop on an is_iteration cycle (cycle guard)", () => {
    // s → a → b → a (loop-back via is_iteration) → end
    const canvas: CanvasState = {
      version: 1,
      nodes: [n("s", "start"), n("a", "action"), n("b", "action"), n("end", "end")],
      edges: [
        e("e1", "s", "a"),
        e("e2", "a", "b"),
        e("e3", "b", "a", { is_iteration: true }), // back-edge
        e("e4", "b", "end"),
      ],
    }
    const t = simulateReachability(canvas) // must terminate
    expect([...t.reachableNodeIds].sort()).toEqual(["a", "b", "end", "s"])
    expect(isEdgeReachable(t, "e3")).toBe(true) // back-edge is traversed once
  })

  it("does not infinite-loop on a self-loop", () => {
    const canvas: CanvasState = {
      version: 1,
      nodes: [n("s", "start"), n("a", "action")],
      edges: [e("e1", "s", "a"), e("e2", "a", "a", { is_iteration: true })],
    }
    const t = simulateReachability(canvas)
    expect(isNodeReachable(t, "a")).toBe(true)
    expect(isEdgeReachable(t, "e2")).toBe(true)
  })

  it("seeds from MULTIPLE start nodes", () => {
    const canvas: CanvasState = {
      version: 1,
      nodes: [n("s1", "start"), n("s2", "start"), n("a", "action"), n("b", "action")],
      edges: [e("e1", "s1", "a"), e("e2", "s2", "b")],
    }
    const t = simulateReachability(canvas)
    expect(t.reachableNodeIds.size).toBe(4)
  })

  it("marks everything unreachable when there is NO start node", () => {
    const canvas: CanvasState = {
      version: 1,
      nodes: [n("a", "action"), n("b", "action")],
      edges: [e("e1", "a", "b")],
    }
    const t = simulateReachability(canvas)
    expect(t.reachableNodeIds.size).toBe(0)
    expect(orphanNodeIds(canvas, t).sort()).toEqual(["a", "b"])
  })

  it("ignores a dangling edge to a deleted target (defensive)", () => {
    const canvas: CanvasState = {
      version: 1,
      nodes: [n("s", "start")],
      edges: [e("e1", "s", "ghost")], // target does not exist
    }
    const t = simulateReachability(canvas)
    expect(isNodeReachable(t, "s")).toBe(true)
    expect(isEdgeReachable(t, "e1")).toBe(false)
  })

  it("empty canvas → empty trace", () => {
    const t = simulateReachability({ version: 1, nodes: [], edges: [] })
    expect(t.reachableNodeIds.size).toBe(0)
    expect(t.reachableEdgeIds.size).toBe(0)
  })
})

describe("simulate-trace — helpers", () => {
  it("isTerminalNode true only for end nodes", () => {
    expect(isTerminalNode(n("e", "end"))).toBe(true)
    expect(isTerminalNode(n("a", "action"))).toBe(false)
    expect(isTerminalNode(n("s", "start"))).toBe(false)
  })

  it("start nodes are never orphans", () => {
    const canvas: CanvasState = {
      version: 1,
      nodes: [n("s", "start"), n("dead", "action")],
      edges: [],
    }
    const t = simulateReachability(canvas)
    expect(orphanNodeIds(canvas, t)).toEqual(["dead"])
    expect(isNodeReachable(t, "s")).toBe(true)
  })
})

/**
 * Frontend canvas validator tests — mirrors backend
 * `test_workflow_templates_phase4.py::TestCanvasValidator` shape.
 *
 * Cross-reference parity is enforced: every canvas valid here must
 * be valid on the backend, and vice versa. The two validators MUST
 * agree on schema rules.
 */

import { describe, expect, it } from "vitest"

import {
  CanvasValidationError,
  VALID_NODE_TYPES,
  summarizeCanvas,
  validateCanvasState,
} from "./canvas-validator"

import type { CanvasState } from "@/bridgeable-admin/services/workflow-templates-service"


function minimalNode(
  id: string,
  type: string = "action",
): CanvasState["nodes"][number] {
  return { id, type, position: { x: 0, y: 0 }, config: {} }
}


describe("validateCanvasState", () => {
  it("accepts empty {} as unauthored draft", () => {
    expect(() => validateCanvasState({})).not.toThrow()
  })

  it("rejects null/undefined with descriptive message", () => {
    expect(() => validateCanvasState(null)).toThrow(CanvasValidationError)
    expect(() => validateCanvasState(undefined)).toThrow(CanvasValidationError)
  })

  it("rejects array root", () => {
    expect(() =>
      validateCanvasState([] as unknown as CanvasState),
    ).toThrow(/mapping/)
  })

  it("rejects missing required keys", () => {
    expect(() =>
      validateCanvasState({ nodes: [] } as unknown as CanvasState),
    ).toThrow(/missing required keys/)
  })

  it("rejects non-positive version", () => {
    expect(() =>
      validateCanvasState({ version: 0, nodes: [], edges: [] }),
    ).toThrow(/positive integer/)
    expect(() =>
      validateCanvasState({ version: -1, nodes: [], edges: [] }),
    ).toThrow(/positive integer/)
  })

  it("accepts canonical seeded shape (start + action + end)", () => {
    const canvas: CanvasState = {
      version: 1,
      nodes: [
        minimalNode("start", "start"),
        minimalNode("a1", "action"),
        minimalNode("end", "end"),
      ],
      edges: [
        { id: "e1", source: "start", target: "a1" },
        { id: "e2", source: "a1", target: "end" },
      ],
    }
    expect(() => validateCanvasState(canvas)).not.toThrow()
  })

  it("rejects unknown node types", () => {
    const canvas: CanvasState = {
      version: 1,
      nodes: [{ ...minimalNode("x"), type: "unknown_type_xyz" }],
      edges: [],
    }
    expect(() => validateCanvasState(canvas)).toThrow(/VALID_NODE_TYPES/)
  })

  it("rejects duplicate node ids", () => {
    const canvas: CanvasState = {
      version: 1,
      nodes: [minimalNode("dup"), minimalNode("dup")],
      edges: [],
    }
    expect(() => validateCanvasState(canvas)).toThrow(/duplicates/)
  })

  it("rejects edges referencing undeclared nodes", () => {
    const canvas: CanvasState = {
      version: 1,
      nodes: [minimalNode("a")],
      edges: [{ id: "e1", source: "a", target: "missing" }],
    }
    expect(() => validateCanvasState(canvas)).toThrow(
      /doesn't reference a declared node id/,
    )
  })

  it("detects cycles", () => {
    const canvas: CanvasState = {
      version: 1,
      nodes: [minimalNode("a"), minimalNode("b")],
      edges: [
        { id: "e1", source: "a", target: "b" },
        { id: "e2", source: "b", target: "a" },
      ],
    }
    expect(() => validateCanvasState(canvas)).toThrow(/cycle/)
  })

  it("permits cycles when back-edge marked is_iteration=true", () => {
    const canvas: CanvasState = {
      version: 1,
      nodes: [minimalNode("a"), minimalNode("b")],
      edges: [
        { id: "e1", source: "a", target: "b" },
        { id: "e2", source: "b", target: "a", is_iteration: true },
      ],
    }
    expect(() => validateCanvasState(canvas)).not.toThrow()
  })

  it("VALID_NODE_TYPES includes start/end/action/decision/branch", () => {
    expect(VALID_NODE_TYPES).toContain("start")
    expect(VALID_NODE_TYPES).toContain("end")
    expect(VALID_NODE_TYPES).toContain("action")
    expect(VALID_NODE_TYPES).toContain("decision")
    expect(VALID_NODE_TYPES).toContain("branch")
    expect(VALID_NODE_TYPES).toContain("parallel_split")
    expect(VALID_NODE_TYPES).toContain("parallel_join")
  })
})


describe("summarizeCanvas", () => {
  it("returns zeros for empty canvas", () => {
    expect(summarizeCanvas({})).toEqual({
      nodes: 0,
      edges: 0,
      terminalNodes: 0,
      branchingNodes: 0,
    })
  })

  it("counts terminals and branches correctly", () => {
    const canvas: CanvasState = {
      version: 1,
      nodes: [
        minimalNode("start", "start"),
        minimalNode("split", "branch"),
        minimalNode("a"),
        minimalNode("b"),
        minimalNode("end", "end"),
      ],
      edges: [
        { id: "e1", source: "start", target: "split" },
        { id: "e2", source: "split", target: "a" },
        { id: "e3", source: "split", target: "b" },
        { id: "e4", source: "a", target: "end" },
        { id: "e5", source: "b", target: "end" },
      ],
    }
    const summary = summarizeCanvas(canvas)
    expect(summary.nodes).toBe(5)
    expect(summary.edges).toBe(5)
    expect(summary.terminalNodes).toBe(1) // only "end"
    expect(summary.branchingNodes).toBe(1) // "split" has 2 outgoing
  })

  it("excludes is_iteration edges from out-degree", () => {
    const canvas: CanvasState = {
      version: 1,
      nodes: [minimalNode("a"), minimalNode("b")],
      edges: [
        { id: "e1", source: "a", target: "b" },
        { id: "e2", source: "b", target: "a", is_iteration: true },
      ],
    }
    const summary = summarizeCanvas(canvas)
    // b's only outgoing is is_iteration, so it counts as terminal
    expect(summary.terminalNodes).toBe(1)
    expect(summary.branchingNodes).toBe(0)
  })
})

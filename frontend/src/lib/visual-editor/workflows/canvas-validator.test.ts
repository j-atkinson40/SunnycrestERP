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


// ── Container-arc Phase 1 — `containers` overlay validation ───────────
// Lockstep with backend test_workflow_templates_phase4.py::TestCanvasValidator
// container cases. Every canvas valid here must be valid on the backend.

describe("validateCanvasState — containers overlay", () => {
  function base(containers: unknown): CanvasState {
    return {
      version: 1,
      nodes: [minimalNode("n_a"), minimalNode("n_b")],
      edges: [],
      // cast — some tests pass deliberately-malformed shapes
      containers: containers as CanvasState["containers"],
    }
  }

  it("accepts a canvas with no containers field (back-compat)", () => {
    expect(() =>
      validateCanvasState({ version: 1, nodes: [minimalNode("n_a")], edges: [] }),
    ).not.toThrow()
  })

  it("accepts a valid flat container (node members reference declared nodes)", () => {
    expect(() =>
      validateCanvasState(
        base([
          {
            id: "c_1",
            label: "Group",
            members: [
              { kind: "node", id: "n_a" },
              { kind: "node", id: "n_b" },
            ],
            collapsed: false,
          },
        ]),
      ),
    ).not.toThrow()
  })

  it("accepts an empty member-list container", () => {
    expect(() =>
      validateCanvasState(base([{ id: "c_1", members: [], collapsed: false }])),
    ).not.toThrow()
  })

  it("rejects an orphan node-member (id not a declared node)", () => {
    expect(() =>
      validateCanvasState(
        base([
          { id: "c_1", members: [{ kind: "node", id: "n_ghost" }], collapsed: false },
        ]),
      ),
    ).toThrow(/doesn't reference a declared node id/)
  })

  it("rejects a node appearing in two containers", () => {
    expect(() =>
      validateCanvasState(
        base([
          { id: "c_1", members: [{ kind: "node", id: "n_a" }], collapsed: false },
          { id: "c_2", members: [{ kind: "node", id: "n_a" }], collapsed: false },
        ]),
      ),
    ).toThrow(/more than one container/)
  })

  it("rejects duplicate container ids", () => {
    expect(() =>
      validateCanvasState(
        base([
          { id: "c_1", members: [], collapsed: false },
          { id: "c_1", members: [], collapsed: false },
        ]),
      ),
    ).toThrow(/duplicates an earlier container/)
  })

  it("rejects a non-boolean collapsed", () => {
    expect(() =>
      validateCanvasState(
        base([{ id: "c_1", members: [], collapsed: "no" }]),
      ),
    ).toThrow(/collapsed must be a boolean/)
  })

  it("rejects a bad member kind", () => {
    expect(() =>
      validateCanvasState(
        base([{ id: "c_1", members: [{ kind: "widget", id: "n_a" }], collapsed: false }]),
      ),
    ).toThrow(/kind must be/)
  })

  it("rejects a non-array containers", () => {
    expect(() => validateCanvasState(base({}))).toThrow(/must be an array/)
  })

  it("accepts kind:'container' members without ref-checking (nesting-ready, P3 validates)", () => {
    // P1 produces no container-members, but the discriminated shape is
    // type-allowed; ref-integrity + nesting-cycle detection is a Phase 3 add.
    expect(() =>
      validateCanvasState(
        base([
          { id: "c_outer", members: [{ kind: "container", id: "c_inner" }], collapsed: false },
        ]),
      ),
    ).not.toThrow()
  })
})

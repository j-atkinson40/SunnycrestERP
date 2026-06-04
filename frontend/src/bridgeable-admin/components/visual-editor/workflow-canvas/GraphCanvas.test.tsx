/**
 * GraphCanvas.test — Phase B sub-arc B-1 (Graph canvas foundation).
 *
 * Render coverage for the directed-graph authoring canvas. Per Q-40,
 * operator-observable assertions target rendered DOM (node cards at
 * inline-style positions, SVG edge paths) + the preserved test anchors.
 * Pointer-drag gestures defer to Playwright; node-move COMMIT math is
 * covered in `canvas-layout.test.ts`. Here we drive selection + removal
 * (non-drag affordances) directly.
 */

import { describe, it, expect, vi } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"

// P2a — clickable sentence tokens resolve their schema via the registry
// (the editable gate + popover editor); populate it.
import "@/lib/visual-editor/registry/auto-register"
import { GraphCanvas } from "./GraphCanvas"
import type { CanvasState } from "@/bridgeable-admin/services/workflow-templates-service"


function makeCanvas(overrides: Partial<CanvasState> = {}): CanvasState {
  return {
    version: 1,
    nodes: [
      { id: "n_node_1", type: "start", label: "Begin", position: { x: 40, y: 40 }, config: {} },
      { id: "n_node_2", type: "action", label: "Do work", position: { x: 40, y: 200 }, config: {} },
    ],
    edges: [{ id: "e_n_node_1_n_node_2", source: "n_node_1", target: "n_node_2" }],
    ...overrides,
  }
}

const noop = () => {}


describe("GraphCanvas — empty + validation", () => {
  it("renders the empty-state when no nodes", () => {
    render(
      <GraphCanvas
        canvas={{ version: 1, nodes: [], edges: [] }}
        selectedNodeId={null}
        onSelectNode={noop}
        onMoveNode={noop}
        onRemoveNode={noop}
      />,
    )
    expect(screen.getByTestId("canvas-node-list")).toBeInTheDocument()
    expect(screen.getByText(/No nodes yet/i)).toBeInTheDocument()
    // No graph surface when empty.
    expect(screen.queryByTestId("graph-canvas-surface")).not.toBeInTheDocument()
  })

  it("renders the validation banner when validationError is set", () => {
    render(
      <GraphCanvas
        canvas={{ version: 1, nodes: [], edges: [] }}
        selectedNodeId={null}
        onSelectNode={noop}
        onMoveNode={noop}
        onRemoveNode={noop}
        validationError="Node n_x references unknown target"
      />,
    )
    const banner = screen.getByTestId("canvas-validation-message")
    expect(banner).toHaveTextContent(/references unknown target/i)
  })

  it("does NOT render the validation banner when validationError is null", () => {
    render(
      <GraphCanvas
        canvas={makeCanvas()}
        selectedNodeId={null}
        onSelectNode={noop}
        onMoveNode={noop}
        onRemoveNode={noop}
        validationError={null}
      />,
    )
    expect(screen.queryByTestId("canvas-validation-message")).not.toBeInTheDocument()
  })
})


describe("GraphCanvas — node rendering", () => {
  it("renders a draggable card per node with preserved test anchors", () => {
    render(
      <GraphCanvas
        canvas={makeCanvas()}
        selectedNodeId={null}
        onSelectNode={noop}
        onMoveNode={noop}
        onRemoveNode={noop}
      />,
    )
    const n1 = screen.getByTestId("canvas-node-n_node_1")
    const n2 = screen.getByTestId("canvas-node-n_node_2")
    expect(n1).toHaveAttribute("data-node-type", "start")
    expect(n2).toHaveAttribute("data-node-type", "action")
  })

  it("positions node cards at their canvas_state position via inline style", () => {
    render(
      <GraphCanvas
        canvas={makeCanvas()}
        selectedNodeId={null}
        onSelectNode={noop}
        onMoveNode={noop}
        onRemoveNode={noop}
      />,
    )
    const n2 = screen.getByTestId("canvas-node-n_node_2")
    // position {x:40, y:200} → left:40px; top:200px
    expect(n2.style.left).toBe("40px")
    expect(n2.style.top).toBe("200px")
  })

  it("marks the selected node via data-selected", () => {
    render(
      <GraphCanvas
        canvas={makeCanvas()}
        selectedNodeId="n_node_2"
        onSelectNode={noop}
        onMoveNode={noop}
        onRemoveNode={noop}
      />,
    )
    expect(screen.getByTestId("canvas-node-n_node_1")).toHaveAttribute("data-selected", "false")
    expect(screen.getByTestId("canvas-node-n_node_2")).toHaveAttribute("data-selected", "true")
  })

  it("renders the plain-language label; the n_ node-ID is NOT shown (A3 grow-to-fit)", () => {
    render(
      <GraphCanvas
        canvas={makeCanvas()}
        selectedNodeId={null}
        onSelectNode={noop}
        onMoveNode={noop}
        onRemoveNode={noop}
      />,
    )
    expect(screen.getByText("Begin")).toBeInTheDocument()
    // The n_ technical ID is dropped from the card (Shortcuts-like,
    // plain-language only). It survives as the testid + React key.
    expect(screen.queryByText("n_node_1")).toBeNull()
    expect(screen.getByTestId("canvas-node-n_node_1")).toBeInTheDocument()
  })
})


describe("GraphCanvas — edge rendering", () => {
  it("renders an SVG path per edge with the edge test anchor", () => {
    render(
      <GraphCanvas
        canvas={makeCanvas()}
        selectedNodeId={null}
        onSelectNode={noop}
        onMoveNode={noop}
        onRemoveNode={noop}
      />,
    )
    const edgeGroup = screen.getByTestId("edge-e_n_node_1_n_node_2")
    expect(edgeGroup).toBeInTheDocument()
    expect(edgeGroup.querySelector("path")).toBeInTheDocument()
  })

  it("renders multi-edge fan-out (branching) as N paths from one source", () => {
    const canvas: CanvasState = {
      version: 1,
      nodes: [
        { id: "d", type: "decision", position: { x: 40, y: 40 }, config: {} },
        { id: "a", type: "action", position: { x: 40, y: 200 }, config: {} },
        { id: "b", type: "action", position: { x: 300, y: 200 }, config: {} },
      ],
      edges: [
        { id: "e_d_a", source: "d", target: "a", condition: "approved" },
        { id: "e_d_b", source: "d", target: "b", condition: "rejected" },
      ],
    }
    render(
      <GraphCanvas
        canvas={canvas}
        selectedNodeId={null}
        onSelectNode={noop}
        onMoveNode={noop}
        onRemoveNode={noop}
      />,
    )
    expect(screen.getByTestId("edge-e_d_a")).toBeInTheDocument()
    expect(screen.getByTestId("edge-e_d_b")).toBeInTheDocument()
    // Condition rendered as edge label text.
    expect(screen.getByText("approved")).toBeInTheDocument()
    expect(screen.getByText("rejected")).toBeInTheDocument()
  })

  it("skips an edge whose source/target node is missing (defensive)", () => {
    const canvas: CanvasState = {
      version: 1,
      nodes: [{ id: "a", type: "start", position: { x: 0, y: 0 }, config: {} }],
      edges: [{ id: "e_dangling", source: "a", target: "ghost" }],
    }
    render(
      <GraphCanvas
        canvas={canvas}
        selectedNodeId={null}
        onSelectNode={noop}
        onMoveNode={noop}
        onRemoveNode={noop}
      />,
    )
    expect(screen.queryByTestId("edge-e_dangling")).not.toBeInTheDocument()
  })
})


describe("GraphCanvas — non-drag affordances", () => {
  it("fires onSelectNode when a node card is clicked", () => {
    const onSelectNode = vi.fn()
    render(
      <GraphCanvas
        canvas={makeCanvas()}
        selectedNodeId={null}
        onSelectNode={onSelectNode}
        onMoveNode={noop}
        onRemoveNode={noop}
      />,
    )
    fireEvent.click(screen.getByTestId("canvas-node-n_node_1"))
    // Container-arc Phase 0 — onSelectNode now carries an additive flag
    // (false for a plain click → single-select; the page maps it to the
    // unchanged { kind:"node" } path). Signature widened additively.
    expect(onSelectNode).toHaveBeenCalledWith("n_node_1", false)
  })

  it("fires onRemoveNode (not onSelectNode) when the trash button is clicked", () => {
    const onSelectNode = vi.fn()
    const onRemoveNode = vi.fn()
    render(
      <GraphCanvas
        canvas={makeCanvas()}
        selectedNodeId={null}
        onSelectNode={onSelectNode}
        onMoveNode={noop}
        onRemoveNode={onRemoveNode}
      />,
    )
    fireEvent.click(screen.getByTestId("canvas-node-n_node_1-remove"))
    expect(onRemoveNode).toHaveBeenCalledWith("n_node_1")
  })
})


// ── A3 shape-treatment — uniform cards + per-type icon + family tone ───
//
// Replaces the retired B-3b silhouette system. Type is signalled by a
// per-type Lucide ICON (primary); family by a warm-tonal bg + left STRIPE
// (lightness step, no hue). Selection is an ORTHOGONAL channel (terracotta
// ring + border + elevation) — the family tone persists when selected. No
// silhouette SVG renders. Tests run in default light mode (getMode() →
// "light" with no data-mode attr) so the family tones are deterministic.

import { VALID_NODE_TYPES } from "@/lib/visual-editor/workflows/canvas-validator"
import { resolveNodeFamily, TYPE_ICON } from "./node-families"

function nodeOfType(
  type: string,
  config: Record<string, unknown> = {},
): CanvasState {
  return {
    version: 1,
    nodes: [{ id: "n1", type, label: "Check", position: { x: 40, y: 40 }, config }],
    edges: [],
  }
}

function renderType(type: string, selectedNodeId: string | null = null) {
  return render(
    <GraphCanvas
      canvas={nodeOfType(type)}
      selectedNodeId={selectedNodeId}
      onSelectNode={noop}
      onMoveNode={noop}
      onRemoveNode={noop}
    />,
  )
}

/** First descendant div of a node = the visual card (bg-tone + border). */
function cardOf(nodeId: string): HTMLElement {
  const el = screen.getByTestId(`canvas-node-${nodeId}`).querySelector("div")
  if (!el) throw new Error("card div not found")
  return el as HTMLElement
}

describe("GraphCanvas — A3 shape-treatment (icon + family tone)", () => {
  it("renders a uniform card with a per-type icon — no silhouette SVG", () => {
    renderType("decision")
    const icon = screen.getByTestId("canvas-node-n1-icon")
    expect(icon.querySelector("svg")).toBeInTheDocument()
    // The retired B-3b silhouette backdrop no longer renders.
    expect(screen.queryByTestId("node-shape-diamond")).toBeNull()
    expect(screen.getByTestId("canvas-node-n1")).not.toHaveAttribute(
      "data-node-shape",
    )
  })

  it("every VALID_NODE_TYPES type renders an icon (no fallthrough)", () => {
    for (const type of VALID_NODE_TYPES) {
      const { unmount } = renderType(type)
      expect(
        screen.getByTestId("canvas-node-n1-icon").querySelector("svg"),
      ).toBeInTheDocument()
      unmount()
    }
    // Every canonical type is explicitly mapped (the defensive Circle
    // fallback only covers a future unmapped type).
    for (const type of VALID_NODE_TYPES) {
      expect(TYPE_ICON[type]).toBeDefined()
    }
  })

  it("carries the node's family via data-node-family", () => {
    const cases: [string, string][] = [
      ["decision", "flow-control"],
      ["start", "lifecycle"],
      ["action", "action-data"],
      ["ai_prompt", "ai-generation"],
      ["send_email", "communication"],
      ["cross_tenant_order", "cross-tenant"],
    ]
    for (const [type, family] of cases) {
      const { unmount } = renderType(type)
      expect(screen.getByTestId("canvas-node-n1")).toHaveAttribute(
        "data-node-family",
        family,
      )
      expect(resolveNodeFamily(type)).toBe(family)
      unmount()
    }
  })

  it("unknown type → family 'none' + defensive Circle icon (no fallthrough)", () => {
    renderType("__nonexistent__")
    expect(screen.getByTestId("canvas-node-n1")).toHaveAttribute(
      "data-node-family",
      "none",
    )
    expect(
      screen.getByTestId("canvas-node-n1-icon").querySelector("svg"),
    ).toBeInTheDocument()
  })

  it("renders the family left-stripe with a warm-tone background", () => {
    renderType("decision")
    const stripe = screen.getByTestId("canvas-node-n1-family-stripe")
    expect(stripe).toBeInTheDocument()
    expect(stripe.style.background).toContain("oklch")
  })

  it("applies the family bg-tone to the card; distinct families differ", () => {
    const { unmount } = renderType("decision")
    const bgFlowControl = cardOf("n1").style.background
    expect(bgFlowControl).toContain("oklch")
    unmount()
    renderType("cross_tenant_order")
    const bgCrossTenant = cardOf("n1").style.background
    expect(bgCrossTenant).toContain("oklch")
    expect(bgCrossTenant).not.toBe(bgFlowControl)
  })

  it("selection is ORTHOGONAL to family: selected node gets the accent ring + border; family tone + stripe persist", () => {
    // Unselected: family tone present, no selection ring.
    const { unmount } = renderType("action")
    const unselected = cardOf("n1")
    const familyBg = unselected.style.background
    expect(unselected.style.outline).toBe("")
    expect(
      screen.getByTestId("canvas-node-n1-family-stripe"),
    ).toBeInTheDocument()
    unmount()

    // Selected (same type/family): accent ring + border appear; the family
    // bg-tone + stripe are UNCHANGED — the channels never collide.
    renderType("action", "n1")
    expect(screen.getByTestId("canvas-node-n1")).toHaveAttribute(
      "data-selected",
      "true",
    )
    const selected = cardOf("n1")
    expect(selected.style.outline).toContain("var(--accent)")
    expect(selected.style.borderColor).toBe("var(--accent)")
    expect(selected.style.background).toBe(familyBg) // family tone persists
    expect(
      screen.getByTestId("canvas-node-n1-family-stripe"),
    ).toBeInTheDocument()
  })

  it("renders the label; the n_ node-ID is NOT shown (A3 grow-to-fit)", () => {
    renderType("decision")
    expect(screen.getByTestId("canvas-node-n1-label")).toHaveTextContent("Check")
    expect(screen.queryByText("n1")).toBeNull()
  })

  it("label wraps (no truncate) so a long label is shown in full; card grows (min-height floor, no fixed height)", () => {
    const longLabel =
      "Generate case file VaultItem and route to the arrangement review queue"
    render(
      <GraphCanvas
        canvas={{
          version: 1,
          nodes: [
            { id: "nL", type: "generate_document", label: longLabel, position: { x: 0, y: 0 }, config: {} },
          ],
          edges: [],
        }}
        selectedNodeId={null}
        onSelectNode={noop}
        onMoveNode={noop}
        onRemoveNode={noop}
      />,
    )
    // Full label present, untruncated.
    expect(screen.getByTestId("canvas-node-nL-label")).toHaveTextContent(longLabel)
    expect(screen.getByTestId("canvas-node-nL-label").className).not.toContain("truncate")
    // Outer node uses a min-height floor + auto growth — NOT a fixed height.
    const outer = screen.getByTestId("canvas-node-nL")
    expect(outer.style.height).toBe("")
    expect(outer.style.minHeight).not.toBe("")
  })
})


// ── Phase B sub-arc B-4 — execution-trace reachability overlay ────────
//
// Overlay DEFAULT OFF (operator-locked): overlay-off = byte-identical to
// the B-1/B-3 authoring render. Toggle composes trace dim/marker OVER the
// existing render without altering shapes/edges.

// s -> a -> end, plus an orphan node (added but never connected).
const TRACE_CANVAS: CanvasState = {
  version: 1,
  nodes: [
    { id: "s", type: "start", position: { x: 0, y: 0 }, config: {} },
    { id: "a", type: "action", position: { x: 0, y: 150 }, config: {} },
    { id: "end", type: "end", position: { x: 0, y: 300 }, config: {} },
    { id: "orphan", type: "action", position: { x: 300, y: 0 }, config: {} },
  ],
  edges: [
    { id: "e1", source: "s", target: "a" },
    { id: "e2", source: "a", target: "end" },
    { id: "e_orphan", source: "orphan", target: "a" }, // source unreachable
  ],
}

function renderTrace() {
  return render(
    <GraphCanvas
      canvas={TRACE_CANVAS}
      selectedNodeId={null}
      onSelectNode={noop}
      onMoveNode={noop}
      onRemoveNode={noop}
    />,
  )
}

describe("GraphCanvas — B-4 reachability overlay", () => {
  it("ships the persistent toggle, default OFF", () => {
    renderTrace()
    const toggle = screen.getByTestId("trace-overlay-toggle")
    expect(toggle).toBeInTheDocument()
    expect(toggle).toHaveAttribute("data-trace-overlay", "off")
  })

  it("overlay OFF (default): no node/edge carries a trace-state attr (byte-identical render)", () => {
    renderTrace()
    expect(screen.getByTestId("canvas-node-s")).not.toHaveAttribute("data-trace-state")
    expect(screen.getByTestId("canvas-node-orphan")).not.toHaveAttribute("data-trace-state")
    expect(screen.getByTestId("edge-e1")).not.toHaveAttribute("data-trace-state")
  })

  it("toggle ON: reachable nodes/edges marked reachable, orphan marked unreachable + dimmed", () => {
    renderTrace()
    fireEvent.click(screen.getByTestId("trace-overlay-toggle"))
    expect(screen.getByTestId("trace-overlay-toggle")).toHaveAttribute("data-trace-overlay", "on")

    // s -> a -> end reachable
    expect(screen.getByTestId("canvas-node-s")).toHaveAttribute("data-trace-state", "reachable")
    expect(screen.getByTestId("canvas-node-a")).toHaveAttribute("data-trace-state", "reachable")
    expect(screen.getByTestId("canvas-node-end")).toHaveAttribute("data-trace-state", "reachable")
    // orphan unreachable + dimmed
    const orphan = screen.getByTestId("canvas-node-orphan")
    expect(orphan).toHaveAttribute("data-trace-state", "unreachable")
    expect(orphan.style.opacity).toBe("0.35")
    // reachable nodes are NOT dimmed
    expect(screen.getByTestId("canvas-node-s").style.opacity).toBe("")
  })

  it("toggle ON: reachable edge bright, unreachable edge (orphan source) dimmed", () => {
    renderTrace()
    fireEvent.click(screen.getByTestId("trace-overlay-toggle"))
    expect(screen.getByTestId("edge-e1")).toHaveAttribute("data-trace-state", "reachable")
    const orphanEdge = screen.getByTestId("edge-e_orphan")
    expect(orphanEdge).toHaveAttribute("data-trace-state", "unreachable")
    expect(orphanEdge.style.opacity).toBe("0.2")
  })

  it("toggle ON: terminal (end) node gets a terminal marker", () => {
    renderTrace()
    fireEvent.click(screen.getByTestId("trace-overlay-toggle"))
    expect(screen.getByTestId("canvas-node-end-terminal-marker")).toBeInTheDocument()
    // non-terminal nodes get no marker
    expect(screen.queryByTestId("canvas-node-a-terminal-marker")).not.toBeInTheDocument()
  })

  it("toggle OFF again: trace attrs + marker cleared (returns to authoring render)", () => {
    renderTrace()
    const toggle = screen.getByTestId("trace-overlay-toggle")
    fireEvent.click(toggle) // on
    expect(screen.getByTestId("canvas-node-end-terminal-marker")).toBeInTheDocument()
    fireEvent.click(toggle) // off
    expect(toggle).toHaveAttribute("data-trace-overlay", "off")
    expect(screen.getByTestId("canvas-node-s")).not.toHaveAttribute("data-trace-state")
    expect(screen.queryByTestId("canvas-node-end-terminal-marker")).not.toBeInTheDocument()
  })

  it("overlay does not alter the card (composes over it)", () => {
    renderTrace()
    const startCardBefore = screen
      .getByTestId("canvas-node-s")
      .querySelector("div")!.style.background
    fireEvent.click(screen.getByTestId("trace-overlay-toggle"))
    // start node still renders its A3 card + icon + family stripe with the
    // overlay on — trace dim is an OUTER opacity layer; the card (bg-tone +
    // icon + stripe) is untouched.
    expect(
      screen.getByTestId("canvas-node-s-icon").querySelector("svg"),
    ).toBeInTheDocument()
    expect(
      screen.getByTestId("canvas-node-s-family-stripe"),
    ).toBeInTheDocument()
    expect(
      screen.getByTestId("canvas-node-s").querySelector("div")!.style
        .background,
    ).toBe(startCardBefore)
  })
})


// ── Phase B sub-arc B-5 — selection mechanics (edge + background) ─────
//
// Additive: node selection (selectedNodeId/onSelectNode) is unchanged.
// Edges become clickable via a per-edge transparent hit-stroke
// (pointer-events:stroke) on the otherwise pointer-events:none SVG —
// node-drag passthrough preserved. Background-click on the empty surface
// reports onSelectBackground.

describe("GraphCanvas — B-5 edge + background selection", () => {
  it("renders a per-edge hit-stroke when onSelectEdge is provided", () => {
    render(
      <GraphCanvas
        canvas={makeCanvas()}
        selectedNodeId={null}
        onSelectNode={noop}
        onMoveNode={noop}
        onRemoveNode={noop}
        onSelectEdge={vi.fn()}
      />,
    )
    expect(screen.getByTestId("edge-hit-e_n_node_1_n_node_2")).toBeInTheDocument()
  })

  it("does NOT render a hit-stroke when onSelectEdge is omitted (B-1/B-4 default)", () => {
    render(
      <GraphCanvas
        canvas={makeCanvas()}
        selectedNodeId={null}
        onSelectNode={noop}
        onMoveNode={noop}
        onRemoveNode={noop}
      />,
    )
    expect(screen.queryByTestId("edge-hit-e_n_node_1_n_node_2")).not.toBeInTheDocument()
  })

  it("clicking the edge hit-stroke fires onSelectEdge with the edge id", () => {
    const onSelectEdge = vi.fn()
    render(
      <GraphCanvas
        canvas={makeCanvas()}
        selectedNodeId={null}
        onSelectNode={noop}
        onMoveNode={noop}
        onRemoveNode={noop}
        onSelectEdge={onSelectEdge}
      />,
    )
    fireEvent.click(screen.getByTestId("edge-hit-e_n_node_1_n_node_2"))
    expect(onSelectEdge).toHaveBeenCalledWith("e_n_node_1_n_node_2")
  })

  it("highlights the selected edge (data-edge-selected) without altering others", () => {
    render(
      <GraphCanvas
        canvas={makeCanvas()}
        selectedNodeId={null}
        onSelectNode={noop}
        onMoveNode={noop}
        onRemoveNode={noop}
        selectedEdgeId="e_n_node_1_n_node_2"
        onSelectEdge={vi.fn()}
      />,
    )
    expect(screen.getByTestId("edge-e_n_node_1_n_node_2")).toHaveAttribute("data-edge-selected", "true")
  })

  it("background-click on the empty surface fires onSelectBackground; a node click does NOT", () => {
    const onSelectBackground = vi.fn()
    const onSelectNode = vi.fn()
    render(
      <GraphCanvas
        canvas={makeCanvas()}
        selectedNodeId={null}
        onSelectNode={onSelectNode}
        onMoveNode={noop}
        onRemoveNode={noop}
        onSelectBackground={onSelectBackground}
      />,
    )
    // Direct surface click (target === currentTarget) → background.
    fireEvent.click(screen.getByTestId("graph-canvas-surface"))
    expect(onSelectBackground).toHaveBeenCalledTimes(1)
    // A node click does NOT bubble to background (target !== surface).
    onSelectBackground.mockClear()
    fireEvent.click(screen.getByTestId("canvas-node-n_node_1"))
    // P0: plain click carries additive=false (single-select, unchanged path).
    expect(onSelectNode).toHaveBeenCalledWith("n_node_1", false)
    expect(onSelectBackground).not.toHaveBeenCalled()
  })

  it("node selection still works with edges present (drag-passthrough contract intact)", () => {
    const onSelectNode = vi.fn()
    render(
      <GraphCanvas
        canvas={makeCanvas()}
        selectedNodeId={null}
        onSelectNode={onSelectNode}
        onMoveNode={noop}
        onRemoveNode={noop}
        onSelectEdge={vi.fn()}
        onSelectBackground={vi.fn()}
      />,
    )
    // SVG edge layer stays pointer-events-none; only the hit-stroke is a
    // target. The node remains clickable/selectable.
    expect(screen.getByTestId("graph-canvas-edges")).toHaveClass("pointer-events-none")
    fireEvent.click(screen.getByTestId("canvas-node-n_node_2"))
    // P0: plain click carries additive=false (single-select, unchanged path).
    expect(onSelectNode).toHaveBeenCalledWith("n_node_2", false)
  })

  it("edge selection composes with the B-4 overlay (dim + selected highlight coexist)", () => {
    // Orphan-source edge: overlay ON dims it; selecting it still flags it.
    const canvas: CanvasState = {
      version: 1,
      nodes: [
        { id: "s", type: "start", position: { x: 0, y: 0 }, config: {} },
        { id: "orphan", type: "action", position: { x: 300, y: 0 }, config: {} },
        { id: "a", type: "action", position: { x: 0, y: 200 }, config: {} },
      ],
      edges: [{ id: "e_o_a", source: "orphan", target: "a" }],
    }
    render(
      <GraphCanvas
        canvas={canvas}
        selectedNodeId={null}
        onSelectNode={noop}
        onMoveNode={noop}
        onRemoveNode={noop}
        selectedEdgeId="e_o_a"
        onSelectEdge={vi.fn()}
      />,
    )
    // overlay default OFF — selection highlight present, no trace dim.
    const edge = screen.getByTestId("edge-e_o_a")
    expect(edge).toHaveAttribute("data-edge-selected", "true")
    expect(edge).not.toHaveAttribute("data-trace-state")
    // turn overlay on → orphan-source edge dims AND stays selected.
    fireEvent.click(screen.getByTestId("trace-overlay-toggle"))
    expect(edge).toHaveAttribute("data-trace-state", "unreachable")
    expect(edge).toHaveAttribute("data-edge-selected", "true")
    expect(edge.style.opacity).toBe("0.2")
  })
})


// ── Phase B integration-phase — pan + zoom view transform ────────────
//
// Self-owned {panX, panY, zoom} on GraphCanvas (B-4 precedent — zero
// WorkflowEditorPage change, never persisted in canvas_state). Pan =
// left-drag on background with a 3px threshold extending the B-5
// bg-click; zoom = wheel zoom-to-cursor clamped [0.25, 2.0]. Numeric
// zoom-to-cursor + boundary-clamp correctness lives in
// canvas-pan-zoom.test.ts; here we assert the gesture wiring + the
// resulting inline transform / state attributes (JSDOM exposes inline
// style + data-* but doesn't compute transforms into layout).

describe("GraphCanvas — pan + zoom", () => {
  it("renders the identity view transform on the surface by default", () => {
    render(
      <GraphCanvas
        canvas={makeCanvas()}
        selectedNodeId={null}
        onSelectNode={noop}
        onMoveNode={noop}
        onRemoveNode={noop}
      />,
    )
    const surface = screen.getByTestId("graph-canvas-surface")
    expect(surface.style.transform).toBe("translate(0px, 0px) scale(1)")
    expect(surface.getAttribute("data-zoom")).toBe("1")
  })

  it("a background drag >3px pans the surface (transform changes); zoom untouched", () => {
    render(
      <GraphCanvas
        canvas={makeCanvas()}
        selectedNodeId={null}
        onSelectNode={noop}
        onMoveNode={noop}
        onRemoveNode={noop}
        onSelectBackground={vi.fn()}
      />,
    )
    const surface = screen.getByTestId("graph-canvas-surface")
    const before = surface.style.transform
    fireEvent.pointerDown(surface, { clientX: 100, clientY: 100, pointerId: 1 })
    fireEvent.pointerMove(surface, { clientX: 140, clientY: 150, pointerId: 1 })
    expect(surface.style.transform).not.toBe(before)
    // Pan changed translate, not scale.
    expect(surface.getAttribute("data-zoom")).toBe("1")
    fireEvent.pointerUp(surface, { clientX: 140, clientY: 150, pointerId: 1 })
  })

  it("a background pointer-down released <3px still fires onSelectBackground (B-5 preserved)", () => {
    const onSelectBackground = vi.fn()
    render(
      <GraphCanvas
        canvas={makeCanvas()}
        selectedNodeId={null}
        onSelectNode={noop}
        onMoveNode={noop}
        onRemoveNode={noop}
        onSelectBackground={onSelectBackground}
      />,
    )
    const surface = screen.getByTestId("graph-canvas-surface")
    fireEvent.pointerDown(surface, { clientX: 100, clientY: 100, pointerId: 1 })
    fireEvent.pointerMove(surface, { clientX: 101, clientY: 101, pointerId: 1 })
    fireEvent.pointerUp(surface, { clientX: 101, clientY: 101, pointerId: 1 })
    fireEvent.click(surface) // trailing click — not suppressed (no pan)
    expect(onSelectBackground).toHaveBeenCalledTimes(1)
  })

  it("a click that terminates a pan does NOT fire onSelectBackground (suppression)", () => {
    const onSelectBackground = vi.fn()
    render(
      <GraphCanvas
        canvas={makeCanvas()}
        selectedNodeId={null}
        onSelectNode={noop}
        onMoveNode={noop}
        onRemoveNode={noop}
        onSelectBackground={onSelectBackground}
      />,
    )
    const surface = screen.getByTestId("graph-canvas-surface")
    fireEvent.pointerDown(surface, { clientX: 100, clientY: 100, pointerId: 1 })
    fireEvent.pointerMove(surface, { clientX: 200, clientY: 200, pointerId: 1 }) // >3px → pan
    fireEvent.pointerUp(surface, { clientX: 200, clientY: 200, pointerId: 1 })
    fireEvent.click(surface) // suppressed — terminated a pan
    expect(onSelectBackground).not.toHaveBeenCalled()
  })

  it("a pointer-down on a NODE does not pan (gating: target !== surface)", () => {
    render(
      <GraphCanvas
        canvas={makeCanvas()}
        selectedNodeId={null}
        onSelectNode={noop}
        onMoveNode={noop}
        onRemoveNode={noop}
        onSelectBackground={vi.fn()}
      />,
    )
    const surface = screen.getByTestId("graph-canvas-surface")
    const before = surface.style.transform
    const node = screen.getByTestId("canvas-node-n_node_1")
    fireEvent.pointerDown(node, { clientX: 50, clientY: 50, pointerId: 1 })
    fireEvent.pointerMove(node, { clientX: 200, clientY: 200, pointerId: 1 })
    expect(surface.style.transform).toBe(before) // unchanged — node-drag is dnd-kit's
  })

  it("mouse-wheel zooms the surface within [0.25, 2.0]", () => {
    render(
      <GraphCanvas
        canvas={makeCanvas()}
        selectedNodeId={null}
        onSelectNode={noop}
        onMoveNode={noop}
        onRemoveNode={noop}
      />,
    )
    const surface = screen.getByTestId("graph-canvas-surface")
    fireEvent.wheel(surface, { deltaY: -100, clientX: 100, clientY: 100 })
    const z = Number(surface.getAttribute("data-zoom"))
    expect(z).toBeGreaterThan(1)
    expect(z).toBeLessThanOrEqual(2)
  })

  it("zoom clamps at the 2.0 ceiling on repeated zoom-in", () => {
    render(
      <GraphCanvas
        canvas={makeCanvas()}
        selectedNodeId={null}
        onSelectNode={noop}
        onMoveNode={noop}
        onRemoveNode={noop}
      />,
    )
    const surface = screen.getByTestId("graph-canvas-surface")
    for (let i = 0; i < 50; i++) {
      fireEvent.wheel(surface, { deltaY: -200, clientX: 100, clientY: 100 })
    }
    expect(Number(surface.getAttribute("data-zoom"))).toBe(2)
  })

  it("reset-view restores pan 0,0 + zoom 1", () => {
    render(
      <GraphCanvas
        canvas={makeCanvas()}
        selectedNodeId={null}
        onSelectNode={noop}
        onMoveNode={noop}
        onRemoveNode={noop}
      />,
    )
    const surface = screen.getByTestId("graph-canvas-surface")
    fireEvent.wheel(surface, { deltaY: -200, clientX: 100, clientY: 100 })
    expect(Number(surface.getAttribute("data-zoom"))).not.toBe(1)
    fireEvent.click(screen.getByTestId("canvas-zoom-reset"))
    expect(surface.getAttribute("data-zoom")).toBe("1")
    expect(surface.getAttribute("data-pan-x")).toBe("0")
    expect(surface.getAttribute("data-pan-y")).toBe("0")
  })

  it("the zoom indicator reflects the current zoom percent", () => {
    render(
      <GraphCanvas
        canvas={makeCanvas()}
        selectedNodeId={null}
        onSelectNode={noop}
        onMoveNode={noop}
        onRemoveNode={noop}
      />,
    )
    expect(screen.getByTestId("canvas-zoom-indicator")).toHaveTextContent("100%")
    fireEvent.wheel(screen.getByTestId("graph-canvas-surface"), {
      deltaY: -200,
      clientX: 0,
      clientY: 0,
    })
    expect(screen.getByTestId("canvas-zoom-indicator").textContent).not.toBe("100%")
  })

  it("node inline top/left stay unchanged after a pan (ancestor transform — B-1 position assertion safe)", () => {
    render(
      <GraphCanvas
        canvas={makeCanvas()}
        selectedNodeId={null}
        onSelectNode={noop}
        onMoveNode={noop}
        onRemoveNode={noop}
        onSelectBackground={vi.fn()}
      />,
    )
    const surface = screen.getByTestId("graph-canvas-surface")
    const n2 = screen.getByTestId("canvas-node-n_node_2")
    expect(n2.style.top).toBe("200px")
    fireEvent.pointerDown(surface, { clientX: 100, clientY: 100, pointerId: 1 })
    fireEvent.pointerMove(surface, { clientX: 200, clientY: 200, pointerId: 1 })
    fireEvent.pointerUp(surface, { clientX: 200, clientY: 200, pointerId: 1 })
    // Transform is on the ancestor surface; node inline styles untouched.
    expect(n2.style.top).toBe("200px")
    expect(n2.style.left).toBe("40px")
  })
})


// ── Inline-params P2a — clickable sentence tokens (popover edit) ──────
//
// n_node_2 is type "action" → sentence "Run action {actionType}" →
// actionType (string) is a simple editable token. Click → popover →
// PropControlDispatcher → edit → onUpdateNodeConfig(nodeId, mergedConfig).
// Positioning-under-pan+zoom is Playwright-deferred (jsdom no layout); the
// click→edit→persist LOGIC is covered here.

describe("GraphCanvas — P2a inline param edit", () => {
  it("clicking a simple token + editing persists the MERGED config via onUpdateNodeConfig", () => {
    const onUpdateNodeConfig = vi.fn()
    render(
      <GraphCanvas
        canvas={makeCanvas()}
        selectedNodeId={null}
        onSelectNode={noop}
        onMoveNode={noop}
        onRemoveNode={noop}
        onUpdateNodeConfig={onUpdateNodeConfig}
      />,
    )
    const token = screen.getByTestId("node-token-n_node_2-actionType")
    expect(token.getAttribute("data-token-editable")).toBe("true")
    fireEvent.click(token)
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "ship" } })
    // config was {} → merged full config flows up (unset→set adds the key).
    expect(onUpdateNodeConfig).toHaveBeenCalledWith("n_node_2", { actionType: "ship" })
  })

  it("without onUpdateNodeConfig, sentence tokens are read-only (P1 behavior)", () => {
    render(
      <GraphCanvas
        canvas={makeCanvas()}
        selectedNodeId={null}
        onSelectNode={noop}
        onMoveNode={noop}
        onRemoveNode={noop}
      />,
    )
    expect(
      screen
        .getByTestId("node-token-n_node_2-actionType")
        .getAttribute("data-token-editable"),
    ).toBe("false")
  })

  it("clicking a token does NOT select the node (stopPropagation → edit-without-select)", () => {
    const onSelectNode = vi.fn()
    render(
      <GraphCanvas
        canvas={makeCanvas()}
        selectedNodeId={null}
        onSelectNode={onSelectNode}
        onMoveNode={noop}
        onRemoveNode={noop}
        onUpdateNodeConfig={vi.fn()}
      />,
    )
    fireEvent.click(screen.getByTestId("node-token-n_node_2-actionType"))
    expect(onSelectNode).not.toHaveBeenCalled()
  })
})

// ── P3a — un-slotted-param expand panel + inline label edit ──────────

function p3aCanvas(): CanvasState {
  return {
    version: 1,
    nodes: [
      // schedule: slots scheduleMode; cronExpression + delaySeconds un-slotted.
      { id: "n_sch", type: "schedule", label: "", position: { x: 40, y: 40 }, config: {} },
      // start: zero un-slotted params (no expand affordance).
      { id: "n_st", type: "start", label: "Begin", position: { x: 40, y: 240 }, config: {} },
    ],
    edges: [],
  }
}

describe("GraphCanvas — P3a un-slotted-param expand panel", () => {
  it("renders the expand toggle ONLY for types with un-slotted params", () => {
    render(
      <GraphCanvas
        canvas={p3aCanvas()}
        selectedNodeId={null}
        onSelectNode={noop}
        onMoveNode={noop}
        onRemoveNode={noop}
        onUpdateNodeConfig={vi.fn()}
      />,
    )
    // schedule has 2 un-slotted (cronExpression, delaySeconds) → toggle present.
    const toggle = screen.getByTestId("canvas-node-n_sch-expand-toggle")
    expect(toggle).toHaveTextContent("2 more fields")
    // start has 0 un-slotted → no toggle.
    expect(screen.queryByTestId("canvas-node-n_st-expand-toggle")).toBeNull()
  })

  it("does NOT render the toggle without an onUpdateNodeConfig editor", () => {
    render(
      <GraphCanvas
        canvas={p3aCanvas()}
        selectedNodeId={null}
        onSelectNode={noop}
        onMoveNode={noop}
        onRemoveNode={noop}
      />,
    )
    expect(screen.queryByTestId("canvas-node-n_sch-expand-toggle")).toBeNull()
  })

  it("toggling reveals the un-slotted params; slotted params are NOT duplicated (two-tier)", () => {
    render(
      <GraphCanvas
        canvas={p3aCanvas()}
        selectedNodeId={null}
        onSelectNode={noop}
        onMoveNode={noop}
        onRemoveNode={noop}
        onUpdateNodeConfig={vi.fn()}
      />,
    )
    expect(screen.queryByTestId("canvas-node-n_sch-expand-panel")).toBeNull()
    fireEvent.click(screen.getByTestId("canvas-node-n_sch-expand-toggle"))
    expect(screen.getByTestId("canvas-node-n_sch-expand-panel")).toBeInTheDocument()
    // un-slotted params surfaced…
    expect(screen.getByTestId("canvas-node-n_sch-field-cronExpression")).toBeInTheDocument()
    expect(screen.getByTestId("canvas-node-n_sch-field-delaySeconds")).toBeInTheDocument()
    // …the SLOTTED param (scheduleMode) is NOT in the panel (it edits via its token).
    expect(screen.queryByTestId("canvas-node-n_sch-field-scheduleMode")).toBeNull()
  })

  it("editing a panel field persists via onUpdateNodeConfig (whole-key merge)", () => {
    const onUpdateNodeConfig = vi.fn()
    render(
      <GraphCanvas
        canvas={p3aCanvas()}
        selectedNodeId={null}
        onSelectNode={noop}
        onMoveNode={noop}
        onRemoveNode={noop}
        onUpdateNodeConfig={onUpdateNodeConfig}
      />,
    )
    fireEvent.click(screen.getByTestId("canvas-node-n_sch-expand-toggle"))
    // cronExpression is a string control → its input carries the -input suffix.
    fireEvent.change(
      screen.getByTestId("canvas-node-n_sch-field-editor-cronExpression-input"),
      { target: { value: "0 9 * * *" } },
    )
    expect(onUpdateNodeConfig).toHaveBeenCalledWith(
      "n_sch",
      expect.objectContaining({ cronExpression: "0 9 * * *" }),
    )
  })

  it("clicking the expand toggle does NOT select the node (stopPropagation)", () => {
    const onSelectNode = vi.fn()
    render(
      <GraphCanvas
        canvas={p3aCanvas()}
        selectedNodeId={null}
        onSelectNode={onSelectNode}
        onMoveNode={noop}
        onRemoveNode={noop}
        onUpdateNodeConfig={vi.fn()}
      />,
    )
    fireEvent.click(screen.getByTestId("canvas-node-n_sch-expand-toggle"))
    expect(onSelectNode).not.toHaveBeenCalled()
  })
})

describe("GraphCanvas — P3a inline label edit", () => {
  it("double-click a label → input → Enter persists via onRenameNode", () => {
    const onRenameNode = vi.fn()
    render(
      <GraphCanvas
        canvas={makeCanvas()}
        selectedNodeId={null}
        onSelectNode={noop}
        onMoveNode={noop}
        onRemoveNode={noop}
        onRenameNode={onRenameNode}
      />,
    )
    fireEvent.doubleClick(screen.getByTestId("canvas-node-n_node_1-label"))
    const input = screen.getByTestId("canvas-node-n_node_1-label-input")
    fireEvent.change(input, { target: { value: "Kickoff" } })
    fireEvent.keyDown(input, { key: "Enter" })
    expect(onRenameNode).toHaveBeenCalledWith("n_node_1", "Kickoff")
  })

  it("Escape cancels the label edit (onRenameNode NOT called)", () => {
    const onRenameNode = vi.fn()
    render(
      <GraphCanvas
        canvas={makeCanvas()}
        selectedNodeId={null}
        onSelectNode={noop}
        onMoveNode={noop}
        onRemoveNode={noop}
        onRenameNode={onRenameNode}
      />,
    )
    fireEvent.doubleClick(screen.getByTestId("canvas-node-n_node_1-label"))
    const input = screen.getByTestId("canvas-node-n_node_1-label-input")
    fireEvent.change(input, { target: { value: "Discard me" } })
    fireEvent.keyDown(input, { key: "Escape" })
    expect(onRenameNode).not.toHaveBeenCalled()
  })

  it("an empty-label node shows the 'name this node' placeholder ONLY when selected", () => {
    const canvas: CanvasState = {
      version: 1,
      nodes: [{ id: "n_x", type: "action", label: "", position: { x: 40, y: 40 }, config: {} }],
      edges: [],
    }
    const { rerender } = render(
      <GraphCanvas
        canvas={canvas}
        selectedNodeId={null}
        onSelectNode={noop}
        onMoveNode={noop}
        onRemoveNode={noop}
        onRenameNode={vi.fn()}
      />,
    )
    // Not selected → no placeholder.
    expect(screen.queryByTestId("canvas-node-n_x-label-placeholder")).toBeNull()
    // Selected → placeholder appears (so the empty node can gain a name).
    rerender(
      <GraphCanvas
        canvas={canvas}
        selectedNodeId="n_x"
        onSelectNode={noop}
        onMoveNode={noop}
        onRemoveNode={noop}
        onRenameNode={vi.fn()}
      />,
    )
    expect(screen.getByTestId("canvas-node-n_x-label-placeholder")).toBeInTheDocument()
  })

  it("label title is read-only when onRenameNode is absent (no double-click edit)", () => {
    render(
      <GraphCanvas
        canvas={makeCanvas()}
        selectedNodeId={null}
        onSelectNode={noop}
        onMoveNode={noop}
        onRemoveNode={noop}
      />,
    )
    fireEvent.doubleClick(screen.getByTestId("canvas-node-n_node_1-label"))
    expect(screen.queryByTestId("canvas-node-n_node_1-label-input")).toBeNull()
  })
})

// ── P3b-1b — drag-to-connect gesture wiring ──────────────────────────
// The PURE math (screenToWorld / nodeAtPoint / dropDecision) is proven in
// canvas-layout.test + canvas-pan-zoom.test (P3b-1a). Here we assert the
// GESTURE WIRING: handle render, pointerdown→drawing, drop→onCreateEdge /
// cancel. In jsdom getBoundingClientRect()→0 + the default view (pan 0,
// zoom 1) means cursorWorld === client coords, so the drop hit-test is
// drivable by choosing clientX/Y. The LIVE drag under pan/zoom + the
// hit-test-when-zoomed is Playwright-territory (like pan+zoom positioning).

// jsdom note: offsetHeight === 0, and the node's synchronous measure seeds
// `heights` with 0 (and `?? NODE_HEIGHT` does NOT fall back on 0 — it's a
// real value), so a node's hittable region collapses to its TOP EDGE
// (y === node.position.y, x ∈ [x, x+NODE_WIDTH]). The drop coords below are
// chosen for that 0-height reality. The real hit-test over MEASURED heights,
// under live pan/zoom, is Playwright-territory (the math itself is proven in
// canvas-layout.test). src top-edge = y 0; tgt top-edge = y 200; x ∈ [0,200].
function dtcCanvas(): CanvasState {
  return {
    version: 1,
    nodes: [
      { id: "src", type: "action", label: "Source", position: { x: 0, y: 0 }, config: {} },
      { id: "tgt", type: "action", label: "Target", position: { x: 0, y: 200 }, config: {} },
    ],
    edges: [],
  }
}

describe("GraphCanvas — P3b-1b drag-to-connect gesture", () => {
  it("renders the outgoing connection handle ONLY when onCreateEdge is wired", () => {
    const { rerender } = render(
      <GraphCanvas
        canvas={dtcCanvas()}
        selectedNodeId={null}
        onSelectNode={noop}
        onMoveNode={noop}
        onRemoveNode={noop}
      />,
    )
    expect(screen.queryByTestId("canvas-node-src-connect-handle")).toBeNull()
    rerender(
      <GraphCanvas
        canvas={dtcCanvas()}
        selectedNodeId={null}
        onSelectNode={noop}
        onMoveNode={noop}
        onRemoveNode={noop}
        onCreateEdge={vi.fn()}
      />,
    )
    expect(screen.getByTestId("canvas-node-src-connect-handle")).toBeInTheDocument()
  })

  it("pointerdown on the handle starts drawing (preview appears) without selecting the node", () => {
    const onSelectNode = vi.fn()
    render(
      <GraphCanvas
        canvas={dtcCanvas()}
        selectedNodeId={null}
        onSelectNode={onSelectNode}
        onMoveNode={noop}
        onRemoveNode={noop}
        onCreateEdge={vi.fn()}
      />,
    )
    expect(screen.queryByTestId("graph-canvas-draw-preview")).toBeNull()
    fireEvent.pointerDown(screen.getByTestId("canvas-node-src-connect-handle"), {
      clientX: 100,
      clientY: 70,
    })
    expect(screen.getByTestId("graph-canvas-draw-preview")).toBeInTheDocument()
    // stopPropagation → the card's onClick(select) never fires from the handle.
    expect(onSelectNode).not.toHaveBeenCalled()
  })

  it("drop on a valid target fires onCreateEdge(source, target) + clears the preview", () => {
    const onCreateEdge = vi.fn()
    render(
      <GraphCanvas
        canvas={dtcCanvas()}
        selectedNodeId={null}
        onSelectNode={noop}
        onMoveNode={noop}
        onRemoveNode={noop}
        onCreateEdge={onCreateEdge}
      />,
    )
    const handle = screen.getByTestId("canvas-node-src-connect-handle")
    fireEvent.pointerDown(handle, { clientX: 100, clientY: 0 })
    fireEvent.pointerMove(handle, { clientX: 100, clientY: 200 })
    fireEvent.pointerUp(handle, { clientX: 100, clientY: 200 }) // tgt top-edge (y 200)
    expect(onCreateEdge).toHaveBeenCalledWith("src", "tgt")
    expect(screen.queryByTestId("graph-canvas-draw-preview")).toBeNull()
  })

  it("drop on the source itself cancels (self) — no onCreateEdge, preview cleared", () => {
    const onCreateEdge = vi.fn()
    render(
      <GraphCanvas
        canvas={dtcCanvas()}
        selectedNodeId={null}
        onSelectNode={noop}
        onMoveNode={noop}
        onRemoveNode={noop}
        onCreateEdge={onCreateEdge}
      />,
    )
    const handle = screen.getByTestId("canvas-node-src-connect-handle")
    fireEvent.pointerDown(handle, { clientX: 100, clientY: 0 })
    fireEvent.pointerUp(handle, { clientX: 100, clientY: 0 }) // src top-edge (self)
    expect(onCreateEdge).not.toHaveBeenCalled()
    expect(screen.queryByTestId("graph-canvas-draw-preview")).toBeNull()
  })

  it("drop on empty canvas cancels (empty) — no onCreateEdge", () => {
    const onCreateEdge = vi.fn()
    render(
      <GraphCanvas
        canvas={dtcCanvas()}
        selectedNodeId={null}
        onSelectNode={noop}
        onMoveNode={noop}
        onRemoveNode={noop}
        onCreateEdge={onCreateEdge}
      />,
    )
    const handle = screen.getByTestId("canvas-node-src-connect-handle")
    fireEvent.pointerDown(handle, { clientX: 100, clientY: 70 })
    fireEvent.pointerUp(handle, { clientX: 900, clientY: 900 }) // empty space
    expect(onCreateEdge).not.toHaveBeenCalled()
  })

  it("the handle is opacity-visible when the node is selected", () => {
    render(
      <GraphCanvas
        canvas={dtcCanvas()}
        selectedNodeId="src"
        onSelectNode={noop}
        onMoveNode={noop}
        onRemoveNode={noop}
        onCreateEdge={vi.fn()}
      />,
    )
    expect(screen.getByTestId("canvas-node-src-connect-handle").className).toContain(
      "opacity-100",
    )
  })
})

// ── P3b-2 — canvas edge delete (midpoint-× on the selected edge) ─────
// Reuses B-5 selection + handleRemoveEdge. Button affordance (matches the
// node trash-button idiom) — NO keyboard listener, so there is deliberately
// NO focus-guard test (Backspace-while-editing can't delete an edge because
// no keydown handler exists). Under-transform click positioning is
// Playwright; the testid click + the gate are vitest-coverable here.

const EDGE_ID = "e_n_node_1_n_node_2"

describe("GraphCanvas — P3b-2 canvas edge delete", () => {
  it("does NOT render the delete-× on an unselected edge", () => {
    render(
      <GraphCanvas
        canvas={makeCanvas()}
        selectedNodeId={null}
        onSelectNode={noop}
        onMoveNode={noop}
        onRemoveNode={noop}
        selectedEdgeId={null}
        onSelectEdge={vi.fn()}
        onDeleteEdge={vi.fn()}
      />,
    )
    expect(screen.queryByTestId(`edge-${EDGE_ID}-delete`)).toBeNull()
  })

  it("renders the delete-× on the SELECTED edge", () => {
    render(
      <GraphCanvas
        canvas={makeCanvas()}
        selectedNodeId={null}
        onSelectNode={noop}
        onMoveNode={noop}
        onRemoveNode={noop}
        selectedEdgeId={EDGE_ID}
        onSelectEdge={vi.fn()}
        onDeleteEdge={vi.fn()}
      />,
    )
    expect(screen.getByTestId(`edge-${EDGE_ID}-delete`)).toBeInTheDocument()
  })

  it("does NOT render the × without an onDeleteEdge handler (gated)", () => {
    render(
      <GraphCanvas
        canvas={makeCanvas()}
        selectedNodeId={null}
        onSelectNode={noop}
        onMoveNode={noop}
        onRemoveNode={noop}
        selectedEdgeId={EDGE_ID}
        onSelectEdge={vi.fn()}
      />,
    )
    expect(screen.queryByTestId(`edge-${EDGE_ID}-delete`)).toBeNull()
  })

  it("clicking the × fires onDeleteEdge(id) + stopPropagation (no background re-select)", () => {
    const onDeleteEdge = vi.fn()
    const onSelectBackground = vi.fn()
    render(
      <GraphCanvas
        canvas={makeCanvas()}
        selectedNodeId={null}
        onSelectNode={noop}
        onMoveNode={noop}
        onRemoveNode={noop}
        selectedEdgeId={EDGE_ID}
        onSelectEdge={vi.fn()}
        onSelectBackground={onSelectBackground}
        onDeleteEdge={onDeleteEdge}
      />,
    )
    fireEvent.click(screen.getByTestId(`edge-${EDGE_ID}-delete`))
    expect(onDeleteEdge).toHaveBeenCalledWith(EDGE_ID)
    // stopPropagation → the click never bubbles to the surface bg-select.
    expect(onSelectBackground).not.toHaveBeenCalled()
  })
})

// ── P3 (E-3) — bespoke focus configs host in the card expand panel ───
// The 2 invoke_* types edit their bespoke config IN the expand panel (the
// dependent op_id + binding-list kwargs need richer editing than dispatcher
// rows). The dumb un-slotted rows (op_id/kwargs) the panel would otherwise
// render for these types are replaced by the bespoke config; the slotted
// {focus_id}/{review_focus_id} token stays read-only (display).

function e3Canvas(): CanvasState {
  return {
    version: 1,
    nodes: [
      { id: "n_gen", type: "invoke_generation_focus", label: "Gen", position: { x: 40, y: 40 }, config: {} },
      { id: "n_rev", type: "invoke_review_focus", label: "Rev", position: { x: 40, y: 240 }, config: {} },
      // P2's migrated obituary node: a TODO focus_id not in the catalog.
      {
        id: "n_todo",
        type: "invoke_generation_focus",
        label: "Obituary",
        position: { x: 40, y: 440 },
        config: { focus_id: "TODO_obituary_generation", op_id: "TODO", kwargs: { extraction_template: "obituary" } },
      },
    ],
    edges: [],
  }
}

describe("GraphCanvas — P3 (E-3) bespoke config hosted in the expand panel", () => {
  it("a bespoke type's toggle reads 'Configure' (not 'N more fields')", () => {
    render(
      <GraphCanvas
        canvas={e3Canvas()}
        selectedNodeId={null}
        onSelectNode={noop}
        onMoveNode={noop}
        onRemoveNode={noop}
        onUpdateNodeConfig={vi.fn()}
      />,
    )
    expect(screen.getByTestId("canvas-node-n_gen-expand-toggle")).toHaveTextContent("Configure")
  })

  it("expanding a bespoke node hosts the bespoke config (NOT the dumb op_id/kwargs rows)", () => {
    render(
      <GraphCanvas
        canvas={e3Canvas()}
        selectedNodeId={null}
        onSelectNode={noop}
        onMoveNode={noop}
        onRemoveNode={noop}
        onUpdateNodeConfig={vi.fn()}
      />,
    )
    fireEvent.click(screen.getByTestId("canvas-node-n_gen-expand-toggle"))
    // The bespoke config (via BespokeNodePane) is hosted in the panel…
    expect(screen.getByTestId("bespoke-node-pane")).toBeInTheDocument()
    expect(screen.getByTestId("wf-invoke-generation-focus-config")).toBeInTheDocument()
    // …and the DUMB un-slotted rows are NOT rendered for the bespoke type.
    expect(screen.queryByTestId("canvas-node-n_gen-field-op_id")).toBeNull()
    expect(screen.queryByTestId("canvas-node-n_gen-field-kwargs")).toBeNull()
  })

  it("editing the hosted bespoke config persists via onUpdateNodeConfig (full config)", () => {
    const onUpdateNodeConfig = vi.fn()
    render(
      <GraphCanvas
        canvas={e3Canvas()}
        selectedNodeId={null}
        onSelectNode={noop}
        onMoveNode={noop}
        onRemoveNode={noop}
        onUpdateNodeConfig={onUpdateNodeConfig}
      />,
    )
    fireEvent.click(screen.getByTestId("canvas-node-n_rev-expand-toggle"))
    // review_focus_id is a plain Input in InvokeReviewFocusConfig — drivable.
    fireEvent.change(screen.getByTestId("wf-invoke-review-focus-slug"), {
      target: { value: "decedent_info_review" },
    })
    expect(onUpdateNodeConfig).toHaveBeenCalledWith(
      "n_rev",
      expect.objectContaining({ review_focus_id: "decedent_info_review" }),
    )
  })

  it("a non-bespoke type still renders the dumb un-slotted rows (regression)", () => {
    render(
      <GraphCanvas
        canvas={p3aCanvas()}
        selectedNodeId={null}
        onSelectNode={noop}
        onMoveNode={noop}
        onRemoveNode={noop}
        onUpdateNodeConfig={vi.fn()}
      />,
    )
    fireEvent.click(screen.getByTestId("canvas-node-n_sch-expand-toggle"))
    expect(screen.getByTestId("canvas-node-n_sch-field-cronExpression")).toBeInTheDocument()
    expect(screen.queryByTestId("bespoke-node-pane")).toBeNull()
  })

  it("the TODO-focus_id node (P2's migrated obituary) hosts the config gracefully (no crash)", () => {
    render(
      <GraphCanvas
        canvas={e3Canvas()}
        selectedNodeId={null}
        onSelectNode={noop}
        onMoveNode={noop}
        onRemoveNode={noop}
        onUpdateNodeConfig={vi.fn()}
      />,
    )
    fireEvent.click(screen.getByTestId("canvas-node-n_todo-expand-toggle"))
    // The bespoke config renders even though focus_id isn't in the catalog
    // (the focus Select shows its placeholder; the op dropdown is disabled).
    expect(screen.getByTestId("bespoke-node-pane")).toBeInTheDocument()
    expect(screen.getByTestId("wf-invoke-generation-focus-config")).toBeInTheDocument()
  })
})


describe("GraphCanvas — Container-arc Phase 0 (multi-node selection)", () => {
  // The selection MECHANISM only: shift/⌘+click reports `additive`, multi
  // members render the ring (data-multi-selected), card editing stays
  // dormant under multi. The union-transition logic lives in the PAGE; here
  // we assert the canvas reports the additive flag + renders the ring from
  // the selectedNodeIds prop.

  it("reports additive=true on a shift+click", () => {
    const onSelectNode = vi.fn()
    render(
      <GraphCanvas
        canvas={makeCanvas()}
        selectedNodeId={null}
        onSelectNode={onSelectNode}
        onMoveNode={noop}
        onRemoveNode={noop}
      />,
    )
    fireEvent.click(screen.getByTestId("canvas-node-n_node_2"), { shiftKey: true })
    expect(onSelectNode).toHaveBeenCalledWith("n_node_2", true)
  })

  it("reports additive=true on a ⌘(meta)+click", () => {
    const onSelectNode = vi.fn()
    render(
      <GraphCanvas
        canvas={makeCanvas()}
        selectedNodeId={null}
        onSelectNode={onSelectNode}
        onMoveNode={noop}
        onRemoveNode={noop}
      />,
    )
    fireEvent.click(screen.getByTestId("canvas-node-n_node_1"), { metaKey: true })
    expect(onSelectNode).toHaveBeenCalledWith("n_node_1", true)
  })

  it("renders the ring on every selectedNodeIds member via data-multi-selected", () => {
    render(
      <GraphCanvas
        canvas={makeCanvas()}
        selectedNodeId={null}
        selectedNodeIds={["n_node_1", "n_node_2"]}
        onSelectNode={noop}
        onMoveNode={noop}
        onRemoveNode={noop}
      />,
    )
    expect(screen.getByTestId("canvas-node-n_node_1")).toHaveAttribute(
      "data-multi-selected",
      "true",
    )
    expect(screen.getByTestId("canvas-node-n_node_2")).toHaveAttribute(
      "data-multi-selected",
      "true",
    )
  })

  it("non-members read data-multi-selected=false", () => {
    render(
      <GraphCanvas
        canvas={makeCanvas()}
        selectedNodeId={null}
        selectedNodeIds={["n_node_1"]}
        onSelectNode={noop}
        onMoveNode={noop}
        onRemoveNode={noop}
      />,
    )
    expect(screen.getByTestId("canvas-node-n_node_2")).toHaveAttribute(
      "data-multi-selected",
      "false",
    )
  })

  it("multi-selection does NOT mark a node single-selected (card editing dormant)", () => {
    // selectedNodeId is null under multi → data-selected stays false, so the
    // single-node card-editing channel (connect-handle full-visibility, label
    // placeholder) never activates. The ring is the only multi affordance.
    render(
      <GraphCanvas
        canvas={makeCanvas()}
        selectedNodeId={null}
        selectedNodeIds={["n_node_1", "n_node_2"]}
        onSelectNode={noop}
        onMoveNode={noop}
        onRemoveNode={noop}
      />,
    )
    expect(screen.getByTestId("canvas-node-n_node_1")).toHaveAttribute(
      "data-selected",
      "false",
    )
    // No single-select label placeholder appears for a multi member.
    expect(
      screen.queryByTestId("canvas-node-n_node_1-label-placeholder"),
    ).not.toBeInTheDocument()
  })

  it("single-select is unperturbed by the multi props (selectedNodeIds omitted)", () => {
    // The pre-P0 single-select render: selectedNodeId marks data-selected;
    // no multi prop → data-multi-selected defaults false.
    render(
      <GraphCanvas
        canvas={makeCanvas()}
        selectedNodeId="n_node_2"
        onSelectNode={noop}
        onMoveNode={noop}
        onRemoveNode={noop}
      />,
    )
    const node2 = screen.getByTestId("canvas-node-n_node_2")
    expect(node2).toHaveAttribute("data-selected", "true")
    expect(node2).toHaveAttribute("data-multi-selected", "false")
  })
})


describe("GraphCanvas — Container-arc Phase 1 (expanded labeled regions)", () => {
  function withContainer(overrides = {}) {
    return makeCanvas({
      containers: [
        {
          id: "c_group_1",
          label: "Burial path",
          members: [
            { kind: "node" as const, id: "n_node_1" },
            { kind: "node" as const, id: "n_node_2" },
          ],
          collapsed: false,
        },
      ],
      ...overrides,
    })
  }

  it("renders a labeled box for a container enclosing its member nodes", () => {
    render(
      <GraphCanvas
        canvas={withContainer()}
        selectedNodeId={null}
        onSelectNode={noop}
        onMoveNode={noop}
        onRemoveNode={noop}
        onUpdateContainer={vi.fn()}
        onRemoveContainer={vi.fn()}
      />,
    )
    expect(screen.getByTestId("canvas-container-c_group_1")).toBeInTheDocument()
    expect(screen.getByTestId("canvas-container-c_group_1-label")).toHaveTextContent(
      "Burial path",
    )
  })

  it("a canvas with no containers renders no container box (back-compat)", () => {
    render(
      <GraphCanvas
        canvas={makeCanvas()}
        selectedNodeId={null}
        onSelectNode={noop}
        onMoveNode={noop}
        onRemoveNode={noop}
      />,
    )
    expect(screen.queryByTestId(/^canvas-container-/)).not.toBeInTheDocument()
  })

  it("a container with no resolvable node-member renders nothing", () => {
    const canvas = makeCanvas({
      containers: [
        { id: "c_empty", members: [], collapsed: false },
      ],
    })
    render(
      <GraphCanvas
        canvas={canvas}
        selectedNodeId={null}
        onSelectNode={noop}
        onMoveNode={noop}
        onRemoveNode={noop}
        onUpdateContainer={vi.fn()}
        onRemoveContainer={vi.fn()}
      />,
    )
    expect(screen.queryByTestId("canvas-container-c_empty")).not.toBeInTheDocument()
  })

  it("ungroup button fires onRemoveContainer", () => {
    const onRemoveContainer = vi.fn()
    render(
      <GraphCanvas
        canvas={withContainer()}
        selectedNodeId={null}
        onSelectNode={noop}
        onMoveNode={noop}
        onRemoveNode={noop}
        onUpdateContainer={vi.fn()}
        onRemoveContainer={onRemoveContainer}
      />,
    )
    fireEvent.click(screen.getByTestId("canvas-container-c_group_1-ungroup"))
    expect(onRemoveContainer).toHaveBeenCalledWith("c_group_1")
  })

  it("double-clicking the label opens an inline editor that commits via onUpdateContainer", () => {
    const onUpdateContainer = vi.fn()
    render(
      <GraphCanvas
        canvas={withContainer()}
        selectedNodeId={null}
        onSelectNode={noop}
        onMoveNode={noop}
        onRemoveNode={noop}
        onUpdateContainer={onUpdateContainer}
        onRemoveContainer={vi.fn()}
      />,
    )
    fireEvent.doubleClick(screen.getByTestId("canvas-container-c_group_1-label"))
    const input = screen.getByTestId("canvas-container-c_group_1-label-input")
    fireEvent.change(input, { target: { value: "Renamed" } })
    fireEvent.keyDown(input, { key: "Enter" })
    expect(onUpdateContainer).toHaveBeenCalledWith("c_group_1", { label: "Renamed" })
  })

  it("an unlabeled container shows the 'name this group' placeholder", () => {
    const canvas = makeCanvas({
      containers: [
        {
          id: "c_group_1",
          members: [{ kind: "node" as const, id: "n_node_1" }],
          collapsed: false,
        },
      ],
    })
    render(
      <GraphCanvas
        canvas={canvas}
        selectedNodeId={null}
        onSelectNode={noop}
        onMoveNode={noop}
        onRemoveNode={noop}
        onUpdateContainer={vi.fn()}
        onRemoveContainer={vi.fn()}
      />,
    )
    expect(
      screen.getByTestId("canvas-container-c_group_1-label-placeholder"),
    ).toBeInTheDocument()
  })
})


describe("GraphCanvas — Container-arc Phase 2b (collapse rendering)", () => {
  const cbProps = {
    onSelectNode: noop,
    onMoveNode: noop,
    onRemoveNode: noop,
    onUpdateContainer: vi.fn(),
    onRemoveContainer: vi.fn(),
  }

  it("a collapsed container hides its member nodes + interior edge, shows the collapsed card", () => {
    // makeCanvas: n_node_1 → n_node_2, both members of c1 (collapsed) → the
    // edge is interior (hidden); both member cards hidden; the box collapses.
    const canvas = makeCanvas({
      containers: [
        {
          id: "c1",
          label: "Group A",
          members: [
            { kind: "node" as const, id: "n_node_1" },
            { kind: "node" as const, id: "n_node_2" },
          ],
          collapsed: true,
        },
      ],
    })
    render(<GraphCanvas canvas={canvas} selectedNodeId={null} {...cbProps} />)
    // Members hidden.
    expect(screen.queryByTestId("canvas-node-n_node_1")).not.toBeInTheDocument()
    expect(screen.queryByTestId("canvas-node-n_node_2")).not.toBeInTheDocument()
    // Interior edge hidden.
    expect(
      screen.queryByTestId("edge-e_n_node_1_n_node_2"),
    ).not.toBeInTheDocument()
    // Collapsed card present.
    const box = screen.getByTestId("canvas-container-c1")
    expect(box).toHaveAttribute("data-collapsed", "true")
    expect(screen.getByTestId("canvas-container-c1-label")).toHaveTextContent(
      "Group A",
    )
    expect(screen.getByTestId("canvas-container-c1-expand")).toBeInTheDocument()
  })

  it("crossing edges render (rerouted, not skipped); interior is skipped", () => {
    const canvas = makeCanvas({
      nodes: [
        { id: "n_node_1", type: "start", position: { x: 40, y: 40 }, config: {} },
        { id: "n_node_2", type: "action", position: { x: 40, y: 200 }, config: {} },
        { id: "n_out", type: "end", position: { x: 400, y: 400 }, config: {} },
      ],
      edges: [
        { id: "e_in", source: "n_out", target: "n_node_1" }, // crossing-in
        { id: "e_out", source: "n_node_2", target: "n_out" }, // crossing-out
        { id: "e_int", source: "n_node_1", target: "n_node_2" }, // interior
      ],
      containers: [
        {
          id: "c1",
          members: [
            { kind: "node" as const, id: "n_node_1" },
            { kind: "node" as const, id: "n_node_2" },
          ],
          collapsed: true,
        },
      ],
    })
    render(<GraphCanvas canvas={canvas} selectedNodeId={null} {...cbProps} />)
    // The outside node renders; the members are hidden.
    expect(screen.getByTestId("canvas-node-n_out")).toBeInTheDocument()
    expect(screen.queryByTestId("canvas-node-n_node_1")).not.toBeInTheDocument()
    // Crossing edges render; interior is skipped.
    expect(screen.getByTestId("edge-e_in")).toBeInTheDocument()
    expect(screen.getByTestId("edge-e_out")).toBeInTheDocument()
    expect(screen.queryByTestId("edge-e_int")).not.toBeInTheDocument()
  })

  it("box-to-box: an edge between two collapsed containers renders", () => {
    const canvas = makeCanvas({
      nodes: [
        { id: "n_a", type: "start", position: { x: 40, y: 40 }, config: {} },
        { id: "n_b", type: "end", position: { x: 400, y: 400 }, config: {} },
      ],
      edges: [{ id: "e_bb", source: "n_a", target: "n_b" }],
      containers: [
        { id: "c1", members: [{ kind: "node" as const, id: "n_a" }], collapsed: true },
        { id: "c2", members: [{ kind: "node" as const, id: "n_b" }], collapsed: true },
      ],
    })
    render(<GraphCanvas canvas={canvas} selectedNodeId={null} {...cbProps} />)
    expect(screen.queryByTestId("canvas-node-n_a")).not.toBeInTheDocument()
    expect(screen.queryByTestId("canvas-node-n_b")).not.toBeInTheDocument()
    expect(screen.getByTestId("edge-e_bb")).toBeInTheDocument()
    expect(screen.getByTestId("canvas-container-c1")).toHaveAttribute(
      "data-collapsed",
      "true",
    )
    expect(screen.getByTestId("canvas-container-c2")).toHaveAttribute(
      "data-collapsed",
      "true",
    )
  })

  it("default (collapsed:false) is identical to P1 — members + edge render, no collapsed card", () => {
    const canvas = makeCanvas({
      containers: [
        {
          id: "c1",
          members: [
            { kind: "node" as const, id: "n_node_1" },
            { kind: "node" as const, id: "n_node_2" },
          ],
          collapsed: false,
        },
      ],
    })
    render(<GraphCanvas canvas={canvas} selectedNodeId={null} {...cbProps} />)
    // Members + edge render (P1 behavior).
    expect(screen.getByTestId("canvas-node-n_node_1")).toBeInTheDocument()
    expect(screen.getByTestId("canvas-node-n_node_2")).toBeInTheDocument()
    expect(screen.getByTestId("edge-e_n_node_1_n_node_2")).toBeInTheDocument()
    // The expanded frame carries data-collapsed=false + a collapse button.
    expect(screen.getByTestId("canvas-container-c1")).toHaveAttribute(
      "data-collapsed",
      "false",
    )
    expect(screen.getByTestId("canvas-container-c1-collapse")).toBeInTheDocument()
  })

  it("the expand toggle fires onUpdateContainer({collapsed:false})", () => {
    const onUpdateContainer = vi.fn()
    const canvas = makeCanvas({
      containers: [
        {
          id: "c1",
          members: [{ kind: "node" as const, id: "n_node_1" }],
          collapsed: true,
        },
      ],
    })
    render(
      <GraphCanvas
        canvas={canvas}
        selectedNodeId={null}
        {...cbProps}
        onUpdateContainer={onUpdateContainer}
      />,
    )
    fireEvent.click(screen.getByTestId("canvas-container-c1-expand"))
    expect(onUpdateContainer).toHaveBeenCalledWith("c1", { collapsed: false })
  })

  it("the collapse toggle (expanded chrome) fires onUpdateContainer({collapsed:true})", () => {
    const onUpdateContainer = vi.fn()
    const canvas = makeCanvas({
      containers: [
        {
          id: "c1",
          members: [{ kind: "node" as const, id: "n_node_1" }],
          collapsed: false,
        },
      ],
    })
    render(
      <GraphCanvas
        canvas={canvas}
        selectedNodeId={null}
        {...cbProps}
        onUpdateContainer={onUpdateContainer}
      />,
    )
    fireEvent.click(screen.getByTestId("canvas-container-c1-collapse"))
    expect(onUpdateContainer).toHaveBeenCalledWith("c1", { collapsed: true })
  })

  it("a canvas with no collapsed container renders every node + edge (no hidden members)", () => {
    // No containers at all — the membership map is empty → nothing filtered.
    render(<GraphCanvas canvas={makeCanvas()} selectedNodeId={null} {...cbProps} />)
    expect(screen.getByTestId("canvas-node-n_node_1")).toBeInTheDocument()
    expect(screen.getByTestId("canvas-node-n_node_2")).toBeInTheDocument()
    expect(screen.getByTestId("edge-e_n_node_1_n_node_2")).toBeInTheDocument()
  })
})


describe("GraphCanvas — Container-arc Phase 3b (nested rendering)", () => {
  const cb = {
    onSelectNode: noop,
    onMoveNode: noop,
    onRemoveNode: noop,
    onUpdateContainer: vi.fn(),
    onRemoveContainer: vi.fn(),
  }
  const px = (el: HTMLElement, prop: "left" | "top" | "width" | "height") =>
    parseFloat(el.style[prop] || "0")
  const z = (el: HTMLElement) => parseFloat(el.style.zIndex || "0")

  // Outer A ⊃ inner B ⊃ { n_node_1, n_node_2 } (the makeCanvas nodes).
  function nestedCanvas(aCollapsed: boolean, bCollapsed: boolean) {
    return makeCanvas({
      containers: [
        { id: "A", label: "Outer", members: [{ kind: "container" as const, id: "B" }], collapsed: aCollapsed },
        {
          id: "B",
          label: "Inner",
          members: [
            { kind: "node" as const, id: "n_node_1" },
            { kind: "node" as const, id: "n_node_2" },
          ],
          collapsed: bCollapsed,
        },
      ],
    })
  }

  it("an expanded outer ENCLOSES an expanded inner box (recursive bounds)", () => {
    render(<GraphCanvas canvas={nestedCanvas(false, false)} selectedNodeId={null} {...cb} />)
    const outer = screen.getByTestId("canvas-container-A")
    const inner = screen.getByTestId("canvas-container-B")
    expect(outer).toHaveAttribute("data-collapsed", "false")
    expect(inner).toHaveAttribute("data-collapsed", "false")
    // Outer frame fully contains the inner frame.
    expect(px(outer, "left")).toBeLessThan(px(inner, "left"))
    expect(px(outer, "top")).toBeLessThan(px(inner, "top"))
    expect(px(outer, "left") + px(outer, "width")).toBeGreaterThan(
      px(inner, "left") + px(inner, "width"),
    )
    // Members visible (nothing collapsed).
    expect(screen.getByTestId("canvas-node-n_node_1")).toBeInTheDocument()
  })

  it("expanded frames share z=0 (below the node band z=1, so nodes stay on top)", () => {
    // CSS z-index is integer-only with no value between 0 and the node band —
    // so all expanded frames share z=0 (== P2); nesting reads via the recursive
    // bounds. The depth-z lives on the opaque collapsed cards (next test).
    render(<GraphCanvas canvas={nestedCanvas(false, false)} selectedNodeId={null} {...cb} />)
    expect(z(screen.getByTestId("canvas-container-A"))).toBe(0)
    expect(z(screen.getByTestId("canvas-container-B"))).toBe(0)
  })

  it("depth-scaled z on the OPAQUE collapsed card: inner (1+depth) paints above the outer frame", () => {
    // Inner B collapsed at depth 1 → z = 2; outer A expanded → z = 0.
    render(<GraphCanvas canvas={nestedCanvas(false, true)} selectedNodeId={null} {...cb} />)
    const outer = screen.getByTestId("canvas-container-A")
    const inner = screen.getByTestId("canvas-container-B")
    expect(z(outer)).toBe(0) // expanded outer
    expect(z(inner)).toBe(2) // collapsed inner, 1 + depth(1)
    expect(z(inner)).toBeGreaterThan(z(outer))
  })

  it("collapsing the OUTER hides the inner box AND its member nodes", () => {
    render(<GraphCanvas canvas={nestedCanvas(true, false)} selectedNodeId={null} {...cb} />)
    // Outer shows as a collapsed card; inner box + member nodes are gone.
    expect(screen.getByTestId("canvas-container-A")).toHaveAttribute(
      "data-collapsed",
      "true",
    )
    expect(screen.queryByTestId("canvas-container-B")).not.toBeInTheDocument()
    expect(screen.queryByTestId("canvas-node-n_node_1")).not.toBeInTheDocument()
    expect(screen.queryByTestId("canvas-node-n_node_2")).not.toBeInTheDocument()
  })

  it("collapsing only the INNER renders its collapsed card inside the expanded outer", () => {
    render(<GraphCanvas canvas={nestedCanvas(false, true)} selectedNodeId={null} {...cb} />)
    const outer = screen.getByTestId("canvas-container-A")
    const inner = screen.getByTestId("canvas-container-B")
    expect(outer).toHaveAttribute("data-collapsed", "false")
    expect(inner).toHaveAttribute("data-collapsed", "true")
    // The outer encloses the inner's collapsed card.
    expect(px(outer, "left")).toBeLessThanOrEqual(px(inner, "left"))
    expect(px(outer, "left") + px(outer, "width")).toBeGreaterThanOrEqual(
      px(inner, "left") + px(inner, "width"),
    )
    // Member nodes hidden (inside collapsed inner).
    expect(screen.queryByTestId("canvas-node-n_node_1")).not.toBeInTheDocument()
    // Inner collapsed card in the node band, above the outer frame.
    expect(z(inner)).toBeGreaterThan(z(outer))
  })

  it("a PURE-NESTING outer (only container-members, no direct nodes) renders", () => {
    // The P2 empty-member guard counted node-members only → would skip this.
    render(<GraphCanvas canvas={nestedCanvas(false, false)} selectedNodeId={null} {...cb} />)
    // A has only a container-member (B) — it must still render.
    expect(screen.getByTestId("canvas-container-A")).toBeInTheDocument()
  })

  it("REGRESSION — a non-nested (flat) container renders byte-identical to P2", () => {
    // Flat expanded container → z=0 frame; flat collapsed → z=1 card.
    const flatExpanded = makeCanvas({
      containers: [
        {
          id: "c1",
          members: [
            { kind: "node" as const, id: "n_node_1" },
            { kind: "node" as const, id: "n_node_2" },
          ],
          collapsed: false,
        },
      ],
    })
    const { rerender } = render(
      <GraphCanvas canvas={flatExpanded} selectedNodeId={null} {...cb} />,
    )
    const frame = screen.getByTestId("canvas-container-c1")
    expect(frame).toHaveAttribute("data-collapsed", "false")
    expect(z(frame)).toBe(0) // P2 expanded z
    expect(screen.getByTestId("canvas-node-n_node_1")).toBeInTheDocument()

    const flatCollapsed = makeCanvas({
      containers: [
        {
          id: "c1",
          members: [
            { kind: "node" as const, id: "n_node_1" },
            { kind: "node" as const, id: "n_node_2" },
          ],
          collapsed: true,
        },
      ],
    })
    rerender(<GraphCanvas canvas={flatCollapsed} selectedNodeId={null} {...cb} />)
    const card = screen.getByTestId("canvas-container-c1")
    expect(card).toHaveAttribute("data-collapsed", "true")
    expect(z(card)).toBe(1) // P2 collapsed z
    expect(screen.queryByTestId("canvas-node-n_node_1")).not.toBeInTheDocument()
  })
})

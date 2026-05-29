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
    expect(onSelectNode).toHaveBeenCalledWith("n_node_1")
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
    expect(onSelectNode).toHaveBeenCalledWith("n_node_1")
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
    expect(onSelectNode).toHaveBeenCalledWith("n_node_2")
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

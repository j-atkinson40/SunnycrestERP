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

  it("renders the node label + id", () => {
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
    expect(screen.getByText("n_node_1")).toBeInTheDocument()
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


// ── Phase B sub-arc B-3 §(b) — render from node.config visual props ───
//
// nodeShape -> SVG shape backdrop; labelPosition -> label placement;
// accentToken -> shape stroke. Defaults reproduce B-1's fixed look.

function nodeWithConfig(config: Record<string, unknown>): CanvasState {
  return {
    version: 1,
    nodes: [{ id: "n1", type: "decision", label: "Check", position: { x: 40, y: 40 }, config }],
    edges: [],
  }
}

// Test resolver standing in for the registry per-type default (the real
// one is getByName-backed in WorkflowEditorPage). Keeps GraphCanvas.test
// registry-free — the injected-resolver contract is what we exercise.
const TYPE_DEFAULTS: Record<string, string> = {
  decision: "diamond",
  start: "circle",
  end: "circle",
  parallel_split: "bar",
  parallel_join: "bar",
}
const testTypeDefault = (nodeType: string): unknown => TYPE_DEFAULTS[nodeType]

describe("GraphCanvas — B-3 render-from-config", () => {
  it("derives the type-default shape (decision → diamond) when config has no nodeShape", () => {
    // B-3 completion: a decision node with config:{} renders its injected
    // type-default (diamond) — NOT rounded-rect. The funeral_cascade case
    // (seeded nodes carry no nodeShape; the page injects the registry
    // default via resolveTypeDefaultShape).
    render(
      <GraphCanvas
        canvas={nodeWithConfig({})}
        selectedNodeId={null}
        onSelectNode={noop}
        onMoveNode={noop}
        onRemoveNode={noop}
        resolveTypeDefaultShape={testTypeDefault}
      />,
    )
    const card = screen.getByTestId("canvas-node-n1")
    expect(card).toHaveAttribute("data-node-shape", "diamond")
    expect(screen.getByTestId("node-shape-diamond")).toBeInTheDocument()
  })

  it("explicit config.nodeShape overrides the type-default (decision + pill → pill)", () => {
    render(
      <GraphCanvas
        canvas={nodeWithConfig({ nodeShape: "pill" })}
        selectedNodeId={null}
        onSelectNode={noop}
        onMoveNode={noop}
        onRemoveNode={noop}
        resolveTypeDefaultShape={testTypeDefault}
      />,
    )
    expect(screen.getByTestId("canvas-node-n1")).toHaveAttribute(
      "data-node-shape",
      "pill",
    )
  })

  it("derives type-defaults for start/end (circle) + parallel_join (bar) with no config", () => {
    const canvas: CanvasState = {
      version: 1,
      nodes: [
        { id: "s", type: "start", position: { x: 0, y: 0 }, config: {} },
        { id: "j", type: "parallel_join", position: { x: 0, y: 200 }, config: {} },
        { id: "e", type: "end", position: { x: 0, y: 400 }, config: {} },
      ],
      edges: [],
    }
    render(
      <GraphCanvas
        canvas={canvas}
        selectedNodeId={null}
        onSelectNode={noop}
        onMoveNode={noop}
        onRemoveNode={noop}
        resolveTypeDefaultShape={testTypeDefault}
      />,
    )
    expect(screen.getByTestId("canvas-node-s")).toHaveAttribute("data-node-shape", "circle")
    expect(screen.getByTestId("canvas-node-j")).toHaveAttribute("data-node-shape", "bar")
    expect(screen.getByTestId("canvas-node-e")).toHaveAttribute("data-node-shape", "circle")
  })

  it("falls to rounded-rect for an unknown node type (resolver returns undefined)", () => {
    const canvas: CanvasState = {
      version: 1,
      nodes: [{ id: "u", type: "__nonexistent__", position: { x: 0, y: 0 }, config: {} }],
      edges: [],
    }
    render(
      <GraphCanvas
        canvas={canvas}
        selectedNodeId={null}
        onSelectNode={noop}
        onMoveNode={noop}
        onRemoveNode={noop}
        resolveTypeDefaultShape={testTypeDefault}
      />,
    )
    expect(screen.getByTestId("canvas-node-u")).toHaveAttribute(
      "data-node-shape",
      "rounded-rect",
    )
  })

  it("falls to rounded-rect when no resolver is provided (omitted prop)", () => {
    render(
      <GraphCanvas
        canvas={nodeWithConfig({})}
        selectedNodeId={null}
        onSelectNode={noop}
        onMoveNode={noop}
        onRemoveNode={noop}
      />,
    )
    expect(screen.getByTestId("canvas-node-n1")).toHaveAttribute(
      "data-node-shape",
      "rounded-rect",
    )
  })

  it("renders the configured nodeShape (diamond) as an SVG backdrop", () => {
    render(
      <GraphCanvas
        canvas={nodeWithConfig({ nodeShape: "diamond" })}
        selectedNodeId={null}
        onSelectNode={noop}
        onMoveNode={noop}
        onRemoveNode={noop}
      />,
    )
    expect(screen.getByTestId("canvas-node-n1")).toHaveAttribute(
      "data-node-shape",
      "diamond",
    )
    expect(screen.getByTestId("node-shape-diamond")).toBeInTheDocument()
  })

  it("renders each of the 9 shapes from config", () => {
    for (const shape of [
      "rounded-rect", "pill", "circle", "diamond", "hexagon",
      "bar", "parallelogram", "envelope", "document",
    ]) {
      const { unmount } = render(
        <GraphCanvas
          canvas={nodeWithConfig({ nodeShape: shape })}
          selectedNodeId={null}
          onSelectNode={noop}
          onMoveNode={noop}
          onRemoveNode={noop}
        />,
      )
      expect(screen.getByTestId(`node-shape-${shape}`)).toBeInTheDocument()
      unmount()
    }
  })

  it("places the label inside by default", () => {
    render(
      <GraphCanvas
        canvas={nodeWithConfig({})}
        selectedNodeId={null}
        onSelectNode={noop}
        onMoveNode={noop}
        onRemoveNode={noop}
      />,
    )
    expect(screen.getByTestId("canvas-node-n1")).toHaveAttribute(
      "data-label-position",
      "inside",
    )
  })

  it("places the label above when configured", () => {
    render(
      <GraphCanvas
        canvas={nodeWithConfig({ labelPosition: "above" })}
        selectedNodeId={null}
        onSelectNode={noop}
        onMoveNode={noop}
        onRemoveNode={noop}
      />,
    )
    const card = screen.getByTestId("canvas-node-n1")
    expect(card).toHaveAttribute("data-label-position", "above")
    expect(screen.getByTestId("canvas-node-n1-label")).toBeInTheDocument()
  })

  it("applies accentToken as the shape stroke (non-selected)", () => {
    render(
      <GraphCanvas
        canvas={nodeWithConfig({ nodeShape: "diamond", accentToken: "status-success" })}
        selectedNodeId={null}
        onSelectNode={noop}
        onMoveNode={noop}
        onRemoveNode={noop}
      />,
    )
    const polygon = screen
      .getByTestId("node-shape-diamond")
      .querySelector("polygon")
    expect(polygon?.getAttribute("stroke")).toBe("var(--status-success)")
  })

  it("selection overrides accentToken with the accent stroke", () => {
    render(
      <GraphCanvas
        canvas={nodeWithConfig({ nodeShape: "diamond", accentToken: "status-success" })}
        selectedNodeId="n1"
        onSelectNode={noop}
        onMoveNode={noop}
        onRemoveNode={noop}
      />,
    )
    const polygon = screen
      .getByTestId("node-shape-diamond")
      .querySelector("polygon")
    expect(polygon?.getAttribute("stroke")).toBe("var(--accent)")
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

  it("overlay does not alter the shape backdrop (composes over it)", () => {
    renderTrace()
    fireEvent.click(screen.getByTestId("trace-overlay-toggle"))
    // start node still renders its circle backdrop (B-3 type-default) with
    // overlay on — trace dim is an outer layer, shape is untouched.
    expect(
      screen.getByTestId("canvas-node-s").querySelector('[data-testid="node-shape-rounded-rect"], [data-testid^="node-shape-"]'),
    ).toBeInTheDocument()
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

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

describe("GraphCanvas — B-3 render-from-config", () => {
  it("defaults to rounded-rect when config has no nodeShape (B-1 parity)", () => {
    render(
      <GraphCanvas
        canvas={nodeWithConfig({})}
        selectedNodeId={null}
        onSelectNode={noop}
        onMoveNode={noop}
        onRemoveNode={noop}
      />,
    )
    const card = screen.getByTestId("canvas-node-n1")
    expect(card).toHaveAttribute("data-node-shape", "rounded-rect")
    expect(screen.getByTestId("node-shape-rounded-rect")).toBeInTheDocument()
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

/**
 * WorkflowNodePalette tests — the right-rail action palette (2026-05-29).
 *
 * Covers the family-grouped render (6 families, ordered + labeled), the
 * wrapper-level search (name + family-label match), click-to-add wiring
 * (onAdd called with the type), and the empty-search "no matches" state.
 * The registry is populated via auto-register (all 32 workflow-node
 * registrations).
 */
import { describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen, within } from "@testing-library/react"

// Populate the component registry (all 32 workflow-node registrations).
import "@/lib/visual-editor/registry/auto-register"
import { WorkflowNodePalette } from "./WorkflowNodePalette"
import {
  NODE_FAMILY_ORDER,
  NODE_FAMILY_LABELS,
  nodeTypesByFamily,
} from "@/lib/visual-editor/workflow-node-palette"

describe("WorkflowNodePalette", () => {
  it("renders all 32 node types as click-to-add items (incl. notify_via_contact_preference, 3a.1; the retired generation-focus-invocation twin stays out)", () => {
    render(<WorkflowNodePalette onAdd={vi.fn()} />)
    const items = screen
      .getAllByRole("button")
      .filter((b) =>
        b.getAttribute("data-testid")?.startsWith("node-palette-item-"),
      )
    expect(items.length).toBe(32)
  })

  it("groups types into the 6 families, ordered + labeled", () => {
    render(<WorkflowNodePalette onAdd={vi.fn()} />)
    const headers = NODE_FAMILY_ORDER.map((f) => NODE_FAMILY_LABELS[f])
    for (const label of headers) {
      expect(screen.getByText(label)).toBeInTheDocument()
    }
    // Section order matches NODE_FAMILY_ORDER (top → bottom).
    const cats = screen.getAllByTestId("widget-palette-category")
    const renderedFamilies = cats.map((c) => c.getAttribute("data-category-id"))
    expect(renderedFamilies).toEqual([...NODE_FAMILY_ORDER])
  })

  it("clicking an item calls onAdd with that node type", () => {
    const onAdd = vi.fn()
    render(<WorkflowNodePalette onAdd={onAdd} />)
    fireEvent.click(screen.getByTestId("node-palette-item-action"))
    expect(onAdd).toHaveBeenCalledWith("action")
  })

  it("search filters items by plain-language name", () => {
    render(<WorkflowNodePalette onAdd={vi.fn()} />)
    fireEvent.change(screen.getByTestId("workflow-node-palette-search"), {
      target: { value: "email" },
    })
    // send_email survives; an unrelated type (start) is filtered out.
    expect(screen.getByTestId("node-palette-item-send_email")).toBeInTheDocument()
    expect(screen.queryByTestId("node-palette-item-start")).toBeNull()
  })

  it("search matches the FAMILY label (typing 'flow' surfaces Flow-control)", () => {
    render(<WorkflowNodePalette onAdd={vi.fn()} />)
    fireEvent.change(screen.getByTestId("workflow-node-palette-search"), {
      target: { value: "flow" },
    })
    // The whole flow-control family surfaces (e.g. decision); a
    // non-flow type (send_email) is filtered out.
    expect(screen.getByTestId("node-palette-item-decision")).toBeInTheDocument()
    expect(screen.queryByTestId("node-palette-item-send_email")).toBeNull()
    const cats = screen.getAllByTestId("widget-palette-category")
    expect(cats.map((c) => c.getAttribute("data-category-id"))).toEqual([
      "flow-control",
    ])
  })

  it("shows a no-matches state when the search matches nothing", () => {
    render(<WorkflowNodePalette onAdd={vi.fn()} />)
    fireEvent.change(screen.getByTestId("workflow-node-palette-search"), {
      target: { value: "zzzznotatype" },
    })
    expect(
      screen.getByTestId("workflow-node-palette-no-matches"),
    ).toBeInTheDocument()
    expect(screen.queryByTestId("widget-palette")).toBeNull()
  })

  it("each family section lists only its own types", () => {
    render(<WorkflowNodePalette onAdd={vi.fn()} />)
    const flow = screen
      .getAllByTestId("widget-palette-category")
      .find((c) => c.getAttribute("data-category-id") === "flow-control")!
    // decision is flow-control; action is action-data → not in this section.
    expect(
      within(flow).getByTestId("node-palette-item-decision"),
    ).toBeInTheDocument()
    expect(
      within(flow).queryByTestId("node-palette-item-action"),
    ).toBeNull()
  })
})

describe("workflow-node-palette vocab — nodeTypesByFamily", () => {
  it("orders groups by NODE_FAMILY_ORDER + omits empty families", () => {
    const groups = nodeTypesByFamily([
      { name: "decision", displayName: "Decision" }, // flow-control
      { name: "start", displayName: "Start" }, // lifecycle
    ])
    // lifecycle precedes flow-control per NODE_FAMILY_ORDER; the other 4
    // families are empty → omitted.
    expect(groups.map((g) => g.family)).toEqual(["lifecycle", "flow-control"])
    expect(groups[0].types[0].name).toBe("start")
    expect(groups[1].types[0].name).toBe("decision")
  })
})

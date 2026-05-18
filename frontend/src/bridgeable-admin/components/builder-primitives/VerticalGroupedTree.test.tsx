import { describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen } from "@testing-library/react"

import { VerticalGroupedTree, type TreeNode } from "./VerticalGroupedTree"

function makeGroups(): TreeNode[] {
  return [
    {
      id: "v-mfg",
      label: "Manufacturing",
      iconName: "box",
      children: [
        {
          id: "v-mfg-prod",
          label: "Production",
          children: [
            { id: "core-1", label: "Kanban dispatch", iconName: "square" },
          ],
        },
      ],
    },
    { id: "v-fh", label: "Funeral Home", iconName: "users" },
  ]
}

describe("VerticalGroupedTree", () => {
  it("renders top-level groups", () => {
    render(
      <VerticalGroupedTree
        groups={makeGroups()}
        selectedId={null}
        onSelect={() => {}}
        expandedIds={new Set()}
        onExpandChange={() => {}}
      />,
    )
    expect(screen.getByText("Manufacturing")).toBeInTheDocument()
    expect(screen.getByText("Funeral Home")).toBeInTheDocument()
    // Nested child should NOT render when parent collapsed.
    expect(screen.queryByText("Production")).not.toBeInTheDocument()
  })

  it("renders nested children when parent expanded", () => {
    render(
      <VerticalGroupedTree
        groups={makeGroups()}
        selectedId={null}
        onSelect={() => {}}
        expandedIds={new Set(["v-mfg", "v-mfg-prod"])}
        onExpandChange={() => {}}
      />,
    )
    expect(screen.getByText("Production")).toBeInTheDocument()
    expect(screen.getByText("Kanban dispatch")).toBeInTheDocument()
  })

  it("fires onExpandChange when chevron clicked", () => {
    const onExpandChange = vi.fn()
    render(
      <VerticalGroupedTree
        groups={makeGroups()}
        selectedId={null}
        onSelect={() => {}}
        expandedIds={new Set()}
        onExpandChange={onExpandChange}
      />,
    )
    fireEvent.click(screen.getByTestId("tree-chevron-v-mfg"))
    expect(onExpandChange).toHaveBeenCalledWith("v-mfg", true)
  })

  it("fires onSelect when row label clicked (not the chevron)", () => {
    const onSelect = vi.fn()
    render(
      <VerticalGroupedTree
        groups={makeGroups()}
        selectedId={null}
        onSelect={onSelect}
        expandedIds={new Set()}
        onExpandChange={() => {}}
      />,
    )
    fireEvent.click(screen.getByTestId("tree-node-v-fh"))
    expect(onSelect).toHaveBeenCalledWith("v-fh", expect.objectContaining({ id: "v-fh" }))
  })

  it("applies selected styling to the selected node", () => {
    render(
      <VerticalGroupedTree
        groups={makeGroups()}
        selectedId="v-fh"
        onSelect={() => {}}
        expandedIds={new Set()}
        onExpandChange={() => {}}
      />,
    )
    expect(screen.getByTestId("tree-node-v-fh")).toHaveAttribute(
      "data-selected",
      "true",
    )
    expect(screen.getByTestId("tree-node-v-mfg")).toHaveAttribute(
      "data-selected",
      "false",
    )
  })

  it("renders the accessory slot when provided + does not propagate accessory click", () => {
    const onSelect = vi.fn()
    render(
      <VerticalGroupedTree
        groups={makeGroups()}
        selectedId={null}
        onSelect={onSelect}
        expandedIds={new Set()}
        onExpandChange={() => {}}
        renderNodeAccessory={(node) =>
          node.id === "v-fh" ? <span data-testid="chip">FH</span> : null
        }
      />,
    )
    const chip = screen.getByTestId("chip")
    expect(chip).toBeInTheDocument()
    fireEvent.click(chip)
    // Accessory click should NOT bubble up to row selection.
    expect(onSelect).not.toHaveBeenCalled()
  })

  it("renders an empty-state when groups list is empty", () => {
    render(
      <VerticalGroupedTree
        groups={[]}
        selectedId={null}
        onSelect={() => {}}
        expandedIds={new Set()}
        onExpandChange={() => {}}
      />,
    )
    expect(
      screen.getByTestId("vertical-grouped-tree-empty"),
    ).toBeInTheDocument()
  })

  it("indents children based on depth", () => {
    render(
      <VerticalGroupedTree
        groups={makeGroups()}
        selectedId={null}
        onSelect={() => {}}
        expandedIds={new Set(["v-mfg", "v-mfg-prod"])}
        onExpandChange={() => {}}
      />,
    )
    expect(screen.getByTestId("tree-node-v-mfg")).toHaveAttribute(
      "data-depth",
      "0",
    )
    expect(screen.getByTestId("tree-node-v-mfg-prod")).toHaveAttribute(
      "data-depth",
      "1",
    )
    expect(screen.getByTestId("tree-node-core-1")).toHaveAttribute(
      "data-depth",
      "2",
    )
  })
})

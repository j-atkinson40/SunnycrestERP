/**
 * GraphCanvas — Phase 1b "Proposed" treatment is ADDITIVE (jsdom).
 *
 * Proves the BYTE-IDENTICAL-WHEN-NO-CANDIDATE invariant at the GraphCanvas
 * layer: without the `proposed` prop, the canvas root is exactly as before
 * (same className, no data-proposed attribute). With `proposed`, it gains the
 * dashed-accent frame + the data attribute — and nothing else changes.
 */
import { describe, it, expect } from "vitest"
import { render } from "@testing-library/react"

import { GraphCanvas } from "./GraphCanvas"
import type { CanvasState } from "@/bridgeable-admin/services/workflow-templates-service"

const noop = () => {}
const CANVAS: CanvasState = { version: 1, nodes: [], edges: [] }

const baseProps = {
  canvas: CANVAS,
  selectedNodeId: null,
  selectedNodeIds: [],
  onSelectNode: noop,
  onMoveNode: noop,
  onRemoveNode: noop,
}

describe("GraphCanvas proposed treatment (additive)", () => {
  it("without `proposed`, the root is byte-identical (original className, no data-proposed)", () => {
    const { container } = render(<GraphCanvas {...baseProps} />)
    const root = container.firstChild as HTMLElement
    expect(root.className).toBe("flex flex-1 flex-col overflow-hidden")
    expect(root.getAttribute("data-proposed")).toBeNull()
  })

  it("with `proposed`, the root gains the dashed-accent frame + data-proposed", () => {
    const { container } = render(<GraphCanvas {...baseProps} proposed />)
    const root = container.firstChild as HTMLElement
    expect(root.getAttribute("data-proposed")).toBe("true")
    expect(root.className).toContain("border-dashed")
    expect(root.className).toContain("border-accent")
  })
})

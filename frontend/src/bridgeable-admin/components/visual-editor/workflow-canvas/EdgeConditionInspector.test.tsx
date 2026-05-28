/**
 * EdgeConditionInspector.test — Phase B sub-arc B-5.
 */
import { describe, it, expect, vi } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"

import { EdgeConditionInspector } from "./EdgeConditionInspector"
import type { CanvasEdge } from "@/bridgeable-admin/services/workflow-templates-service"

const edge: CanvasEdge = {
  id: "e_a_b",
  source: "a",
  target: "b",
  condition: "{{ x > 0 }}",
  label: "approved",
}

describe("EdgeConditionInspector", () => {
  it("renders id (read-only), condition, label", () => {
    render(<EdgeConditionInspector edge={edge} onChange={() => {}} />)
    expect(screen.getByTestId("edge-inspector-id")).toHaveTextContent("e_a_b")
    expect((screen.getByTestId("edge-inspector-condition") as HTMLInputElement).value).toBe("{{ x > 0 }}")
    expect((screen.getByTestId("edge-inspector-label") as HTMLInputElement).value).toBe("approved")
  })

  it("emits the full next edge on condition edit (preserves source/target/id)", () => {
    const onChange = vi.fn()
    render(<EdgeConditionInspector edge={edge} onChange={onChange} />)
    fireEvent.change(screen.getByTestId("edge-inspector-condition"), {
      target: { value: "{{ y }}" },
    })
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ id: "e_a_b", source: "a", target: "b", condition: "{{ y }}" }),
    )
  })

  it("emits the full next edge on label edit", () => {
    const onChange = vi.fn()
    render(<EdgeConditionInspector edge={edge} onChange={onChange} />)
    fireEvent.change(screen.getByTestId("edge-inspector-label"), {
      target: { value: "rejected" },
    })
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ id: "e_a_b", label: "rejected" }),
    )
  })

  it("handles an edge with no condition/label (empty inputs)", () => {
    render(
      <EdgeConditionInspector
        edge={{ id: "e1", source: "a", target: "b" }}
        onChange={() => {}}
      />,
    )
    expect((screen.getByTestId("edge-inspector-condition") as HTMLInputElement).value).toBe("")
    expect((screen.getByTestId("edge-inspector-label") as HTMLInputElement).value).toBe("")
  })
})

/**
 * WorkflowAssistantRail — Phase 1b rail behavior tests (jsdom).
 *   - prompt input → Generate calls onGenerate with the trimmed text
 *   - generating → spinner
 *   - error → friendly message
 *   - candidate → accept/reject call their callbacks; dirty draft → warning
 *   - collapse / expand toggle
 */
import { describe, it, expect, vi } from "vitest"
import { fireEvent, render, screen } from "@testing-library/react"

import { WorkflowAssistantRail } from "./WorkflowAssistantRail"
import type { CanvasState } from "@/bridgeable-admin/services/workflow-templates-service"

const CANDIDATE: CanvasState = {
  version: 1,
  nodes: [
    { id: "n_start", type: "start", position: { x: 0, y: 0 }, config: {} },
    { id: "n_dec", type: "decision", position: { x: 0, y: 120 }, config: {} },
    { id: "n_end", type: "end", position: { x: 0, y: 240 }, config: {} },
  ],
  edges: [
    { id: "e1", source: "n_start", target: "n_dec" },
    { id: "e2", source: "n_dec", target: "n_end" },
  ],
}

function base() {
  return {
    vertical: "funeral_home",
    workflowType: "t",
    isDraftDirty: false,
    generating: false,
    error: null as string | null,
    candidate: null as CanvasState | null,
    onGenerate: vi.fn(),
    onAccept: vi.fn(),
    onReject: vi.fn(),
  }
}

describe("WorkflowAssistantRail", () => {
  it("Generate calls onGenerate with the trimmed input", () => {
    const p = base()
    render(<WorkflowAssistantRail {...p} />)
    fireEvent.change(screen.getByTestId("workflow-assistant-input"), {
      target: { value: "  build a vault order flow  " },
    })
    fireEvent.click(screen.getByTestId("workflow-assistant-generate"))
    expect(p.onGenerate).toHaveBeenCalledWith("build a vault order flow")
  })

  it("Generate is disabled with empty input", () => {
    const p = base()
    render(<WorkflowAssistantRail {...p} />)
    expect(screen.getByTestId("workflow-assistant-generate")).toBeDisabled()
  })

  it("shows the generating spinner state", () => {
    const p = { ...base(), generating: true }
    render(<WorkflowAssistantRail {...p} />)
    expect(screen.getByTestId("workflow-assistant-generating")).toBeInTheDocument()
  })

  it("shows a friendly error message", () => {
    const p = { ...base(), error: "The assistant isn't available right now." }
    render(<WorkflowAssistantRail {...p} />)
    expect(screen.getByTestId("workflow-assistant-error")).toHaveTextContent(
      /isn't available/i,
    )
  })

  it("candidate → accept/reject call their callbacks", () => {
    const p = { ...base(), candidate: CANDIDATE }
    render(<WorkflowAssistantRail {...p} />)
    expect(screen.getByTestId("workflow-assistant-candidate")).toBeInTheDocument()
    fireEvent.click(screen.getByTestId("workflow-assistant-accept"))
    expect(p.onAccept).toHaveBeenCalledTimes(1)
    fireEvent.click(screen.getByTestId("workflow-assistant-reject"))
    expect(p.onReject).toHaveBeenCalledTimes(1)
  })

  it("warns that accept replaces a dirty draft only when the draft is dirty", () => {
    const clean = { ...base(), candidate: CANDIDATE, isDraftDirty: false }
    const { rerender } = render(<WorkflowAssistantRail {...clean} />)
    expect(screen.queryByTestId("workflow-assistant-dirty-warning")).toBeNull()
    rerender(<WorkflowAssistantRail {...clean} isDraftDirty />)
    expect(screen.getByTestId("workflow-assistant-dirty-warning")).toBeInTheDocument()
  })

  it("collapses + re-expands", () => {
    const p = base()
    render(<WorkflowAssistantRail {...p} />)
    fireEvent.click(screen.getByTestId("workflow-assistant-rail-collapse"))
    expect(screen.getByTestId("workflow-assistant-rail")).toHaveAttribute(
      "data-collapsed",
      "true",
    )
    fireEvent.click(screen.getByTestId("workflow-assistant-rail-expand"))
    expect(screen.getByTestId("workflow-assistant-rail")).toHaveAttribute(
      "data-collapsed",
      "false",
    )
  })
})

/**
 * BespokeNodePane.test — P3c. The pane routes the 2 bespoke invoke_* types
 * to their existing bespoke configs (which are shared verbatim with
 * WorkflowsTab's NodeConfigForm and have their own tests). Here we assert
 * the type → config routing + the onChange passthrough — the only logic the
 * pane itself adds.
 */
import { describe, it, expect, vi } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"

import { BespokeNodePane } from "./BespokeNodePane"
import type { CanvasNode } from "@/bridgeable-admin/services/workflow-templates-service"

function node(type: string, config: Record<string, unknown> = {}): CanvasNode {
  return { id: "n_1", type, label: "", position: { x: 0, y: 0 }, config }
}

describe("BespokeNodePane", () => {
  it("routes invoke_generation_focus → InvokeGenerationFocusConfig", () => {
    render(<BespokeNodePane node={node("invoke_generation_focus")} onChange={vi.fn()} />)
    expect(screen.getByTestId("bespoke-node-pane")).toBeInTheDocument()
    expect(screen.getByTestId("wf-invoke-generation-focus-config")).toBeInTheDocument()
    expect(screen.queryByTestId("wf-invoke-review-focus-config")).toBeNull()
  })

  it("routes invoke_review_focus → InvokeReviewFocusConfig", () => {
    render(<BespokeNodePane node={node("invoke_review_focus")} onChange={vi.fn()} />)
    expect(screen.getByTestId("wf-invoke-review-focus-config")).toBeInTheDocument()
    expect(screen.queryByTestId("wf-invoke-generation-focus-config")).toBeNull()
  })

  it("passes onChange through (a review_focus_id edit persists the full config)", () => {
    const onChange = vi.fn()
    render(<BespokeNodePane node={node("invoke_review_focus")} onChange={onChange} />)
    fireEvent.change(screen.getByTestId("wf-invoke-review-focus-slug"), {
      target: { value: "decedent_info_review" },
    })
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ review_focus_id: "decedent_info_review" }),
    )
  })

  it("renders the empty wrapper for a non-bespoke type (defensive — never routed here in practice)", () => {
    render(<BespokeNodePane node={node("action")} onChange={vi.fn()} />)
    expect(screen.getByTestId("bespoke-node-pane")).toBeInTheDocument()
    expect(screen.queryByTestId("wf-invoke-generation-focus-config")).toBeNull()
    expect(screen.queryByTestId("wf-invoke-review-focus-config")).toBeNull()
  })
})

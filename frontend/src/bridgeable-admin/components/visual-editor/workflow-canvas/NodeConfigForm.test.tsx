/**
 * NodeConfigForm.test — Phase B sub-arc B-3 (dispatch ladder).
 *
 * Asserts the per-type config dispatch: bespoke override if registered
 * (invoke_generation_focus / invoke_review_focus), else the schema-driven
 * RegistryDrivenConfig — and that the pre-B-3 JSON-textarea fallback is
 * gone (every canonical node type now has a real inspector). Universal
 * type/id/label/edges UI is preserved.
 */

import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@testing-library/react"

import "@/lib/visual-editor/registry/auto-register"
import { NodeConfigForm } from "./NodeConfigForm"
import type { CanvasNode } from "@/bridgeable-admin/services/workflow-templates-service"

function node(type: string, config: Record<string, unknown> = {}): CanvasNode {
  return { id: "n_1", type, label: "", position: { x: 0, y: 0 }, config }
}

function renderForm(n: CanvasNode) {
  return render(
    <NodeConfigForm
      node={n}
      allNodes={[n]}
      outgoingEdges={[]}
      onPatch={vi.fn()}
      onAddEdge={vi.fn()}
      onRemoveEdge={vi.fn()}
    />,
  )
}

describe("NodeConfigForm — B-3 per-type dispatch", () => {
  it("dispatches invoke_generation_focus to the bespoke config", () => {
    renderForm(node("invoke_generation_focus"))
    expect(
      screen.getByTestId("wf-invoke-generation-focus-config"),
    ).toBeInTheDocument()
    expect(screen.queryByTestId("registry-driven-config")).not.toBeInTheDocument()
  })

  it("dispatches invoke_review_focus to the bespoke config", () => {
    renderForm(node("invoke_review_focus"))
    // Bespoke review config present; generic not used.
    expect(screen.queryByTestId("registry-driven-config")).not.toBeInTheDocument()
  })

  it("dispatches a generic type (ai_prompt) to RegistryDrivenConfig", () => {
    renderForm(node("ai_prompt"))
    expect(screen.getByTestId("registry-driven-config")).toBeInTheDocument()
    expect(screen.getByTestId("prop-promptKey")).toBeInTheDocument()
  })

  it("dispatches a structural type (start) to RegistryDrivenConfig (visual props)", () => {
    renderForm(node("start"))
    expect(screen.getByTestId("registry-driven-config")).toBeInTheDocument()
    expect(screen.getByTestId("prop-nodeShape")).toBeInTheDocument()
  })

  it("removed the pre-B-3 JSON-textarea fallback entirely", () => {
    renderForm(node("create_record"))
    expect(
      screen.queryByTestId("node-config-config-textarea"),
    ).not.toBeInTheDocument()
    expect(screen.getByTestId("registry-driven-config")).toBeInTheDocument()
  })

  it("preserves the universal type / id / label controls", () => {
    renderForm(node("action"))
    expect(screen.getByTestId("node-config-type-select")).toBeInTheDocument()
    expect(screen.getByTestId("node-config-id-input")).toBeInTheDocument()
    expect(screen.getByTestId("node-config-label-input")).toBeInTheDocument()
  })
})

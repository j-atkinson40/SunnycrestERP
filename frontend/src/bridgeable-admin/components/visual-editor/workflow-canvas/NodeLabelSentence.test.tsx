/**
 * NodeLabelSentence tests — inline-params P1 render component. Renders
 * literals as text + slots as read-only token spans (set = accent chip;
 * unset = dimmed placeholder); falls back to plain text for unknown types.
 */
import { describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen } from "@testing-library/react"

import "@/lib/visual-editor/registry/auto-register"
import { NodeLabelSentence } from "./NodeLabelSentence"

describe("NodeLabelSentence", () => {
  it("renders set params as value tokens + unset (empty-default) as placeholder tokens", () => {
    render(
      <NodeLabelSentence
        nodeId="n1"
        nodeType="generate_document"
        config={{ entityBinding: "case" }}
      />,
    )
    // set value token
    const eb = screen.getByTestId("node-token-n1-entityBinding")
    expect(eb).toHaveTextContent("case")
    expect(eb.getAttribute("data-token-placeholder")).toBe("false")
    // unset + empty default → dimmed placeholder
    const tpl = screen.getByTestId("node-token-n1-templateKey")
    expect(tpl.getAttribute("data-token-placeholder")).toBe("true")
    expect(tpl).toHaveTextContent("[template key]")
    // unset BUT non-empty default ("pdf") → value token, not placeholder
    const out = screen.getByTestId("node-token-n1-outputFormat")
    expect(out.getAttribute("data-token-placeholder")).toBe("false")
    expect(out).toHaveTextContent("pdf")
    // literal prose present
    expect(screen.getByTestId("node-sentence-n1")).toHaveTextContent(
      /Generate .* for .* as/,
    )
  })

  it("a no-slot type renders the plain template, no tokens", () => {
    render(<NodeLabelSentence nodeId="s" nodeType="start" config={{}} />)
    expect(screen.getByTestId("node-sentence-s")).toHaveTextContent("Start")
    expect(screen.queryByTestId(/node-token-s-/)).toBeNull()
  })

  it("falls back to plain text for an unknown type (no template)", () => {
    render(
      <NodeLabelSentence
        nodeId="u"
        nodeType="__nope__"
        config={{}}
        fallback="My custom node"
      />,
    )
    expect(screen.getByTestId("node-sentence-u")).toHaveTextContent("My custom node")
  })

  it("object/array params render as summaries", () => {
    render(
      <NodeLabelSentence
        nodeId="d"
        nodeType="decision"
        config={{ branches: [1, 2, 3] }}
      />,
    )
    expect(screen.getByTestId("node-token-d-branches")).toHaveTextContent("3 branches")
  })

  // ── P2a — clickable simple-type tokens (popover editors) ───────────

  it("without onEditParam, all tokens are read-only (P1 behavior)", () => {
    render(
      <NodeLabelSentence nodeId="n1" nodeType="action" config={{ actionType: "x" }} />,
    )
    expect(
      screen.getByTestId("node-token-n1-actionType").getAttribute("data-token-editable"),
    ).toBe("false")
  })

  it("with onEditParam, a simple (string) token is editable + click opens the popover editor", () => {
    render(
      <NodeLabelSentence
        nodeId="n1"
        nodeType="action"
        config={{ actionType: "ship" }}
        onEditParam={vi.fn()}
      />,
    )
    const token = screen.getByTestId("node-token-n1-actionType")
    expect(token.getAttribute("data-token-editable")).toBe("true")
    fireEvent.click(token)
    // popover opened → the PropControlDispatcher editor is present
    expect(screen.getByTestId("node-token-editor-n1-actionType")).toBeInTheDocument()
  })

  it("editing the popover control fires onEditParam(param, value)", () => {
    const onEditParam = vi.fn()
    render(
      <NodeLabelSentence
        nodeId="n1"
        nodeType="action"
        config={{ actionType: "ship" }}
        onEditParam={onEditParam}
      />,
    )
    fireEvent.click(screen.getByTestId("node-token-n1-actionType"))
    const input = screen.getByRole("textbox")
    fireEvent.change(input, { target: { value: "deliver" } })
    expect(onEditParam).toHaveBeenCalledWith("actionType", "deliver")
  })

  it("an UNSET simple token (placeholder) is still editable (unset→set)", () => {
    render(
      <NodeLabelSentence
        nodeId="n1"
        nodeType="action"
        config={{}}
        onEditParam={vi.fn()}
      />,
    )
    const token = screen.getByTestId("node-token-n1-actionType")
    expect(token.getAttribute("data-token-placeholder")).toBe("true")
    expect(token.getAttribute("data-token-editable")).toBe("true")
  })

  // ── P2b — clickable COMPLEX-type tokens (array / componentReference) ──
  // Only `branches` (array, on decision) + `focusTemplateName`
  // (componentReference, on the 3 focus types) are slotted complex params
  // across the 32 templates; object editability is covered at the
  // logic/dispatcher level (no template slots an object param today).

  it("an ARRAY token (decision.branches) is editable + opens ArrayControl", () => {
    render(
      <NodeLabelSentence
        nodeId="d"
        nodeType="decision"
        config={{ branches: ["a"] }}
        onEditParam={vi.fn()}
      />,
    )
    const token = screen.getByTestId("node-token-d-branches")
    expect(token.getAttribute("data-token-editable")).toBe("true")
    fireEvent.click(token)
    // ArrayControl rendered in the popover (its add affordance present).
    expect(screen.getByTestId("node-token-editor-d-branches-add")).toBeInTheDocument()
  })

  it("editing an ARRAY token persists the WHOLE array via onEditParam", () => {
    const onEditParam = vi.fn()
    render(
      <NodeLabelSentence
        nodeId="d"
        nodeType="decision"
        config={{ branches: ["a"] }}
        onEditParam={onEditParam}
      />,
    )
    fireEvent.click(screen.getByTestId("node-token-d-branches"))
    fireEvent.click(screen.getByTestId("node-token-editor-d-branches-add"))
    // Whole-key merge: value is the full next array, not a partial.
    expect(onEditParam).toHaveBeenCalledWith("branches", ["a", ""])
  })

  it("a componentReference token (generation-focus-invocation.focusTemplateName) is editable + persists", () => {
    const onEditParam = vi.fn()
    render(
      <NodeLabelSentence
        nodeId="g"
        nodeType="generation-focus-invocation"
        config={{}}
        onEditParam={onEditParam}
      />,
    )
    const token = screen.getByTestId("node-token-g-focusTemplateName")
    expect(token.getAttribute("data-token-editable")).toBe("true")
    fireEvent.click(token)
    // ComponentReferenceControl is a <select> (the empty option always
    // exists); changing it fires the whole-value onEditParam.
    const select = screen.getByTestId("node-token-editor-g-focusTemplateName")
    fireEvent.change(select, { target: { value: "" } })
    expect(onEditParam).toHaveBeenCalledWith("focusTemplateName", "")
  })

  // ── THE GUARD — bespoke-namespace types stay read-only ──
  // invoke_generation_focus / invoke_review_focus author config.focus_id /
  // config.review_focus_id; their {focusTemplateName} token maps to a key
  // the authoring path never writes. Inline-editing it would write a
  // phantom key the backend ignores → these tokens MUST stay read-only.
  // Locks the divergence so a future patch can't silently re-enable it.

  it("GUARD: invoke_generation_focus {focusTemplateName} stays read-only (phantom-key)", () => {
    render(
      <NodeLabelSentence
        nodeId="ig"
        nodeType="invoke_generation_focus"
        config={{ focusTemplateName: "some-tpl" }}
        onEditParam={vi.fn()}
      />,
    )
    expect(
      screen.getByTestId("node-token-ig-focusTemplateName").getAttribute("data-token-editable"),
    ).toBe("false")
  })

  it("GUARD: invoke_review_focus {focusTemplateName} stays read-only (phantom-key)", () => {
    render(
      <NodeLabelSentence
        nodeId="ir"
        nodeType="invoke_review_focus"
        config={{ focusTemplateName: "some-tpl" }}
        onEditParam={vi.fn()}
      />,
    )
    expect(
      screen.getByTestId("node-token-ir-focusTemplateName").getAttribute("data-token-editable"),
    ).toBe("false")
  })

  it("DISTINCTION: generation-focus-invocation {focusTemplateName} IS editable (in-scope)", () => {
    render(
      <NodeLabelSentence
        nodeId="gfi"
        nodeType="generation-focus-invocation"
        config={{ focusTemplateName: "arrangement-scribe" }}
        onEditParam={vi.fn()}
      />,
    )
    expect(
      screen.getByTestId("node-token-gfi-focusTemplateName").getAttribute("data-token-editable"),
    ).toBe("true")
  })
})

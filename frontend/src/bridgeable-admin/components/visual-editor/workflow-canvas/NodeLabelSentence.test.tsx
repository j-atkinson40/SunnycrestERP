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

  it("a COMPLEX token (componentReference) is NOT editable even with onEditParam (P2b)", () => {
    render(
      <NodeLabelSentence
        nodeId="r"
        nodeType="invoke_review_focus"
        config={{ focusTemplateName: "some-tpl" }}
        onEditParam={vi.fn()}
      />,
    )
    expect(
      screen.getByTestId("node-token-r-focusTemplateName").getAttribute("data-token-editable"),
    ).toBe("false")
  })
})

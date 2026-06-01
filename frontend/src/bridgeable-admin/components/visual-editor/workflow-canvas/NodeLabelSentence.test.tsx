/**
 * NodeLabelSentence tests — inline-params P1 render component. Renders
 * literals as text + slots as read-only token spans (set = accent chip;
 * unset = dimmed placeholder); falls back to plain text for unknown types.
 */
import { describe, expect, it } from "vitest"
import { render, screen } from "@testing-library/react"

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
})

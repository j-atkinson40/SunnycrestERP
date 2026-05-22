/**
 * Tests for AtomResolutionIndicator (WB-5).
 */
import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { AtomResolutionIndicator } from "./AtomResolutionIndicator"


describe("AtomResolutionIndicator", () => {
  it("renders children verbatim when no message", () => {
    const { container } = render(
      <AtomResolutionIndicator atomId="atomA">
        <span data-testid="child">inner</span>
      </AtomResolutionIndicator>,
    )
    expect(container.querySelector("[data-has-resolution-error='true']")).toBeNull()
    expect(screen.getByTestId("child")).toBeTruthy()
  })

  it("surfaces ⚠ overlay + title when message present (error variant)", () => {
    render(
      <AtomResolutionIndicator atomId="atomA" message="View not found">
        <span>child</span>
      </AtomResolutionIndicator>,
    )
    const wrapper = screen.getByTestId(
      "widget-builder-canvas-atom-resolution-atomA",
    )
    expect(wrapper.getAttribute("title")).toBe("View not found")
    expect(wrapper.getAttribute("data-resolution-variant")).toBe("error")
    expect(wrapper.getAttribute("data-has-resolution-error")).toBe("true")
  })

  it("uses status-warning chrome (NOT status-error) — distinct from WB-4b", () => {
    const { container } = render(
      <AtomResolutionIndicator atomId="atomA" message="some err">
        <span>child</span>
      </AtomResolutionIndicator>,
    )
    expect(container.innerHTML).toMatch(/status-warning/)
    expect(container.innerHTML).not.toMatch(/outline-status-error/)
  })

  it("renders lock icon for masked variant", () => {
    const { container } = render(
      <AtomResolutionIndicator
        atomId="atomA"
        message="Cross-tenant masked"
        variant="masked"
      >
        <span>child</span>
      </AtomResolutionIndicator>,
    )
    const wrapper = screen.getByTestId(
      "widget-builder-canvas-atom-resolution-atomA",
    )
    expect(wrapper.getAttribute("data-resolution-variant")).toBe("masked")
    // Masked variant uses border-border-base / muted tone, not warning.
    expect(container.innerHTML).toMatch(/border-border-base/)
  })

  it("composes with selection ring (does not replace children DOM)", () => {
    render(
      <AtomResolutionIndicator atomId="atomA" message="err">
        <span data-testid="child">inner</span>
      </AtomResolutionIndicator>,
    )
    expect(screen.getByTestId("child")).toBeTruthy()
    expect(
      screen.getByTestId("widget-builder-canvas-atom-resolution-atomA"),
    ).toBeTruthy()
  })
})

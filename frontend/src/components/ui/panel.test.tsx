/**
 * Panel chrome — Builder Craft Arc Phase 1a primitive tests.
 * Slots render with the canonical token classes; className merge preserves
 * visual-parity overrides (the adoption contract).
 */
import { describe, it, expect } from "vitest"
import { render, screen } from "@testing-library/react"

import {
  Panel,
  PanelHeader,
  PanelTitle,
  PanelActions,
  PanelBody,
  PanelFooter,
} from "./panel"

describe("Panel chrome", () => {
  it("renders the full slot composition with data-slot markers", () => {
    render(
      <Panel data-testid="p">
        <PanelHeader>
          <PanelTitle>Title</PanelTitle>
          <PanelActions>
            <button>act</button>
          </PanelActions>
        </PanelHeader>
        <PanelBody>body</PanelBody>
        <PanelFooter>footer</PanelFooter>
      </Panel>,
    )
    const panel = screen.getByTestId("p")
    expect(panel.getAttribute("data-slot")).toBe("panel")
    expect(panel.querySelector('[data-slot="panel-header"]')).toBeTruthy()
    expect(panel.querySelector('[data-slot="panel-title"]')).toBeTruthy()
    expect(panel.querySelector('[data-slot="panel-actions"]')).toBeTruthy()
    expect(panel.querySelector('[data-slot="panel-body"]')).toBeTruthy()
    expect(panel.querySelector('[data-slot="panel-footer"]')).toBeTruthy()
  })

  it("header carries the border-separator token classes", () => {
    render(<PanelHeader data-testid="h">x</PanelHeader>)
    const cls = screen.getByTestId("h").className
    expect(cls).toContain("border-b")
    expect(cls).toContain("border-border-subtle")
  })

  it("title is a heading with the canonical type classes", () => {
    render(<PanelTitle>The title</PanelTitle>)
    const h = screen.getByRole("heading", { name: "The title" })
    expect(h.className).toContain("text-content-strong")
  })

  it("className merge lets adopters keep visual parity (override paddings/surfaces)", () => {
    render(
      <PanelHeader data-testid="h" className="bg-surface-elevated px-6">
        x
      </PanelHeader>,
    )
    const cls = screen.getByTestId("h").className
    expect(cls).toContain("bg-surface-elevated")
    expect(cls).toContain("px-6")
    // tailwind-merge drops the default px-4 in favor of the override
    expect(cls).not.toMatch(/\bpx-4\b/)
  })

  it("body is the scrollable flex-1 region", () => {
    render(<PanelBody data-testid="b">x</PanelBody>)
    const cls = screen.getByTestId("b").className
    expect(cls).toContain("flex-1")
    expect(cls).toContain("overflow-y-auto")
  })
})

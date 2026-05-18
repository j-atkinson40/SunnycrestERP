/**
 * PropertyPanel unit tests — sub-arc C-1.
 */
import { describe, it, expect, vi } from "vitest"
import { fireEvent, render, screen } from "@testing-library/react"

import {
  PropertyPanel,
  PropertySection,
  PropertyRow,
} from "./PropertyPanel"

describe("PropertyPanel", () => {
  it("renders sections and rows", () => {
    render(
      <PropertyPanel>
        <PropertySection title="Preset">
          <PropertyRow label="Style">
            <button data-testid="row-control">Pick</button>
          </PropertyRow>
        </PropertySection>
      </PropertyPanel>,
    )
    expect(screen.getByTestId("property-panel")).toBeInTheDocument()
    expect(screen.getByText("Preset")).toBeInTheDocument()
    expect(screen.getByText("Style")).toBeInTheDocument()
    expect(screen.getByTestId("row-control")).toBeInTheDocument()
  })

  it("collapsible section toggles body via header click", () => {
    render(
      <PropertyPanel>
        <PropertySection title="Sliders">
          <PropertyRow>
            <span data-testid="body-content">Body</span>
          </PropertyRow>
        </PropertySection>
      </PropertyPanel>,
    )
    expect(screen.getByTestId("body-content")).toBeInTheDocument()
    fireEvent.click(screen.getByText("Sliders"))
    expect(screen.queryByTestId("body-content")).not.toBeInTheDocument()
    fireEvent.click(screen.getByText("Sliders"))
    expect(screen.getByTestId("body-content")).toBeInTheDocument()
  })

  it("respects defaultExpanded=false", () => {
    render(
      <PropertyPanel>
        <PropertySection title="Tokens" defaultExpanded={false}>
          <PropertyRow>
            <span data-testid="body-content">Body</span>
          </PropertyRow>
        </PropertySection>
      </PropertyPanel>,
    )
    expect(screen.queryByTestId("body-content")).not.toBeInTheDocument()
  })

  // Sub-arc C-2.2c: className + data-testid passthrough on the outer
  // container so consumers can mount multiple PropertyPanels without
  // testid collision and add scoping classes (e.g. for slide-in
  // positioning on the inherited-core inspector).
  it("passes className through to the outer container", () => {
    render(
      <PropertyPanel className="custom-scope-class">
        <PropertySection title="Section">
          <PropertyRow>
            <span>Body</span>
          </PropertyRow>
        </PropertySection>
      </PropertyPanel>,
    )
    expect(screen.getByTestId("property-panel")).toHaveClass(
      "custom-scope-class",
    )
  })

  it("passes data-testid override through to the outer container", () => {
    render(
      <PropertyPanel data-testid="inherited-core-inspector">
        <PropertySection title="Section">
          <PropertyRow>
            <span>Body</span>
          </PropertyRow>
        </PropertySection>
      </PropertyPanel>,
    )
    expect(
      screen.getByTestId("inherited-core-inspector"),
    ).toBeInTheDocument()
    // Default id should NOT be present when an override is supplied.
    expect(screen.queryByTestId("property-panel")).not.toBeInTheDocument()
  })

  it("defaults data-testid to property-panel when no override supplied", () => {
    render(
      <PropertyPanel>
        <PropertySection title="Section">
          <PropertyRow>
            <span>Body</span>
          </PropertyRow>
        </PropertySection>
      </PropertyPanel>,
    )
    expect(screen.getByTestId("property-panel")).toBeInTheDocument()
  })

  // ─── Sub-arc C-2.3: per-row inheritance + reset ↺ ──────────────

  it("renders a neutral row when no inheritanceSource is provided", () => {
    render(
      <PropertyRow label="Preset">
        <button>Pick</button>
      </PropertyRow>,
    )
    const value = screen.getByTestId("property-row-value")
    expect(value.getAttribute("data-dimmed")).toBeNull()
    expect(
      screen.queryByTestId("property-row-inheritance-caption"),
    ).toBeNull()
    expect(screen.queryByTestId("property-row-reset")).toBeNull()
  })

  it("dims the value + renders inheritance caption when inherited", () => {
    render(
      <PropertyRow
        label="Elevation"
        inheritanceSource={{ tier: "Tier 1 core" }}
      >
        <button>50</button>
      </PropertyRow>,
    )
    const value = screen.getByTestId("property-row-value")
    expect(value.getAttribute("data-dimmed")).toBe("true")
    const caption = screen.getByTestId("property-row-inheritance-caption")
    expect(caption.textContent).toMatch(/inherited from Tier 1 core/)
    // Inherited rows never carry the reset affordance.
    expect(screen.queryByTestId("property-row-reset")).toBeNull()
  })

  it("renders full-opacity value when inheritanceSource is explicit", () => {
    render(
      <PropertyRow
        label="Preset"
        inheritanceSource="explicit"
        onReset={() => {}}
      >
        <button>card</button>
      </PropertyRow>,
    )
    const value = screen.getByTestId("property-row-value")
    expect(value.getAttribute("data-dimmed")).toBeNull()
    expect(
      screen.queryByTestId("property-row-inheritance-caption"),
    ).toBeNull()
  })

  it("renders the reset ↺ affordance only for explicit rows that wire onReset", () => {
    const onReset = vi.fn()
    render(
      <PropertyRow
        label="Preset"
        inheritanceSource="explicit"
        onReset={onReset}
      >
        <button>card</button>
      </PropertyRow>,
    )
    const btn = screen.getByTestId("property-row-reset")
    expect(btn).toBeInTheDocument()
    fireEvent.click(btn)
    expect(onReset).toHaveBeenCalledTimes(1)
  })

  it("hides the reset button when explicit row has no onReset handler", () => {
    render(
      <PropertyRow label="Preset" inheritanceSource="explicit">
        <button>card</button>
      </PropertyRow>,
    )
    expect(screen.queryByTestId("property-row-reset")).toBeNull()
  })
})

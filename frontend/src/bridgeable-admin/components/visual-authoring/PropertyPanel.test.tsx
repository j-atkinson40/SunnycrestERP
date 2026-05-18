/**
 * PropertyPanel unit tests — sub-arc C-1.
 */
import { describe, it, expect } from "vitest"
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
})

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
})

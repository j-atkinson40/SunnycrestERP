/**
 * StudioRailContext smoke tests — Studio 1a-i.B.
 *
 * Verifies the context default value (when consumed outside a provider)
 * and the hook's behavior when wrapped in a provider. Editor-specific
 * adaptation tests live next to each editor file.
 */
import { describe, expect, it } from "vitest"
import { render, screen } from "@testing-library/react"

import {
  StudioRailContext,
  useStudioRail,
} from "./StudioRailContext"


function Probe() {
  const { railExpanded, inStudioContext } = useStudioRail()
  return (
    <div
      data-testid="probe"
      data-rail-expanded={railExpanded ? "true" : "false"}
      data-in-studio-context={inStudioContext ? "true" : "false"}
    />
  )
}


describe("StudioRailContext — default value", () => {
  it("returns railExpanded=false outside provider", () => {
    render(<Probe />)
    const el = screen.getByTestId("probe")
    expect(el.getAttribute("data-rail-expanded")).toBe("false")
  })

  it("returns inStudioContext=false outside provider", () => {
    render(<Probe />)
    const el = screen.getByTestId("probe")
    expect(el.getAttribute("data-in-studio-context")).toBe("false")
  })
})


describe("StudioRailContext — provider value", () => {
  it("propagates railExpanded=true through provider", () => {
    render(
      <StudioRailContext.Provider
        value={{ railExpanded: true, inStudioContext: true }}
      >
        <Probe />
      </StudioRailContext.Provider>,
    )
    const el = screen.getByTestId("probe")
    expect(el.getAttribute("data-rail-expanded")).toBe("true")
    expect(el.getAttribute("data-in-studio-context")).toBe("true")
  })

  it("propagates railExpanded=false even when inStudioContext=true", () => {
    render(
      <StudioRailContext.Provider
        value={{ railExpanded: false, inStudioContext: true }}
      >
        <Probe />
      </StudioRailContext.Provider>,
    )
    const el = screen.getByTestId("probe")
    expect(el.getAttribute("data-rail-expanded")).toBe("false")
    expect(el.getAttribute("data-in-studio-context")).toBe("true")
  })

  it("supports inStudioContext=false (e.g. legacy /visual-editor mount)", () => {
    render(
      <StudioRailContext.Provider
        value={{ railExpanded: true, inStudioContext: false }}
      >
        <Probe />
      </StudioRailContext.Provider>,
    )
    const el = screen.getByTestId("probe")
    // With inStudioContext=false, the editor's `hideLeftPane`
    // guard short-circuits even if railExpanded=true — exercised
    // in per-editor adaptation tests.
    expect(el.getAttribute("data-rail-expanded")).toBe("true")
    expect(el.getAttribute("data-in-studio-context")).toBe("false")
  })
})

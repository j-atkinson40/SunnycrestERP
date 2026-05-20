/**
 * MarqueeOverlay unit tests (sub-arc FF-7).
 */
import { describe, expect, it } from "vitest"
import { render, screen } from "@testing-library/react"

import { MarqueeOverlay } from "./MarqueeOverlay"

describe("MarqueeOverlay", () => {
  it("renders nothing when isActive false", () => {
    const { container } = render(
      <MarqueeOverlay
        isActive={false}
        startPoint={{ x: 0, y: 0 }}
        currentPoint={{ x: 100, y: 100 }}
      />,
    )
    expect(container.querySelector("[data-testid='marquee-overlay']")).toBeNull()
  })

  it("renders nothing when start point null", () => {
    const { container } = render(
      <MarqueeOverlay
        isActive={true}
        startPoint={null}
        currentPoint={{ x: 100, y: 100 }}
      />,
    )
    expect(container.querySelector("[data-testid='marquee-overlay']")).toBeNull()
  })

  it("renders nothing when below 3×3 threshold", () => {
    const { container } = render(
      <MarqueeOverlay
        isActive={true}
        startPoint={{ x: 50, y: 50 }}
        currentPoint={{ x: 51, y: 51 }}
      />,
    )
    expect(container.querySelector("[data-testid='marquee-overlay']")).toBeNull()
  })

  it("renders rectangle with correct bounds", () => {
    render(
      <MarqueeOverlay
        isActive={true}
        startPoint={{ x: 50, y: 50 }}
        currentPoint={{ x: 250, y: 200 }}
      />,
    )
    const el = screen.getByTestId("marquee-overlay")
    const style = el.getAttribute("style") ?? ""
    expect(style).toMatch(/left:\s*50px/i)
    expect(style).toMatch(/top:\s*50px/i)
    expect(style).toMatch(/width:\s*200px/i)
    expect(style).toMatch(/height:\s*150px/i)
    expect(style).toMatch(/pointer-events:\s*none/i)
  })

  it("handles inverted drag (drag from bottom-right to top-left)", () => {
    render(
      <MarqueeOverlay
        isActive={true}
        startPoint={{ x: 300, y: 300 }}
        currentPoint={{ x: 100, y: 50 }}
      />,
    )
    const el = screen.getByTestId("marquee-overlay")
    const style = el.getAttribute("style") ?? ""
    expect(style).toMatch(/left:\s*100px/i)
    expect(style).toMatch(/top:\s*50px/i)
    expect(style).toMatch(/width:\s*200px/i)
    expect(style).toMatch(/height:\s*250px/i)
  })
})

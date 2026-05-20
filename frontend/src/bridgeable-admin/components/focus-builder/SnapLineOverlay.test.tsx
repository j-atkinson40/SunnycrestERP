/**
 * SnapLineOverlay unit tests (sub-arc FF-7).
 */
import { describe, expect, it } from "vitest"
import { render, screen } from "@testing-library/react"

import { SnapLineOverlay } from "./SnapLineOverlay"

const CANVAS = { width: 1200, height: 800 }

describe("SnapLineOverlay", () => {
  it("renders nothing when snapLines empty", () => {
    const { container } = render(
      <SnapLineOverlay snapLines={[]} canvasDimensions={CANVAS} />,
    )
    expect(container.querySelectorAll("[data-testid='snap-line']")).toHaveLength(0)
  })

  it("renders horizontal line at correct y position spanning full width", () => {
    render(
      <SnapLineOverlay
        snapLines={[{ axis: "horizontal", position: 200 }]}
        canvasDimensions={CANVAS}
      />,
    )
    const line = screen.getByTestId("snap-line")
    expect(line.getAttribute("data-axis")).toBe("horizontal")
    expect(line.getAttribute("data-position")).toBe("200")
    const styleAttr = line.getAttribute("style") ?? ""
    expect(styleAttr).toMatch(/top:\s*200px/i)
    expect(styleAttr).toMatch(/width:\s*1200px/i)
    expect(styleAttr).toMatch(/height:\s*1px/i)
  })

  it("renders vertical line at correct x position spanning full height", () => {
    render(
      <SnapLineOverlay
        snapLines={[{ axis: "vertical", position: 600 }]}
        canvasDimensions={CANVAS}
      />,
    )
    const line = screen.getByTestId("snap-line")
    expect(line.getAttribute("data-axis")).toBe("vertical")
    expect(line.getAttribute("data-position")).toBe("600")
    const styleAttr = line.getAttribute("style") ?? ""
    expect(styleAttr).toMatch(/left:\s*600px/i)
    expect(styleAttr).toMatch(/width:\s*1px/i)
    expect(styleAttr).toMatch(/height:\s*800px/i)
  })

  it("renders multiple lines when snapLines has multiple entries", () => {
    render(
      <SnapLineOverlay
        snapLines={[
          { axis: "horizontal", position: 100 },
          { axis: "vertical", position: 200 },
          { axis: "horizontal", position: 400 },
        ]}
        canvasDimensions={CANVAS}
      />,
    )
    expect(screen.getAllByTestId("snap-line")).toHaveLength(3)
  })

  it("pointer-events: none on each line", () => {
    render(
      <SnapLineOverlay
        snapLines={[
          { axis: "horizontal", position: 100 },
          { axis: "vertical", position: 200 },
        ]}
        canvasDimensions={CANVAS}
      />,
    )
    const lines = screen.getAllByTestId("snap-line")
    for (const l of lines) {
      const styleAttr = l.getAttribute("style") ?? ""
      expect(styleAttr).toMatch(/pointer-events:\s*none/i)
    }
  })
})

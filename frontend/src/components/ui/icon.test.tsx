/**
 * Icon — Builder Craft Arc Phase 1a primitive tests.
 * The §7 stroke rule as a DEFAULT: ≤16px → 1.5 stroke, >16px → 2;
 * explicit strokeWidth wins; decorative-by-default a11y.
 */
import { describe, it, expect } from "vitest"
import { render } from "@testing-library/react"
import { Save } from "lucide-react"

import { Icon } from "./icon"

function svgOf(container: HTMLElement): SVGElement {
  const svg = container.querySelector("svg")
  if (!svg) throw new Error("no svg rendered")
  return svg
}

describe("Icon", () => {
  it("defaults to 1.5px stroke at small sizes (≤16)", () => {
    const { container } = render(<Icon icon={Save} size={14} />)
    expect(svgOf(container).getAttribute("stroke-width")).toBe("1.5")
  })

  it("defaults to 1.5px stroke at exactly 16", () => {
    const { container } = render(<Icon icon={Save} size={16} />)
    expect(svgOf(container).getAttribute("stroke-width")).toBe("1.5")
  })

  it("defaults to 2px stroke above 16", () => {
    const { container } = render(<Icon icon={Save} size={20} />)
    expect(svgOf(container).getAttribute("stroke-width")).toBe("2")
  })

  it("explicit strokeWidth wins over the size rule", () => {
    const { container } = render(<Icon icon={Save} size={14} strokeWidth={2} />)
    expect(svgOf(container).getAttribute("stroke-width")).toBe("2")
  })

  it("renders at the requested size and is decorative by default", () => {
    const { container } = render(<Icon icon={Save} size={14} />)
    const svg = svgOf(container)
    expect(svg.getAttribute("width")).toBe("14")
    expect(svg.getAttribute("height")).toBe("14")
    expect(svg.getAttribute("aria-hidden")).toBe("true")
  })

  it("aria-label flips decorative off", () => {
    const { container } = render(<Icon icon={Save} aria-label="Save" />)
    const svg = svgOf(container)
    expect(svg.getAttribute("aria-label")).toBe("Save")
    expect(svg.getAttribute("aria-hidden")).toBeNull()
  })
})

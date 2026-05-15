/**
 * TypographyPresetPicker unit tests — sub-arc C-2.2b.
 */
import { describe, it, expect, vi } from "vitest"
import { fireEvent, render, screen } from "@testing-library/react"

import { TypographyPresetPicker } from "./TypographyPresetPicker"

describe("TypographyPresetPicker", () => {
  it("renders 4 preset pills (card-text/frosted-text/headline/custom)", () => {
    render(<TypographyPresetPicker value={null} onChange={vi.fn()} />)
    const slugs = ["card-text", "frosted-text", "headline", "custom"]
    for (const slug of slugs) {
      expect(screen.getByTestId(`typography-pill-${slug}`)).toBeInTheDocument()
    }
  })

  it("marks the active preset distinctly", () => {
    render(<TypographyPresetPicker value="frosted-text" onChange={vi.fn()} />)
    const active = screen.getByTestId("typography-pill-frosted-text")
    expect(active).toHaveAttribute("data-active", "true")
    expect(active).toHaveAttribute("aria-pressed", "true")
    const inactive = screen.getByTestId("typography-pill-card-text")
    expect(inactive).not.toHaveAttribute("data-active")
    expect(inactive).toHaveAttribute("aria-pressed", "false")
  })

  it("click changes selection and emits the slug", () => {
    const onChange = vi.fn()
    render(<TypographyPresetPicker value={null} onChange={onChange} />)
    fireEvent.click(screen.getByTestId("typography-pill-headline"))
    expect(onChange).toHaveBeenCalledWith("headline")
  })

  it("click on the active pill emits null (toggle off)", () => {
    const onChange = vi.fn()
    render(<TypographyPresetPicker value="headline" onChange={onChange} />)
    fireEvent.click(screen.getByTestId("typography-pill-headline"))
    expect(onChange).toHaveBeenCalledWith(null)
  })
})

/**
 * ChromePresetPicker unit tests — sub-arc C-1.
 */
import { describe, it, expect, vi } from "vitest"
import { fireEvent, render, screen } from "@testing-library/react"

import { ChromePresetPicker } from "./ChromePresetPicker"

describe("ChromePresetPicker", () => {
  it("renders 7 preset pills (card/modal/dropdown/toast/floating/frosted/custom)", () => {
    render(<ChromePresetPicker value={null} onChange={vi.fn()} />)
    const slugs = [
      "card",
      "modal",
      "dropdown",
      "toast",
      "floating",
      "frosted",
      "custom",
    ]
    for (const slug of slugs) {
      expect(screen.getByTestId(`preset-pill-${slug}`)).toBeInTheDocument()
    }
  })

  it("marks the active preset distinctly", () => {
    render(<ChromePresetPicker value="frosted" onChange={vi.fn()} />)
    const active = screen.getByTestId("preset-pill-frosted")
    expect(active).toHaveAttribute("data-active", "true")
    expect(active).toHaveAttribute("aria-pressed", "true")
    const inactive = screen.getByTestId("preset-pill-card")
    expect(inactive).not.toHaveAttribute("data-active")
    expect(inactive).toHaveAttribute("aria-pressed", "false")
  })

  it("click changes selection and emits the slug", () => {
    const onChange = vi.fn()
    render(<ChromePresetPicker value={null} onChange={onChange} />)
    fireEvent.click(screen.getByTestId("preset-pill-modal"))
    expect(onChange).toHaveBeenCalledWith("modal")
  })
})

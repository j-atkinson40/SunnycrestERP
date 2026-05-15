/**
 * SubstratePresetPicker unit tests — sub-arc C-2.2b.
 */
import { describe, it, expect, vi } from "vitest"
import { fireEvent, render, screen } from "@testing-library/react"

import { SubstratePresetPicker } from "./SubstratePresetPicker"

describe("SubstratePresetPicker", () => {
  it("renders 5 preset pills (morning-warm/morning-cool/evening-lounge/neutral/custom)", () => {
    render(<SubstratePresetPicker value={null} onChange={vi.fn()} />)
    const slugs = [
      "morning-warm",
      "morning-cool",
      "evening-lounge",
      "neutral",
      "custom",
    ]
    for (const slug of slugs) {
      expect(screen.getByTestId(`substrate-pill-${slug}`)).toBeInTheDocument()
    }
  })

  it("marks the active preset distinctly", () => {
    render(<SubstratePresetPicker value="morning-warm" onChange={vi.fn()} />)
    const active = screen.getByTestId("substrate-pill-morning-warm")
    expect(active).toHaveAttribute("data-active", "true")
    expect(active).toHaveAttribute("aria-pressed", "true")
    const inactive = screen.getByTestId("substrate-pill-neutral")
    expect(inactive).not.toHaveAttribute("data-active")
    expect(inactive).toHaveAttribute("aria-pressed", "false")
  })

  it("click changes selection and emits the slug", () => {
    const onChange = vi.fn()
    render(<SubstratePresetPicker value={null} onChange={onChange} />)
    fireEvent.click(screen.getByTestId("substrate-pill-evening-lounge"))
    expect(onChange).toHaveBeenCalledWith("evening-lounge")
  })

  it("click on the active pill emits null (toggle off)", () => {
    const onChange = vi.fn()
    render(
      <SubstratePresetPicker value="morning-warm" onChange={onChange} />,
    )
    fireEvent.click(screen.getByTestId("substrate-pill-morning-warm"))
    expect(onChange).toHaveBeenCalledWith(null)
  })
})

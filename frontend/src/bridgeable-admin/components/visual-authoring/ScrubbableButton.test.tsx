/**
 * ScrubbableButton unit tests — sub-arc C-1.
 *
 * Verifies idle render, pointer-driven scrub, modifier-keyed
 * fine-grain, clamp to bounds, keyboard a11y, and disabled gating.
 */
import { describe, it, expect, vi } from "vitest"
import { fireEvent, render, screen } from "@testing-library/react"

import { ScrubbableButton } from "./ScrubbableButton"

function makeProps(over: Partial<React.ComponentProps<typeof ScrubbableButton>> = {}) {
  return {
    value: 50,
    min: 0,
    max: 100,
    label: "Elevation",
    unit: "",
    onChange: vi.fn(),
    ...over,
  }
}

describe("ScrubbableButton", () => {
  it("renders label and value in idle state", () => {
    render(<ScrubbableButton {...makeProps({ value: 42, label: "Corner" })} />)
    const btn = screen.getByTestId("scrubbable-button")
    expect(btn).toBeInTheDocument()
    expect(btn).toHaveAttribute("aria-valuenow", "42")
    expect(btn).toHaveTextContent("Corner")
    expect(btn).toHaveTextContent("42")
  })

  it("scrubs value on pointerdown + pointermove", () => {
    const onChange = vi.fn()
    render(
      <ScrubbableButton
        {...makeProps({ value: 50, onChange, scrubMultiplier: 3 })}
      />,
    )
    const btn = screen.getByTestId("scrubbable-button")

    // Mock setPointerCapture / releasePointerCapture (jsdom).
    ;(btn as unknown as HTMLElement & {
      setPointerCapture: () => void
      releasePointerCapture: () => void
    }).setPointerCapture = vi.fn()
    ;(btn as unknown as HTMLElement & {
      releasePointerCapture: () => void
    }).releasePointerCapture = vi.fn()

    fireEvent.pointerDown(btn, { clientX: 100, button: 0, pointerId: 1 })
    fireEvent.pointerMove(btn, { clientX: 130, pointerId: 1 })
    // 30px / 3 = 10 units → 50 + 10 = 60
    expect(onChange).toHaveBeenCalledWith(60)
  })

  it("scrubs slower under Shift modifier", () => {
    const onChange = vi.fn()
    render(
      <ScrubbableButton
        {...makeProps({ value: 50, onChange, scrubMultiplier: 3 })}
      />,
    )
    const btn = screen.getByTestId("scrubbable-button")
    ;(btn as unknown as { setPointerCapture: () => void }).setPointerCapture =
      vi.fn()
    ;(btn as unknown as { releasePointerCapture: () => void }).releasePointerCapture =
      vi.fn()

    fireEvent.pointerDown(btn, { clientX: 100, button: 0, pointerId: 1 })
    // With Shift held the scrubMultiplier is 4× (12 px per unit). 30px
    // / 12 = 2.5 units → snapped to 2 (step=1) → 50 + 2 = 52. The
    // un-shifted comparison call would have emitted 60.
    fireEvent.pointerMove(btn, { clientX: 130, shiftKey: true, pointerId: 1 })
    expect(onChange).toHaveBeenCalled()
    const lastCall = onChange.mock.calls.at(-1)![0] as number
    // With finer Shift modifier, magnitude well under un-shifted 10.
    expect(Math.abs(lastCall - 50)).toBeLessThan(10)
    expect(Math.abs(lastCall - 50)).toBeGreaterThan(0)
  })

  it("releases on pointerup and stops emitting", () => {
    const onChange = vi.fn()
    render(<ScrubbableButton {...makeProps({ value: 50, onChange })} />)
    const btn = screen.getByTestId("scrubbable-button")
    ;(btn as unknown as { setPointerCapture: () => void }).setPointerCapture =
      vi.fn()
    ;(btn as unknown as { releasePointerCapture: () => void }).releasePointerCapture =
      vi.fn()

    fireEvent.pointerDown(btn, { clientX: 100, button: 0, pointerId: 1 })
    fireEvent.pointerMove(btn, { clientX: 130, pointerId: 1 })
    onChange.mockClear()
    fireEvent.pointerUp(btn, { clientX: 130, pointerId: 1 })
    // Subsequent pointermove (no capture) should not emit.
    fireEvent.pointerMove(btn, { clientX: 200, pointerId: 1 })
    expect(onChange).not.toHaveBeenCalled()
  })

  it("clamps to min and max bounds", () => {
    const onChange = vi.fn()
    render(<ScrubbableButton {...makeProps({ value: 95, onChange })} />)
    const btn = screen.getByTestId("scrubbable-button")
    ;(btn as unknown as { setPointerCapture: () => void }).setPointerCapture =
      vi.fn()
    ;(btn as unknown as { releasePointerCapture: () => void }).releasePointerCapture =
      vi.fn()

    fireEvent.pointerDown(btn, { clientX: 100, button: 0, pointerId: 1 })
    fireEvent.pointerMove(btn, { clientX: 1000, pointerId: 1 })
    expect(onChange).toHaveBeenLastCalledWith(100)

    onChange.mockClear()
    fireEvent.pointerMove(btn, { clientX: -1000, pointerId: 1 })
    expect(onChange).toHaveBeenLastCalledWith(0)
  })

  it("arrow keys adjust value by step", () => {
    const onChange = vi.fn()
    render(<ScrubbableButton {...makeProps({ value: 50, onChange, step: 1 })} />)
    const btn = screen.getByTestId("scrubbable-button")
    fireEvent.keyDown(btn, { key: "ArrowRight" })
    expect(onChange).toHaveBeenLastCalledWith(51)
    fireEvent.keyDown(btn, { key: "ArrowLeft" })
    expect(onChange).toHaveBeenLastCalledWith(49)
  })

  it("disabled prevents scrub and keyboard interaction", () => {
    const onChange = vi.fn()
    render(<ScrubbableButton {...makeProps({ value: 50, onChange, disabled: true })} />)
    const btn = screen.getByTestId("scrubbable-button")
    ;(btn as unknown as { setPointerCapture: () => void }).setPointerCapture =
      vi.fn()

    fireEvent.pointerDown(btn, { clientX: 100, button: 0, pointerId: 1 })
    fireEvent.pointerMove(btn, { clientX: 200, pointerId: 1 })
    fireEvent.keyDown(btn, { key: "ArrowRight" })
    expect(onChange).not.toHaveBeenCalled()
    expect(btn).toBeDisabled()
  })
})

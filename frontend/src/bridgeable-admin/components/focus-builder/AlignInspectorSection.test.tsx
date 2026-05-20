/**
 * AlignInspectorSection unit tests (sub-arc FF-7).
 */
import { describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen } from "@testing-library/react"

import { AlignInspectorSection } from "./AlignInspectorSection"
import type { AlignAction } from "./computeAlignTargets"

const TWO_PLACEMENTS = [
  { id: "a", x: 100, y: 100, width: 200, height: 100 },
  { id: "b", x: 500, y: 250, width: 100, height: 150 },
]

describe("AlignInspectorSection", () => {
  it("renders 6 buttons", () => {
    render(
      <AlignInspectorSection
        selectedPlacements={TWO_PLACEMENTS}
        onAlign={() => {}}
      />,
    )
    const section = screen.getByTestId("align-inspector-section")
    const buttons = section.querySelectorAll("button")
    expect(buttons.length).toBe(6)
  })

  it("each button fires onAlign with correct action", () => {
    const onAlign = vi.fn()
    render(
      <AlignInspectorSection
        selectedPlacements={TWO_PLACEMENTS}
        onAlign={onAlign}
      />,
    )
    const actions: AlignAction[] = [
      "left",
      "center-horizontal",
      "right",
      "top",
      "center-vertical",
      "bottom",
    ]
    for (const a of actions) {
      fireEvent.click(screen.getByTestId(`align-action-${a}`))
    }
    expect(onAlign).toHaveBeenCalledTimes(6)
    for (const a of actions) {
      expect(onAlign).toHaveBeenCalledWith(a)
    }
  })

  it("disabled when fewer than 2 placements", () => {
    const onAlign = vi.fn()
    render(
      <AlignInspectorSection
        selectedPlacements={[TWO_PLACEMENTS[0]]}
        onAlign={onAlign}
      />,
    )
    const btn = screen.getByTestId("align-action-left") as HTMLButtonElement
    expect(btn.disabled).toBe(true)
    fireEvent.click(btn)
    // onClick fired on disabled button is a no-op for React buttons,
    // but assert defensively that onAlign didn't fire either.
    expect(onAlign).not.toHaveBeenCalled()
  })

  it("displays count of selected widgets", () => {
    render(
      <AlignInspectorSection
        selectedPlacements={[
          ...TWO_PLACEMENTS,
          { id: "c", x: 50, y: 50, width: 80, height: 80 },
        ]}
        onAlign={() => {}}
      />,
    )
    expect(screen.getByText(/3 widgets selected/i)).toBeInTheDocument()
  })
})

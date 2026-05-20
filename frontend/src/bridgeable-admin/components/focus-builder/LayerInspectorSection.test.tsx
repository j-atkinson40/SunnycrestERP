/**
 * LayerInspectorSection tests — sub-arc FF-5.
 *
 * Asserts the four-button surface renders + fires the correct action.
 * Disabled-state coverage for both null-placement and isCore branches.
 */
import { describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen } from "@testing-library/react"

import { LayerInspectorSection } from "./LayerInspectorSection"

describe("LayerInspectorSection", () => {
  it("renders all four buttons with correct labels", () => {
    render(<LayerInspectorSection placementId="w-1" onAction={() => {}} />)
    const front = screen.getByTestId("layer-action-front")
    const forward = screen.getByTestId("layer-action-forward")
    const backward = screen.getByTestId("layer-action-backward")
    const back = screen.getByTestId("layer-action-back")
    expect(front.textContent).toContain("Bring to front")
    expect(forward.textContent).toContain("Bring forward")
    expect(backward.textContent).toContain("Send backward")
    expect(back.textContent).toContain("Send to back")
  })

  it("each button fires onAction with the correct action when clicked", () => {
    const onAction = vi.fn()
    render(<LayerInspectorSection placementId="w-1" onAction={onAction} />)
    fireEvent.click(screen.getByTestId("layer-action-front"))
    fireEvent.click(screen.getByTestId("layer-action-forward"))
    fireEvent.click(screen.getByTestId("layer-action-backward"))
    fireEvent.click(screen.getByTestId("layer-action-back"))
    expect(onAction).toHaveBeenNthCalledWith(1, "front")
    expect(onAction).toHaveBeenNthCalledWith(2, "forward")
    expect(onAction).toHaveBeenNthCalledWith(3, "backward")
    expect(onAction).toHaveBeenNthCalledWith(4, "back")
  })

  it("buttons disabled when placementId is null", () => {
    const onAction = vi.fn()
    render(<LayerInspectorSection placementId={null} onAction={onAction} />)
    const front = screen.getByTestId("layer-action-front") as HTMLButtonElement
    expect(front.disabled).toBe(true)
    fireEvent.click(front)
    expect(onAction).not.toHaveBeenCalled()
  })

  it("buttons disabled when isCore is true", () => {
    const onAction = vi.fn()
    render(
      <LayerInspectorSection
        placementId="core-1"
        onAction={onAction}
        isCore
      />,
    )
    const front = screen.getByTestId("layer-action-front") as HTMLButtonElement
    const back = screen.getByTestId("layer-action-back") as HTMLButtonElement
    expect(front.disabled).toBe(true)
    expect(back.disabled).toBe(true)
    fireEvent.click(front)
    fireEvent.click(back)
    expect(onAction).not.toHaveBeenCalled()
  })
})

/**
 * PositionInspectorSection tests — sub-arc FF-6.
 *
 * Coverage:
 *   - 4-input render with correct labels (X / Y / Width / Height)
 *   - Each input reflects current placement value
 *   - onChange updates local state without onUpdate firing
 *   - onBlur commits clamped value via onUpdate
 *   - Enter triggers blur → commit
 *   - Invalid input reverts to placement on blur
 *   - Disabled when placement null
 *   - Disabled when isCore
 *   - X clamps to canvas - widget_width
 *   - Width clamps to min
 *   - Negative X clamps to 0
 *   - Focus preservation: placementValue change while focused does NOT
 *     overwrite localValue (load-bearing UX correctness)
 *   - Sync: when NOT focused, placementValue change updates display
 */
import { describe, expect, it, vi } from "vitest"
import { act, fireEvent, render, screen } from "@testing-library/react"

import { PositionInspectorSection } from "./PositionInspectorSection"
import type { WidgetPlacement } from "@/bridgeable-admin/hooks/useFocusTemplateDraft"

function makePlacement(
  overrides: Partial<WidgetPlacement> = {},
): WidgetPlacement {
  return {
    id: "w-1",
    widget_slug: "today-pin-widget",
    x: 100,
    y: 100,
    width: 200,
    height: 100,
    chrome: {},
    ...overrides,
  }
}

const canvas = { width: 1200, height: 800 }
const min = { width: 80, height: 40 }

describe("PositionInspectorSection", () => {
  it("renders all four inputs with correct labels", () => {
    render(
      <PositionInspectorSection
        placement={makePlacement()}
        canvasDimensions={canvas}
        minDimensions={min}
        onUpdate={() => {}}
      />,
    )
    expect(screen.getByTestId("position-inspector-section")).toBeInTheDocument()
    expect(screen.getByTestId("position-input-x")).toBeInTheDocument()
    expect(screen.getByTestId("position-input-y")).toBeInTheDocument()
    expect(screen.getByTestId("position-input-width")).toBeInTheDocument()
    expect(screen.getByTestId("position-input-height")).toBeInTheDocument()
  })

  it("each input reflects current placement value", () => {
    render(
      <PositionInspectorSection
        placement={makePlacement({ x: 50, y: 75, width: 240, height: 120 })}
        canvasDimensions={canvas}
        minDimensions={min}
        onUpdate={() => {}}
      />,
    )
    expect((screen.getByTestId("position-input-x") as HTMLInputElement).value).toBe(
      "50",
    )
    expect((screen.getByTestId("position-input-y") as HTMLInputElement).value).toBe(
      "75",
    )
    expect(
      (screen.getByTestId("position-input-width") as HTMLInputElement).value,
    ).toBe("240")
    expect(
      (screen.getByTestId("position-input-height") as HTMLInputElement).value,
    ).toBe("120")
  })

  it("onChange updates local state without calling onUpdate", () => {
    const onUpdate = vi.fn()
    render(
      <PositionInspectorSection
        placement={makePlacement()}
        canvasDimensions={canvas}
        minDimensions={min}
        onUpdate={onUpdate}
      />,
    )
    const x = screen.getByTestId("position-input-x") as HTMLInputElement
    fireEvent.change(x, { target: { value: "150" } })
    expect(x.value).toBe("150")
    expect(onUpdate).not.toHaveBeenCalled()
  })

  it("onBlur commits clamped value via onUpdate", () => {
    const onUpdate = vi.fn()
    render(
      <PositionInspectorSection
        placement={makePlacement({ x: 100, width: 200 })}
        canvasDimensions={canvas}
        minDimensions={min}
        onUpdate={onUpdate}
      />,
    )
    const x = screen.getByTestId("position-input-x") as HTMLInputElement
    fireEvent.change(x, { target: { value: "250" } })
    fireEvent.blur(x)
    expect(onUpdate).toHaveBeenCalledWith("x", 250)
  })

  it("Enter keypress triggers blur which commits", () => {
    const onUpdate = vi.fn()
    render(
      <PositionInspectorSection
        placement={makePlacement()}
        canvasDimensions={canvas}
        minDimensions={min}
        onUpdate={onUpdate}
      />,
    )
    const y = screen.getByTestId("position-input-y") as HTMLInputElement
    y.focus()
    fireEvent.change(y, { target: { value: "175" } })
    fireEvent.keyDown(y, { key: "Enter" })
    expect(onUpdate).toHaveBeenCalledWith("y", 175)
  })

  it("invalid input (non-numeric) reverts to placement value on blur without calling onUpdate", () => {
    const onUpdate = vi.fn()
    render(
      <PositionInspectorSection
        placement={makePlacement({ x: 100 })}
        canvasDimensions={canvas}
        minDimensions={min}
        onUpdate={onUpdate}
      />,
    )
    const x = screen.getByTestId("position-input-x") as HTMLInputElement
    fireEvent.change(x, { target: { value: "abc" } })
    fireEvent.blur(x)
    expect(onUpdate).not.toHaveBeenCalled()
    expect(x.value).toBe("100")
  })

  it("inputs disabled when placement is null", () => {
    render(
      <PositionInspectorSection
        placement={null}
        canvasDimensions={canvas}
        minDimensions={min}
        onUpdate={() => {}}
      />,
    )
    const x = screen.getByTestId("position-input-x") as HTMLInputElement
    const w = screen.getByTestId("position-input-width") as HTMLInputElement
    expect(x.disabled).toBe(true)
    expect(w.disabled).toBe(true)
  })

  it("inputs disabled when isCore is true", () => {
    render(
      <PositionInspectorSection
        placement={makePlacement()}
        canvasDimensions={canvas}
        minDimensions={min}
        isCore
        onUpdate={() => {}}
      />,
    )
    const x = screen.getByTestId("position-input-x") as HTMLInputElement
    expect(x.disabled).toBe(true)
  })

  it("clamp: X exceeding canvas bound clamps to canvas_width - widget_width", () => {
    const onUpdate = vi.fn()
    render(
      <PositionInspectorSection
        placement={makePlacement({ x: 100, width: 200 })}
        canvasDimensions={canvas}
        minDimensions={min}
        onUpdate={onUpdate}
      />,
    )
    const x = screen.getByTestId("position-input-x") as HTMLInputElement
    fireEvent.change(x, { target: { value: "1500" } })
    fireEvent.blur(x)
    // canvas.width 1200 - widget.width 200 = 1000
    expect(onUpdate).toHaveBeenCalledWith("x", 1000)
  })

  it("clamp: Width below minDimensions clamps to minDimensions.width", () => {
    const onUpdate = vi.fn()
    render(
      <PositionInspectorSection
        placement={makePlacement({ width: 200 })}
        canvasDimensions={canvas}
        minDimensions={{ width: 120, height: 64 }}
        onUpdate={onUpdate}
      />,
    )
    const w = screen.getByTestId("position-input-width") as HTMLInputElement
    fireEvent.change(w, { target: { value: "50" } })
    fireEvent.blur(w)
    expect(onUpdate).toHaveBeenCalledWith("width", 120)
  })

  it("clamp: negative X clamps to 0", () => {
    const onUpdate = vi.fn()
    render(
      <PositionInspectorSection
        placement={makePlacement({ x: 100 })}
        canvasDimensions={canvas}
        minDimensions={min}
        onUpdate={onUpdate}
      />,
    )
    const x = screen.getByTestId("position-input-x") as HTMLInputElement
    fireEvent.change(x, { target: { value: "-50" } })
    fireEvent.blur(x)
    expect(onUpdate).toHaveBeenCalledWith("x", 0)
  })

  it("focus preservation: placementValue change while focused does NOT overwrite localValue (load-bearing UX)", () => {
    const Wrapper = ({ x }: { x: number }) => (
      <PositionInspectorSection
        placement={makePlacement({ x })}
        canvasDimensions={canvas}
        minDimensions={min}
        onUpdate={() => {}}
      />
    )
    const { rerender } = render(<Wrapper x={100} />)
    const input = screen.getByTestId("position-input-x") as HTMLInputElement

    // Operator focuses and types "200" without blurring.
    input.focus()
    fireEvent.change(input, { target: { value: "200" } })
    expect(input.value).toBe("200")
    expect(document.activeElement).toBe(input)

    // Canvas drag updates the placement's x to 500 while the input
    // still has focus. The input must NOT clobber the operator's
    // mid-edit local string.
    act(() => {
      rerender(<Wrapper x={500} />)
    })

    // Focus preserved.
    expect(document.activeElement).toBe(input)
    // Mid-edit local string preserved (NOT overwritten with "500").
    expect(input.value).toBe("200")
  })

  it("sync: when input is NOT focused, placementValue change updates displayed value", () => {
    const Wrapper = ({ x }: { x: number }) => (
      <PositionInspectorSection
        placement={makePlacement({ x })}
        canvasDimensions={canvas}
        minDimensions={min}
        onUpdate={() => {}}
      />
    )
    const { rerender } = render(<Wrapper x={100} />)
    const input = screen.getByTestId("position-input-x") as HTMLInputElement
    expect(input.value).toBe("100")
    // Input never focused; placement updates should sync through.
    act(() => {
      rerender(<Wrapper x={500} />)
    })
    expect(input.value).toBe("500")
  })
})

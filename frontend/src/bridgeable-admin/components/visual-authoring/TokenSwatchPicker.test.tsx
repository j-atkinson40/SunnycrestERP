/**
 * TokenSwatchPicker unit tests — sub-arc C-1.
 */
import { describe, it, expect, vi } from "vitest"
import { fireEvent, render, screen } from "@testing-library/react"

import { TokenSwatchPicker } from "./TokenSwatchPicker"

const themeTokens = {
  "surface-base": "#fafafa",
  "surface-elevated": "#ffffff",
  "surface-raised": "#fbfaf6",
  "surface-sunken": "#f1efe9",
  "border-subtle": "#e8e3d8",
  "border-base": "#cfc8b8",
  "border-strong": "#a89e88",
  "border-brass": "#9C5640",
}

describe("TokenSwatchPicker", () => {
  it("renders swatch + label + current value", () => {
    const onChange = vi.fn()
    render(
      <TokenSwatchPicker
        value="surface-elevated"
        tokenFamily="surface"
        themeTokens={themeTokens}
        onChange={onChange}
        label="Background"
      />,
    )
    expect(screen.getByText("Background")).toBeInTheDocument()
    expect(screen.getByText("surface-elevated")).toBeInTheDocument()
    expect(screen.getByTestId("token-swatch-trigger")).toHaveAttribute(
      "aria-expanded",
      "false",
    )
  })

  it("opens popover on trigger click and shows family tokens", () => {
    render(
      <TokenSwatchPicker
        value={null}
        tokenFamily="surface"
        themeTokens={themeTokens}
        onChange={vi.fn()}
        label="Background"
      />,
    )
    fireEvent.click(screen.getByTestId("token-swatch-trigger"))
    expect(screen.getByTestId("token-swatch-popover")).toBeInTheDocument()
    // All surface tokens present.
    expect(
      screen.getByTestId("token-swatch-option-surface-elevated"),
    ).toBeInTheDocument()
    expect(
      screen.getByTestId("token-swatch-option-surface-raised"),
    ).toBeInTheDocument()
  })

  it("emits token name and closes on swatch click", () => {
    const onChange = vi.fn()
    render(
      <TokenSwatchPicker
        value={null}
        tokenFamily="surface"
        themeTokens={themeTokens}
        onChange={onChange}
        label="Background"
      />,
    )
    fireEvent.click(screen.getByTestId("token-swatch-trigger"))
    fireEvent.click(screen.getByTestId("token-swatch-option-surface-raised"))
    expect(onChange).toHaveBeenCalledWith("surface-raised")
    expect(screen.queryByTestId("token-swatch-popover")).not.toBeInTheDocument()
  })

  it("closes without emission on outside click", () => {
    const onChange = vi.fn()
    render(
      <div>
        <TokenSwatchPicker
          value="surface-elevated"
          tokenFamily="surface"
          themeTokens={themeTokens}
          onChange={onChange}
          label="Background"
        />
        <button data-testid="outside">Outside</button>
      </div>,
    )
    fireEvent.click(screen.getByTestId("token-swatch-trigger"))
    expect(screen.getByTestId("token-swatch-popover")).toBeInTheDocument()
    fireEvent.mouseDown(screen.getByTestId("outside"))
    expect(screen.queryByTestId("token-swatch-popover")).not.toBeInTheDocument()
    expect(onChange).not.toHaveBeenCalled()
  })

  it("allowNone renders a None option that emits null", () => {
    const onChange = vi.fn()
    render(
      <TokenSwatchPicker
        value="surface-elevated"
        tokenFamily="surface"
        themeTokens={themeTokens}
        onChange={onChange}
        label="Background"
        allowNone
      />,
    )
    fireEvent.click(screen.getByTestId("token-swatch-trigger"))
    fireEvent.click(screen.getByTestId("token-swatch-option-none"))
    expect(onChange).toHaveBeenCalledWith(null)
  })

  it("padding family renders box illustrations rather than color swatches", () => {
    render(
      <TokenSwatchPicker
        value="space-4"
        tokenFamily="padding"
        themeTokens={themeTokens}
        onChange={vi.fn()}
        label="Padding"
        allowNone={false}
      />,
    )
    fireEvent.click(screen.getByTestId("token-swatch-trigger"))
    expect(
      screen.getByTestId("token-swatch-option-space-2"),
    ).toBeInTheDocument()
    expect(
      screen.getByTestId("token-swatch-option-space-8"),
    ).toBeInTheDocument()
    // No "None" option when allowNone=false.
    expect(
      screen.queryByTestId("token-swatch-option-none"),
    ).not.toBeInTheDocument()
  })
})

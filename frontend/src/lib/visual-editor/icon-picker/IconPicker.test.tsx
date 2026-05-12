/**
 * Arc 4a.1 — IconPicker shared component tests.
 *
 * Verifies:
 *   - Subset grid renders with all canonical group sections + cells.
 *   - Cell click emits onChange with the icon name.
 *   - Free-form text input commits on blur + Enter; falls through to
 *     custom-flag indicator when value is outside the subset.
 *   - Clear button resets value to empty string.
 *   - Selected cell carries aria-pressed=true; others false.
 *   - resolveSubsetIcon returns null for unknown names + the lucide
 *     component for canonical names.
 */
import { describe, expect, it, vi } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"

import { IconPicker } from "./IconPicker"
import { ICON_SUBSET, resolveSubsetIcon, ICON_GROUPS } from "./icon-subset"


describe("IconPicker", () => {
  it("renders all groups + cell buttons", () => {
    const handleChange = vi.fn()
    render(<IconPicker value="" onChange={handleChange} />)

    // Every group section present
    for (const group of ICON_GROUPS) {
      expect(
        screen.getByTestId(`icon-picker-group-${group}`),
      ).toBeInTheDocument()
    }

    // Every subset entry has a cell
    for (const entry of ICON_SUBSET) {
      expect(
        screen.getByTestId(`icon-picker-cell-${entry.name}`),
      ).toBeInTheDocument()
    }
  })

  it("cell click emits onChange with icon name", () => {
    const handleChange = vi.fn()
    render(<IconPicker value="" onChange={handleChange} />)

    fireEvent.click(screen.getByTestId("icon-picker-cell-Plus"))
    expect(handleChange).toHaveBeenCalledWith("Plus")
  })

  it("selected cell sets aria-pressed=true", () => {
    const handleChange = vi.fn()
    render(<IconPicker value="Workflow" onChange={handleChange} />)

    const selected = screen.getByTestId("icon-picker-cell-Workflow")
    expect(selected.getAttribute("aria-pressed")).toBe("true")

    const unselected = screen.getByTestId("icon-picker-cell-Plus")
    expect(unselected.getAttribute("aria-pressed")).toBe("false")
  })

  it("text input commits on blur", () => {
    const handleChange = vi.fn()
    render(<IconPicker value="" onChange={handleChange} />)

    const input = screen.getByTestId(
      "icon-picker-text-input",
    ) as HTMLInputElement
    fireEvent.change(input, { target: { value: "CustomIcon" } })
    fireEvent.blur(input)
    expect(handleChange).toHaveBeenCalledWith("CustomIcon")
  })

  it("text input commits on Enter", () => {
    const handleChange = vi.fn()
    render(<IconPicker value="" onChange={handleChange} />)

    const input = screen.getByTestId(
      "icon-picker-text-input",
    ) as HTMLInputElement
    fireEvent.change(input, { target: { value: "TypedName" } })
    fireEvent.keyDown(input, { key: "Enter" })
    expect(handleChange).toHaveBeenCalledWith("TypedName")
  })

  it("flags free-form value not in subset with custom badge", () => {
    const handleChange = vi.fn()
    render(<IconPicker value="NotInSubset" onChange={handleChange} />)
    expect(
      screen.getByTestId("icon-picker-free-form-flag"),
    ).toBeInTheDocument()
  })

  it("does not flag subset value as custom", () => {
    const handleChange = vi.fn()
    render(<IconPicker value="Plus" onChange={handleChange} />)
    expect(
      screen.queryByTestId("icon-picker-free-form-flag"),
    ).not.toBeInTheDocument()
  })

  it("clear button resets value to empty string", () => {
    const handleChange = vi.fn()
    render(<IconPicker value="Workflow" onChange={handleChange} />)

    fireEvent.click(screen.getByTestId("icon-picker-clear"))
    expect(handleChange).toHaveBeenCalledWith("")
  })

  it("disabled prop disables all interactive elements", () => {
    render(<IconPicker value="" onChange={vi.fn()} disabled />)
    const cells = screen.getAllByRole("button")
    for (const cell of cells) {
      expect(cell).toBeDisabled()
    }
  })

  it("resolveSubsetIcon returns null for unknown name", () => {
    expect(resolveSubsetIcon("NotARealIcon")).toBeNull()
    expect(resolveSubsetIcon(undefined)).toBeNull()
    expect(resolveSubsetIcon("")).toBeNull()
  })

  it("resolveSubsetIcon returns lucide component for canonical name", () => {
    const Icon = resolveSubsetIcon("Plus")
    expect(Icon).not.toBeNull()
  })
})

/**
 * FocusBuilderThemePicker tests (sub-arc F-4).
 */
import { describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen } from "@testing-library/react"

import { FocusBuilderThemePicker } from "./FocusBuilderThemePicker"
import type { UseFocusTemplateDraftResult } from "@/bridgeable-admin/hooks/useFocusTemplateDraft"

function makeHook(
  overrides: Partial<UseFocusTemplateDraftResult> = {},
): UseFocusTemplateDraftResult {
  const noop = vi.fn()
  return {
    template: null,
    isLoading: false,
    isSaving: false,
    error: null,
    editSessionId: null,
    chromeOverridesDraft: {},
    substrateDraft: {},
    typographyDraft: {},
    rowsDraft: [],
    updateChromeOverrides: noop,
    updateSubstrate: vi.fn(),
    updateTypography: vi.fn(),
    resetChromeOverridesField: noop,
    resetSubstrateField: noop,
    resetTypographyField: noop,
    addWidget: vi.fn(() => "new-id"),
    removeWidget: noop,
    updateWidget: noop,
    moveWidget: noop,
    isDirty: false,
    lastSavedAt: null,
    save: vi.fn(),
    discard: vi.fn(),
    ...overrides,
  } as unknown as UseFocusTemplateDraftResult
}

describe("FocusBuilderThemePicker", () => {
  it("shows disabled state with hint when mode is core", () => {
    render(<FocusBuilderThemePicker mode="core" templateHook={null} />)
    expect(
      screen.getByTestId("focus-builder-theme-picker-disabled"),
    ).toBeInTheDocument()
    expect(
      screen.getByTestId("focus-builder-theme-picker-disabled-hint"),
    ).toHaveTextContent(/themes apply to templates, not cores/i)
  })

  it("shows disabled state when mode is empty", () => {
    render(<FocusBuilderThemePicker mode="empty" templateHook={null} />)
    expect(
      screen.getByTestId("focus-builder-theme-picker-disabled"),
    ).toBeInTheDocument()
  })

  it("renders substrate + typography preset strips when mode is template", () => {
    render(
      <FocusBuilderThemePicker mode="template" templateHook={makeHook()} />,
    )
    expect(
      screen.getByTestId("focus-builder-theme-picker"),
    ).toBeInTheDocument()
    expect(
      screen.getByTestId("focus-builder-theme-picker-substrate"),
    ).toBeInTheDocument()
    expect(
      screen.getByTestId("focus-builder-theme-picker-typography"),
    ).toBeInTheDocument()
    expect(screen.getByTestId("substrate-preset-picker")).toBeInTheDocument()
    expect(screen.getByTestId("typography-preset-picker")).toBeInTheDocument()
  })

  it("currently-selected substrate chip shows selected state", () => {
    render(
      <FocusBuilderThemePicker
        mode="template"
        templateHook={makeHook({
          substrateDraft: { preset: "morning-warm" } as Record<string, unknown>,
        })}
      />,
    )
    const chip = screen.getByTestId("substrate-pill-morning-warm")
    expect(chip.getAttribute("data-active")).toBe("true")
    expect(chip.getAttribute("aria-pressed")).toBe("true")
  })

  it("currently-selected typography chip shows selected state", () => {
    render(
      <FocusBuilderThemePicker
        mode="template"
        templateHook={makeHook({
          typographyDraft: { preset: "headline" } as Record<string, unknown>,
        })}
      />,
    )
    const chip = screen.getByTestId("typography-pill-headline")
    expect(chip.getAttribute("data-active")).toBe("true")
  })

  it("clicking a substrate chip fires updateSubstrate with preset-only partial", () => {
    const updateSubstrate = vi.fn()
    render(
      <FocusBuilderThemePicker
        mode="template"
        templateHook={makeHook({ updateSubstrate })}
      />,
    )
    fireEvent.click(screen.getByTestId("substrate-pill-evening-lounge"))
    expect(updateSubstrate).toHaveBeenCalledTimes(1)
    expect(updateSubstrate).toHaveBeenCalledWith({ preset: "evening-lounge" })
  })

  it("clicking a typography chip fires updateTypography with preset-only partial", () => {
    const updateTypography = vi.fn()
    render(
      <FocusBuilderThemePicker
        mode="template"
        templateHook={makeHook({ updateTypography })}
      />,
    )
    fireEvent.click(screen.getByTestId("typography-pill-frosted-text"))
    expect(updateTypography).toHaveBeenCalledTimes(1)
    expect(updateTypography).toHaveBeenCalledWith({ preset: "frosted-text" })
  })

  // C-1 SubstratePresetPicker emits null when the active chip is
  // clicked (toggle-to-clear semantics). F-4 preserves that
  // behavior — the theme picker is a thin wrapper, not a
  // re-implementation of the picker semantics. Clicking the
  // currently-selected chip clears the preset.
  it("clicking currently-selected chip clears the preset (toggle-to-clear from C-1)", () => {
    const updateSubstrate = vi.fn()
    render(
      <FocusBuilderThemePicker
        mode="template"
        templateHook={makeHook({
          substrateDraft: { preset: "morning-warm" } as Record<string, unknown>,
          updateSubstrate,
        })}
      />,
    )
    fireEvent.click(screen.getByTestId("substrate-pill-morning-warm"))
    expect(updateSubstrate).toHaveBeenCalledWith({ preset: null })
  })
})

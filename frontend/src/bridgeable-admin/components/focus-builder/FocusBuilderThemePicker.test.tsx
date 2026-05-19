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

  // F-4.1 — chip-click = "apply preset wholesale". Payload nulls out
  // specifics so the resolver's expandXPreset applies preset defaults.
  // (Resolver specifics-win priority is correct for the inspector's
  // fine-grained scrubbing path — the chip is the wholesale override.)
  it("clicking a substrate chip fires updateSubstrate with preset + nulled specifics", () => {
    const updateSubstrate = vi.fn()
    render(
      <FocusBuilderThemePicker
        mode="template"
        templateHook={makeHook({ updateSubstrate })}
      />,
    )
    fireEvent.click(screen.getByTestId("substrate-pill-evening-lounge"))
    expect(updateSubstrate).toHaveBeenCalledTimes(1)
    expect(updateSubstrate).toHaveBeenCalledWith({
      preset: "evening-lounge",
      intensity: null,
      base_token: null,
      accent_token_1: null,
      accent_token_2: null,
    })
  })

  it("clicking a typography chip fires updateTypography with preset + nulled specifics", () => {
    const updateTypography = vi.fn()
    render(
      <FocusBuilderThemePicker
        mode="template"
        templateHook={makeHook({ updateTypography })}
      />,
    )
    fireEvent.click(screen.getByTestId("typography-pill-frosted-text"))
    expect(updateTypography).toHaveBeenCalledTimes(1)
    expect(updateTypography).toHaveBeenCalledWith({
      preset: "frosted-text",
      heading_weight: null,
      body_weight: null,
      heading_color_token: null,
      body_color_token: null,
    })
  })

  // C-1 SubstratePresetPicker emits null when the active chip is
  // clicked (toggle-to-clear semantics). F-4.1 preserves that
  // behavior — clicking the currently-selected chip clears the
  // preset AND nulls specifics (preset null + null specifics =
  // canvas falls back to defaults; canon-correct).
  it("clicking currently-selected chip clears preset AND nulls specifics", () => {
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
    expect(updateSubstrate).toHaveBeenCalledWith({
      preset: null,
      intensity: null,
      base_token: null,
      accent_token_1: null,
      accent_token_2: null,
    })
  })
})

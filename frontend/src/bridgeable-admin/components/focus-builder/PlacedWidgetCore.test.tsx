/**
 * PlacedWidgetCore unit tests (sub-arc FF-2).
 *
 * Validates the shared inner wrapper extracted from F-3.1c's
 * `PlacedWidget` inline implementation per investigation Q-29. The
 * outer `focus-builder-placed-widget` data-testid is preserved on
 * the wrapper div; the inner `focus-builder-placed-widget-core`
 * data-testid is the new operator-observable assertion target per
 * the 2026-05-20 late-evening canon.
 */
import { describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen } from "@testing-library/react"

import "@/lib/visual-editor/registry/auto-register"

import { BASE_TOKENS } from "@/lib/visual-editor/themes/base-tokens"

import { PlacedWidgetCore } from "./PlacedWidgetCore"
import type { WidgetPlacement } from "@/bridgeable-admin/hooks/useFocusTemplateDraft"

const tokens = { ...BASE_TOKENS.light }

const placement: WidgetPlacement = {
  id: "w-core-test-1",
  widget_slug: "day-strip-widget",
  column_start: 1,
  column_span: 12,
  chrome: {},
}

describe("PlacedWidgetCore", () => {
  it("renders the outer focus-builder-placed-widget test-id", () => {
    render(
      <PlacedWidgetCore
        placement={placement}
        selected={false}
        onSelect={() => {}}
        themeTokens={tokens}
        outerStyle={{ gridColumn: "1 / span 12" }}
      />,
    )
    expect(screen.getByTestId("focus-builder-placed-widget")).toBeInTheDocument()
  })

  it("renders the inner focus-builder-placed-widget-core test-id", () => {
    render(
      <PlacedWidgetCore
        placement={placement}
        selected={false}
        onSelect={() => {}}
        themeTokens={tokens}
        outerStyle={{ gridColumn: "1 / span 12" }}
      />,
    )
    expect(
      screen.getByTestId("focus-builder-placed-widget-core"),
    ).toBeInTheDocument()
  })

  it("applies chrome-resolved style on the outer wrapper (F-3.1c preservation)", () => {
    render(
      <PlacedWidgetCore
        placement={placement}
        selected={false}
        onSelect={() => {}}
        themeTokens={tokens}
        outerStyle={{ gridColumn: "1 / span 12" }}
      />,
    )
    const outer = screen.getByTestId("focus-builder-placed-widget")
    const styleAttr = outer.getAttribute("style") ?? ""
    // DEFAULT_WIDGET_CHROME (elevation 50) produces a box-shadow,
    // border-radius, and padding via the chrome-resolver. Pre-FF-2
    // F-3.1c established these as the load-bearing render-side
    // assertions; FF-2 preserves them.
    expect(styleAttr).toMatch(/box-shadow/i)
    expect(styleAttr).toMatch(/border-radius/i)
    expect(styleAttr).toMatch(/padding/i)
  })

  it("applies outer positioning style (e.g. gridColumn)", () => {
    render(
      <PlacedWidgetCore
        placement={placement}
        selected={false}
        onSelect={() => {}}
        themeTokens={tokens}
        outerStyle={{ gridColumn: "3 / span 6" }}
      />,
    )
    const outer = screen.getByTestId("focus-builder-placed-widget")
    const styleAttr = outer.getAttribute("style") ?? ""
    expect(styleAttr).toMatch(/grid-column:\s*3\s*\/\s*span\s*6/i)
  })

  it("shows selection chrome (brass outline) when selected", () => {
    render(
      <PlacedWidgetCore
        placement={placement}
        selected={true}
        onSelect={() => {}}
        themeTokens={tokens}
        outerStyle={{ gridColumn: "1 / span 12" }}
      />,
    )
    const outer = screen.getByTestId("focus-builder-placed-widget")
    expect(outer).toHaveAttribute("data-selected", "true")
    const styleAttr = outer.getAttribute("style") ?? ""
    expect(styleAttr).toMatch(/outline.*var\(--accent\)/i)
  })

  it("does NOT show selection chrome when not selected", () => {
    render(
      <PlacedWidgetCore
        placement={placement}
        selected={false}
        onSelect={() => {}}
        themeTokens={tokens}
        outerStyle={{ gridColumn: "1 / span 12" }}
      />,
    )
    const outer = screen.getByTestId("focus-builder-placed-widget")
    expect(outer).toHaveAttribute("data-selected", "false")
    const styleAttr = outer.getAttribute("style") ?? ""
    // Transparent outline holds the selection chrome layer present
    // but invisible — preserves layout, prevents jump-on-select.
    expect(styleAttr).toMatch(/outline:.*transparent/i)
  })

  it("fires onSelect with placement.id on click", () => {
    const onSelect = vi.fn()
    render(
      <PlacedWidgetCore
        placement={placement}
        selected={false}
        onSelect={onSelect}
        themeTokens={tokens}
        outerStyle={{ gridColumn: "1 / span 12" }}
      />,
    )
    fireEvent.click(screen.getByTestId("focus-builder-placed-widget"))
    expect(onSelect).toHaveBeenCalledWith("w-core-test-1")
  })

  it("fires onSelect on Enter keyboard activation", () => {
    const onSelect = vi.fn()
    render(
      <PlacedWidgetCore
        placement={placement}
        selected={false}
        onSelect={onSelect}
        themeTokens={tokens}
        outerStyle={{ gridColumn: "1 / span 12" }}
      />,
    )
    fireEvent.keyDown(screen.getByTestId("focus-builder-placed-widget"), {
      key: "Enter",
    })
    expect(onSelect).toHaveBeenCalledWith("w-core-test-1")
  })

  it("stops propagation on click (parent canvas onClick is not fired)", () => {
    const onSelect = vi.fn()
    const parentClick = vi.fn()
    render(
      <div onClick={parentClick}>
        <PlacedWidgetCore
          placement={placement}
          selected={false}
          onSelect={onSelect}
          themeTokens={tokens}
          outerStyle={{ gridColumn: "1 / span 12" }}
        />
      </div>,
    )
    fireEvent.click(screen.getByTestId("focus-builder-placed-widget"))
    expect(onSelect).toHaveBeenCalledTimes(1)
    expect(parentClick).not.toHaveBeenCalled()
  })

  it("renders 'Unknown widget' fallback when widget_slug not in registry", () => {
    const bad: WidgetPlacement = {
      id: "w-bad",
      widget_slug: "nonexistent-widget-slug-9999",
      column_start: 1,
      column_span: 12,
      chrome: {},
    }
    render(
      <PlacedWidgetCore
        placement={bad}
        selected={false}
        onSelect={() => {}}
        themeTokens={tokens}
        outerStyle={{ gridColumn: "1 / span 12" }}
      />,
    )
    expect(
      screen.getByText(/Unknown widget: nonexistent-widget-slug-9999/i),
    ).toBeInTheDocument()
  })
})

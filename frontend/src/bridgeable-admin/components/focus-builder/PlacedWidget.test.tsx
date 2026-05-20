/**
 * PlacedWidget unit tests (sub-arc FF-2 — regression preservation).
 *
 * `PlacedWidget` was inline inside `FocusBuilderCanvas` pre-FF-2;
 * FF-2 extracted it to its own file as a thin grid-positioning shell
 * that delegates to `PlacedWidgetCore`. These tests assert the grid
 * positioning math (column_start + column_span → gridColumn CSS) and
 * regression-cover F-3 + F-3.1c behavior.
 */
import { describe, expect, it } from "vitest"
import { render, screen } from "@testing-library/react"

import "@/lib/visual-editor/registry/auto-register"

import { BASE_TOKENS } from "@/lib/visual-editor/themes/base-tokens"

import { PlacedWidget } from "./PlacedWidget"
import type { WidgetPlacement } from "@/bridgeable-admin/hooks/useFocusTemplateDraft"

const tokens = { ...BASE_TOKENS.light }

describe("PlacedWidget (grid positioning shell)", () => {
  it("computes gridColumn from column_start + column_span", () => {
    const placement: WidgetPlacement = {
      id: "w-pw-1",
      widget_slug: "today-pin-widget",
      column_start: 3,
      column_span: 4,
      chrome: {},
    }
    render(
      <PlacedWidget
        placement={placement}
        selected={false}
        onSelect={() => {}}
        columns={12}
        themeTokens={tokens}
      />,
    )
    const outer = screen.getByTestId("focus-builder-placed-widget")
    const styleAttr = outer.getAttribute("style") ?? ""
    expect(styleAttr).toMatch(/grid-column:\s*3\s*\/\s*span\s*4/i)
  })

  it("clamps column_start within columns count", () => {
    const placement: WidgetPlacement = {
      id: "w-pw-2",
      widget_slug: "today-pin-widget",
      column_start: 99, // out of bounds
      column_span: 2,
      chrome: {},
    }
    render(
      <PlacedWidget
        placement={placement}
        selected={false}
        onSelect={() => {}}
        columns={12}
        themeTokens={tokens}
      />,
    )
    const outer = screen.getByTestId("focus-builder-placed-widget")
    const styleAttr = outer.getAttribute("style") ?? ""
    // Clamped to max columns=12.
    expect(styleAttr).toMatch(/grid-column:\s*12\s*\/\s*span\s*2/i)
  })

  it("falls back to defaults when column_start/column_span absent", () => {
    const placement: WidgetPlacement = {
      id: "w-pw-3",
      widget_slug: "today-pin-widget",
      chrome: {},
    }
    render(
      <PlacedWidget
        placement={placement}
        selected={false}
        onSelect={() => {}}
        columns={12}
        themeTokens={tokens}
      />,
    )
    const outer = screen.getByTestId("focus-builder-placed-widget")
    const styleAttr = outer.getAttribute("style") ?? ""
    // Defaults: start=1, span=4.
    expect(styleAttr).toMatch(/grid-column:\s*1\s*\/\s*span\s*4/i)
  })

  it("delegates chrome rendering to PlacedWidgetCore (preserves F-3.1c)", () => {
    const placement: WidgetPlacement = {
      id: "w-pw-4",
      widget_slug: "day-strip-widget",
      column_start: 1,
      column_span: 12,
      chrome: {},
    }
    render(
      <PlacedWidget
        placement={placement}
        selected={false}
        onSelect={() => {}}
        columns={12}
        themeTokens={tokens}
      />,
    )
    const outer = screen.getByTestId("focus-builder-placed-widget")
    const styleAttr = outer.getAttribute("style") ?? ""
    expect(styleAttr).toMatch(/box-shadow/i)
    expect(styleAttr).toMatch(/border-radius/i)
    expect(styleAttr).toMatch(/padding/i)
  })

  it("inner core test-id present (FF-2 operator-observable anchor)", () => {
    const placement: WidgetPlacement = {
      id: "w-pw-5",
      widget_slug: "day-strip-widget",
      column_start: 1,
      column_span: 12,
      chrome: {},
    }
    render(
      <PlacedWidget
        placement={placement}
        selected={false}
        onSelect={() => {}}
        columns={12}
        themeTokens={tokens}
      />,
    )
    expect(
      screen.getByTestId("focus-builder-placed-widget-core"),
    ).toBeInTheDocument()
  })
})

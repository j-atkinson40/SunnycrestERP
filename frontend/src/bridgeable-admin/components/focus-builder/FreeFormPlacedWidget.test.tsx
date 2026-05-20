/**
 * FreeFormPlacedWidget unit tests (sub-arc FF-2).
 *
 * Asserts absolute-positioning math: pixel coords are read from
 * placement.x/y/width/height/z_index and emitted as inline styles.
 * Per the operator-observable assertion canon (2026-05-20 late-
 * evening), assertions target the rendered element's inline style
 * attribute — the load-bearing render-side contract.
 */
import { describe, expect, it } from "vitest"
import { render, screen } from "@testing-library/react"

import "@/lib/visual-editor/registry/auto-register"

import { BASE_TOKENS } from "@/lib/visual-editor/themes/base-tokens"

import { FreeFormPlacedWidget } from "./FreeFormPlacedWidget"
import type { WidgetPlacement } from "@/bridgeable-admin/hooks/useFocusTemplateDraft"

const tokens = { ...BASE_TOKENS.light }

describe("FreeFormPlacedWidget (absolute positioning shell)", () => {
  it("emits position:absolute + left/top/width/height from placement", () => {
    const placement: WidgetPlacement = {
      id: "w-ff-1",
      widget_slug: "today-pin-widget",
      x: 100,
      y: 200,
      width: 240,
      height: 120,
      chrome: {},
    }
    render(
      <FreeFormPlacedWidget
        placement={placement}
        selected={false}
        onSelect={() => {}}
        themeTokens={tokens}
      />,
    )
    const outer = screen.getByTestId("focus-builder-placed-widget")
    const styleAttr = outer.getAttribute("style") ?? ""
    expect(styleAttr).toMatch(/position:\s*absolute/i)
    expect(styleAttr).toMatch(/left:\s*100px/i)
    expect(styleAttr).toMatch(/top:\s*200px/i)
    expect(styleAttr).toMatch(/width:\s*240px/i)
    expect(styleAttr).toMatch(/height:\s*120px/i)
  })

  it("applies z_index when supplied", () => {
    const placement: WidgetPlacement = {
      id: "w-ff-2",
      widget_slug: "today-pin-widget",
      x: 0,
      y: 0,
      width: 200,
      height: 100,
      z_index: 5,
      chrome: {},
    }
    render(
      <FreeFormPlacedWidget
        placement={placement}
        selected={false}
        onSelect={() => {}}
        themeTokens={tokens}
      />,
    )
    const outer = screen.getByTestId("focus-builder-placed-widget")
    const styleAttr = outer.getAttribute("style") ?? ""
    expect(styleAttr).toMatch(/z-index:\s*5/i)
  })

  it("defaults z_index to 0 when absent", () => {
    const placement: WidgetPlacement = {
      id: "w-ff-3",
      widget_slug: "today-pin-widget",
      x: 0,
      y: 0,
      width: 200,
      height: 100,
      chrome: {},
    }
    render(
      <FreeFormPlacedWidget
        placement={placement}
        selected={false}
        onSelect={() => {}}
        themeTokens={tokens}
      />,
    )
    const outer = screen.getByTestId("focus-builder-placed-widget")
    const styleAttr = outer.getAttribute("style") ?? ""
    expect(styleAttr).toMatch(/z-index:\s*0/i)
  })

  it("defensive fallback to platform free-form default (320×180) when width/height absent", () => {
    const placement: WidgetPlacement = {
      id: "w-ff-4",
      widget_slug: "today-pin-widget",
      x: 50,
      y: 60,
      chrome: {},
    }
    render(
      <FreeFormPlacedWidget
        placement={placement}
        selected={false}
        onSelect={() => {}}
        themeTokens={tokens}
      />,
    )
    const outer = screen.getByTestId("focus-builder-placed-widget")
    const styleAttr = outer.getAttribute("style") ?? ""
    expect(styleAttr).toMatch(/width:\s*320px/i)
    expect(styleAttr).toMatch(/height:\s*180px/i)
  })

  it("defensive fallback to 0/0 when x/y absent", () => {
    const placement: WidgetPlacement = {
      id: "w-ff-5",
      widget_slug: "today-pin-widget",
      width: 240,
      height: 120,
      chrome: {},
    }
    render(
      <FreeFormPlacedWidget
        placement={placement}
        selected={false}
        onSelect={() => {}}
        themeTokens={tokens}
      />,
    )
    const outer = screen.getByTestId("focus-builder-placed-widget")
    const styleAttr = outer.getAttribute("style") ?? ""
    expect(styleAttr).toMatch(/left:\s*0px/i)
    expect(styleAttr).toMatch(/top:\s*0px/i)
  })

  it("inner core test-id present (FF-2 anchor)", () => {
    const placement: WidgetPlacement = {
      id: "w-ff-6",
      widget_slug: "day-strip-widget",
      x: 10,
      y: 20,
      width: 240,
      height: 120,
      chrome: {},
    }
    render(
      <FreeFormPlacedWidget
        placement={placement}
        selected={false}
        onSelect={() => {}}
        themeTokens={tokens}
      />,
    )
    expect(
      screen.getByTestId("focus-builder-placed-widget-core"),
    ).toBeInTheDocument()
  })

  it("delegates chrome rendering to PlacedWidgetCore (cross-shape parity)", () => {
    const placement: WidgetPlacement = {
      id: "w-ff-7",
      widget_slug: "day-strip-widget",
      x: 0,
      y: 0,
      width: 240,
      height: 120,
      chrome: {},
    }
    render(
      <FreeFormPlacedWidget
        placement={placement}
        selected={false}
        onSelect={() => {}}
        themeTokens={tokens}
      />,
    )
    const outer = screen.getByTestId("focus-builder-placed-widget")
    const styleAttr = outer.getAttribute("style") ?? ""
    // Chrome-resolved styles applied at the outer wrapper just like
    // grid path (cross-shape parity for chrome inheritance).
    expect(styleAttr).toMatch(/box-shadow/i)
    expect(styleAttr).toMatch(/border-radius/i)
    expect(styleAttr).toMatch(/padding/i)
  })
})

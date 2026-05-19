/**
 * FocusBuilderPalette tests — sub-arc F-3.
 *
 * Registry is populated via auto-register.ts side-effect import at app
 * bootstrap. F-3 placeholder widgets registered in
 * `registrations/focus-builder-widgets.ts` are queryable at test time.
 */
import { describe, expect, it } from "vitest"
import { render, screen, within } from "@testing-library/react"
import { DndContext } from "@dnd-kit/core"

import "@/lib/visual-editor/registry/auto-register"

import {
  FocusBuilderPalette,
  PALETTE_ITEM_PREFIX,
  paletteItemIdToSlug,
} from "./FocusBuilderPalette"

function wrap(ui: React.ReactNode) {
  return render(<DndContext>{ui}</DndContext>)
}

describe("FocusBuilderPalette", () => {
  it("renders categories from the component registry", () => {
    wrap(<FocusBuilderPalette />)
    const palette = screen.getByTestId("widget-palette")
    expect(palette).toBeInTheDocument()
    // At least the Information category (Day Strip + Today Pin) and
    // Map category (Map placeholder) ship as F-3 seeds.
    expect(screen.getAllByTestId("widget-palette-category").length).toBeGreaterThanOrEqual(2)
  })

  it("namespaces item ids with palette-widget: prefix", () => {
    wrap(<FocusBuilderPalette />)
    const items = screen.getAllByTestId("widget-palette-item")
    expect(items.length).toBeGreaterThan(0)
    for (const it of items) {
      const id = it.getAttribute("data-item-id") ?? ""
      expect(id.startsWith(PALETTE_ITEM_PREFIX)).toBe(true)
    }
  })

  it("paletteItemIdToSlug strips the prefix", () => {
    expect(paletteItemIdToSlug("palette-widget:day-strip-widget")).toBe(
      "day-strip-widget",
    )
    expect(paletteItemIdToSlug("not-a-palette-id")).toBeNull()
  })

  it("groups F-3 seed widgets into expected categories", () => {
    wrap(<FocusBuilderPalette />)
    const cats = screen.getAllByTestId("widget-palette-category")
    const byId = new Map(
      cats.map((c) => [c.getAttribute("data-category-id"), c]),
    )
    // Information category should contain Day Strip + Today Pin.
    const info = byId.get("information")
    expect(info).toBeDefined()
    if (info) {
      expect(within(info).getByText("Day Strip")).toBeInTheDocument()
      expect(within(info).getByText("Today Pin")).toBeInTheDocument()
    }
    const map = byId.get("map")
    expect(map).toBeDefined()
    if (map) {
      // Category contains the Map placeholder widget (slug =
      // map-placeholder-widget) — assert via data attribute.
      const items = within(map).getAllByTestId("widget-palette-item")
      const slugs = items.map((it) => it.getAttribute("data-item-id"))
      expect(slugs).toContain("palette-widget:map-placeholder-widget")
    }
  })

  it("propagates disabled to the primitive", () => {
    wrap(<FocusBuilderPalette disabled />)
    const palette = screen.getByTestId("widget-palette")
    expect(palette.getAttribute("data-disabled")).toBe("true")
  })
})

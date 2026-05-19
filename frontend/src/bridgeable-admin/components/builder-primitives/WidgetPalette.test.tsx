/**
 * WidgetPalette primitive tests — sub-arc F-3.
 */
import { describe, expect, it } from "vitest"
import { render, screen } from "@testing-library/react"
import { DndContext } from "@dnd-kit/core"

import { WidgetPalette, type PaletteCategory } from "./WidgetPalette"

function wrap(ui: React.ReactNode) {
  return render(<DndContext>{ui}</DndContext>)
}

describe("WidgetPalette", () => {
  it("renders categories with items", () => {
    const cats: PaletteCategory[] = [
      {
        id: "info",
        label: "Information",
        items: [
          { id: "palette-widget:a", label: "Alpha", description: "A widget" },
          { id: "palette-widget:b", label: "Beta" },
        ],
      },
      {
        id: "map",
        label: "Maps",
        items: [{ id: "palette-widget:m", label: "Map" }],
      },
    ]
    wrap(<WidgetPalette categories={cats} />)
    expect(screen.getByText("Information")).toBeInTheDocument()
    expect(screen.getByText("Alpha")).toBeInTheDocument()
    expect(screen.getByText("A widget")).toBeInTheDocument()
    expect(screen.getByText("Beta")).toBeInTheDocument()
    expect(screen.getByText("Maps")).toBeInTheDocument()
    expect(screen.getByText("Map")).toBeInTheDocument()
    expect(screen.getAllByTestId("widget-palette-item").length).toBe(3)
  })

  it("renders empty palette when zero categories", () => {
    wrap(<WidgetPalette categories={[]} />)
    expect(screen.getByTestId("widget-palette-empty")).toBeInTheDocument()
  })

  it("renders custom empty hint", () => {
    wrap(<WidgetPalette categories={[]} emptyHint="Custom hint" />)
    expect(screen.getByText("Custom hint")).toBeInTheDocument()
  })

  it("renders 'No items' when a category has zero items", () => {
    wrap(
      <WidgetPalette
        categories={[{ id: "x", label: "Empty Cat", items: [] }]}
      />,
    )
    expect(
      screen.getByTestId("widget-palette-category-empty"),
    ).toBeInTheDocument()
  })

  it("attaches item id to each draggable row", () => {
    wrap(
      <WidgetPalette
        categories={[
          {
            id: "i",
            label: "I",
            items: [{ id: "palette-widget:foo", label: "Foo" }],
          },
        ]}
      />,
    )
    const item = screen.getByTestId("widget-palette-item")
    expect(item.getAttribute("data-item-id")).toBe("palette-widget:foo")
  })

  it("renders disabled state via data attribute", () => {
    wrap(
      <WidgetPalette
        disabled
        categories={[
          {
            id: "i",
            label: "I",
            items: [{ id: "palette-widget:foo", label: "Foo" }],
          },
        ]}
      />,
    )
    const palette = screen.getByTestId("widget-palette")
    expect(palette.getAttribute("data-disabled")).toBe("true")
    const item = screen.getByTestId("widget-palette-item")
    expect(item.getAttribute("aria-disabled")).toBe("true")
  })
})

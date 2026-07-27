/**
 * CommandBarSurfaceHost — S-2 generalization + S-1 regression.
 *
 * The host now dispatches every surface via getWidgetRenderer instead of
 * rendering EntityPortalCard by name. These tests pin:
 *   - S-1 REGRESSION: a highlighted entity still renders via
 *     "entity-card.portal" with byte-identical props (widgetId, config,
 *     surface, variant) to the pre-S-2 host.
 *   - S-2: param-keyed SurfaceDescriptors render via their widgetId.
 *   - §4.3 discipline lives in the host: null when empty, cap at 3,
 *     no drag/resize affordances.
 */

import { beforeEach, describe, expect, it } from "vitest"
import { render, screen } from "@testing-library/react"

import {
  _resetWidgetRendererRegistryForTests,
  registerWidgetRenderer,
  type WidgetRendererProps,
} from "@/components/focus/canvas/widget-renderers"
import type { SurfaceDescriptor } from "@/components/command-bar-surfaces/types"

import { CommandBarSurfaceHost } from "./CommandBarSurfaceHost"

function FakeWidget({
  widgetId,
  config,
  surface,
  variant_id,
}: WidgetRendererProps) {
  return (
    <div
      data-testid={`fake:${widgetId}`}
      data-config={JSON.stringify(config ?? null)}
      data-surface={surface}
      data-variant={variant_id}
    />
  )
}

beforeEach(() => {
  _resetWidgetRendererRegistryForTests()
  registerWidgetRenderer("entity-card.portal", FakeWidget)
  registerWidgetRenderer("surface.quote-preview", FakeWidget)
  registerWidgetRenderer("surface.price-list-reference", FakeWidget)
})

describe("CommandBarSurfaceHost", () => {
  it("renders nothing when there's no entity and no surfaces", () => {
    render(<CommandBarSurfaceHost highlighted={null} surfaces={[]} />)
    expect(
      screen.queryByTestId("command-bar-surface-host"),
    ).not.toBeInTheDocument()
  })

  it("S-1 regression: a highlighted entity dispatches entity-card.portal with identical props", () => {
    render(
      <CommandBarSurfaceHost
        highlighted={{ entityType: "contact", entityId: "c1" }}
        surfaces={[]}
      />,
    )
    const card = screen.getByTestId("fake:portal:contact:c1")
    expect(card).toBeInTheDocument()
    expect(card).toHaveAttribute(
      "data-config",
      JSON.stringify({ entity_type: "contact", entity_id: "c1" }),
    )
    expect(card).toHaveAttribute("data-surface", "command_bar")
    expect(card).toHaveAttribute("data-variant", "brief")
  })

  it("S-2: param-keyed surfaces render via their widgetId", () => {
    const surfaces: SurfaceDescriptor[] = [
      {
        key: "quote_preview",
        widgetId: "surface.quote-preview",
        variantId: "brief",
        config: { lines: [] },
      },
      {
        key: "price_list_reference",
        widgetId: "surface.price-list-reference",
        variantId: "brief",
        config: { products: ["Monticello"] },
      },
    ]
    render(<CommandBarSurfaceHost highlighted={null} surfaces={surfaces} />)
    expect(
      screen.getByTestId("fake:quote_preview"),
    ).toBeInTheDocument()
    const plr = screen.getByTestId("fake:price_list_reference")
    expect(plr).toHaveAttribute(
      "data-config",
      JSON.stringify({ products: ["Monticello"] }),
    )
  })

  it("caps visible surfaces at 3 (§4.3 max 2–3)", () => {
    const surfaces: SurfaceDescriptor[] = Array.from({ length: 4 }, (_, i) => ({
      key: `s${i}`,
      widgetId: "surface.quote-preview",
    }))
    render(<CommandBarSurfaceHost highlighted={null} surfaces={surfaces} />)
    const host = screen.getByTestId("command-bar-surface-host")
    expect(host.querySelectorAll('[data-testid^="fake:"]').length).toBe(3)
  })

  it("entity card renders before S-2 surfaces", () => {
    render(
      <CommandBarSurfaceHost
        highlighted={{ entityType: "invoice", entityId: "i1" }}
        surfaces={[{ key: "quote_preview", widgetId: "surface.quote-preview" }]}
      />,
    )
    const host = screen.getByTestId("command-bar-surface-host")
    const ids = Array.from(
      host.querySelectorAll('[data-testid^="fake:"]'),
    ).map((el) => el.getAttribute("data-testid"))
    expect(ids).toEqual(["fake:portal:invoice:i1", "fake:quote_preview"])
  })

  it("adds no drag/resize affordances (Act discipline)", () => {
    render(
      <CommandBarSurfaceHost
        highlighted={{ entityType: "contact", entityId: "c1" }}
        surfaces={[]}
      />,
    )
    const host = screen.getByTestId("command-bar-surface-host")
    expect(host).not.toHaveAttribute("draggable", "true")
    expect(host.querySelector("[data-drag-handle]")).toBeNull()
    expect(
      host.querySelector('[data-testid*="resize"]'),
    ).toBeNull()
  })
})

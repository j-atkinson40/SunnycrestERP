/**
 * FreeFormPlacedWidget unit tests (sub-arcs FF-2 + FF-3).
 *
 * FF-2 asserted absolute-positioning math on the (then sole)
 * PlacedWidgetCore outer div. FF-3 introduced a draggable wrapper
 * above the core — positioning + drag listeners now live on
 * `focus-builder-freeform-placed-widget-draggable`. The core inside
 * fills the wrapper (width/height: 100%). Tests below preserve the
 * operator-observable assertion canon (inline style on the rendered
 * positioning element) but retarget the new wrapper.
 *
 * useDraggable requires a DndContext ancestor; tests render the
 * component inside a no-op DndContext.
 */
import type { ReactNode } from "react"
import { describe, expect, it } from "vitest"
import { render, screen } from "@testing-library/react"
import { DndContext } from "@dnd-kit/core"

import "@/lib/visual-editor/registry/auto-register"

import { BASE_TOKENS } from "@/lib/visual-editor/themes/base-tokens"

import {
  FreeFormPlacedWidget,
  freeFormDraggableIdFor,
  parseFreeFormDraggableId,
  FREE_FORM_DRAGGABLE_ID_PREFIX,
} from "./FreeFormPlacedWidget"
import type { WidgetPlacement } from "@/bridgeable-admin/hooks/useFocusTemplateDraft"

const tokens = { ...BASE_TOKENS.light }

function renderWithDnd(node: ReactNode) {
  return render(<DndContext>{node}</DndContext>)
}

describe("FreeFormPlacedWidget (absolute positioning + drag shell)", () => {
  it("emits position:absolute + left/top/width/height on the draggable wrapper", () => {
    const placement: WidgetPlacement = {
      id: "w-ff-1",
      widget_slug: "today-pin-widget",
      x: 100,
      y: 200,
      width: 240,
      height: 120,
      chrome: {},
    }
    renderWithDnd(
      <FreeFormPlacedWidget
        placement={placement}
        selected={false}
        onSelect={() => {}}
        themeTokens={tokens}
      />,
    )
    const draggable = screen.getByTestId(
      "focus-builder-freeform-placed-widget-draggable",
    )
    const styleAttr = draggable.getAttribute("style") ?? ""
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
    renderWithDnd(
      <FreeFormPlacedWidget
        placement={placement}
        selected={false}
        onSelect={() => {}}
        themeTokens={tokens}
      />,
    )
    const draggable = screen.getByTestId(
      "focus-builder-freeform-placed-widget-draggable",
    )
    const styleAttr = draggable.getAttribute("style") ?? ""
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
    renderWithDnd(
      <FreeFormPlacedWidget
        placement={placement}
        selected={false}
        onSelect={() => {}}
        themeTokens={tokens}
      />,
    )
    const draggable = screen.getByTestId(
      "focus-builder-freeform-placed-widget-draggable",
    )
    const styleAttr = draggable.getAttribute("style") ?? ""
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
    renderWithDnd(
      <FreeFormPlacedWidget
        placement={placement}
        selected={false}
        onSelect={() => {}}
        themeTokens={tokens}
      />,
    )
    const draggable = screen.getByTestId(
      "focus-builder-freeform-placed-widget-draggable",
    )
    const styleAttr = draggable.getAttribute("style") ?? ""
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
    renderWithDnd(
      <FreeFormPlacedWidget
        placement={placement}
        selected={false}
        onSelect={() => {}}
        themeTokens={tokens}
      />,
    )
    const draggable = screen.getByTestId(
      "focus-builder-freeform-placed-widget-draggable",
    )
    const styleAttr = draggable.getAttribute("style") ?? ""
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
    renderWithDnd(
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
    renderWithDnd(
      <FreeFormPlacedWidget
        placement={placement}
        selected={false}
        onSelect={() => {}}
        themeTokens={tokens}
      />,
    )
    // Chrome resolves on PlacedWidgetCore's outer (preserved test-id).
    const core = screen.getByTestId("focus-builder-placed-widget")
    const styleAttr = core.getAttribute("style") ?? ""
    expect(styleAttr).toMatch(/box-shadow/i)
    expect(styleAttr).toMatch(/border-radius/i)
    expect(styleAttr).toMatch(/padding/i)
  })

  // ── FF-3 drag wiring assertions ──────────────────────────────────────
  it("FF-3 — draggable wrapper exposes cursor: grab idle", () => {
    const placement: WidgetPlacement = {
      id: "w-ff-drag-1",
      widget_slug: "today-pin-widget",
      x: 0,
      y: 0,
      width: 240,
      height: 120,
      chrome: {},
    }
    renderWithDnd(
      <FreeFormPlacedWidget
        placement={placement}
        selected={false}
        onSelect={() => {}}
        themeTokens={tokens}
      />,
    )
    const draggable = screen.getByTestId(
      "focus-builder-freeform-placed-widget-draggable",
    )
    expect(draggable.getAttribute("style") ?? "").toMatch(/cursor:\s*grab/i)
    expect(draggable.getAttribute("data-dragging")).toBe("false")
  })

  it("FF-3 — data-placement-id attribute exposes placement id for drag-end lookup", () => {
    const placement: WidgetPlacement = {
      id: "placement-xyz",
      widget_slug: "today-pin-widget",
      x: 0,
      y: 0,
      width: 240,
      height: 120,
      chrome: {},
    }
    renderWithDnd(
      <FreeFormPlacedWidget
        placement={placement}
        selected={false}
        onSelect={() => {}}
        themeTokens={tokens}
      />,
    )
    const draggable = screen.getByTestId(
      "focus-builder-freeform-placed-widget-draggable",
    )
    expect(draggable.getAttribute("data-placement-id")).toBe("placement-xyz")
  })

  it("FF-3 — draggable id helpers roundtrip", () => {
    const id = freeFormDraggableIdFor("placement-abc")
    expect(id.startsWith(FREE_FORM_DRAGGABLE_ID_PREFIX)).toBe(true)
    expect(parseFreeFormDraggableId(id)).toBe("placement-abc")
    expect(parseFreeFormDraggableId("palette-widget:foo")).toBeNull()
  })
})

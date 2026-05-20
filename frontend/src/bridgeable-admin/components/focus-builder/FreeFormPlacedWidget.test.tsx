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
import { describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen } from "@testing-library/react"
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

  // ── FF-4 resize-handle conditional render assertions ─────────────
  it("FF-4 — renders 8 resize handles when selected", () => {
    const placement: WidgetPlacement = {
      id: "w-ff-resize-1",
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
        selected
        onSelect={() => {}}
        themeTokens={tokens}
      />,
    )
    const handles = screen.getAllByTestId("focus-builder-resize-handle")
    expect(handles).toHaveLength(8)
  })

  // ── FF-5 right-click context menu wiring ─────────────────────────
  it("FF-5 — fires onContextMenuRequest with placement id + cursor position on right-click", () => {
    const onContextMenu = vi.fn()
    const placement: WidgetPlacement = {
      id: "ctx-1",
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
        onContextMenuRequest={onContextMenu}
      />,
    )
    const draggable = screen.getByTestId(
      "focus-builder-freeform-placed-widget-draggable",
    )
    fireEvent.contextMenu(draggable, { clientX: 320, clientY: 410 })
    expect(onContextMenu).toHaveBeenCalledTimes(1)
    expect(onContextMenu).toHaveBeenCalledWith("ctx-1", { x: 320, y: 410 })
  })

  it("FF-5 — right-click does NOT change selection (left-click owns selection)", () => {
    const onSelect = vi.fn()
    const onContextMenu = vi.fn()
    const placement: WidgetPlacement = {
      id: "ctx-2",
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
        onSelect={onSelect}
        themeTokens={tokens}
        onContextMenuRequest={onContextMenu}
      />,
    )
    const draggable = screen.getByTestId(
      "focus-builder-freeform-placed-widget-draggable",
    )
    fireEvent.contextMenu(draggable, { clientX: 0, clientY: 0 })
    expect(onContextMenu).toHaveBeenCalledTimes(1)
    expect(onSelect).not.toHaveBeenCalled()
  })

  it("FF-5 — no onContextMenuRequest prop → no handler errors; native context menu defaults", () => {
    const placement: WidgetPlacement = {
      id: "ctx-3",
      widget_slug: "today-pin-widget",
      x: 0,
      y: 0,
      width: 240,
      height: 120,
      chrome: {},
    }
    // Render WITHOUT onContextMenuRequest. Right-click should not
    // throw; the handler short-circuits when the callback is absent.
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
    // Should not throw.
    fireEvent.contextMenu(draggable, { clientX: 50, clientY: 60 })
    expect(draggable).toBeInTheDocument()
  })

  it("FF-4 — does not render resize handles when not selected AND not hovered", () => {
    const placement: WidgetPlacement = {
      id: "w-ff-resize-2",
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
    expect(
      screen.queryAllByTestId("focus-builder-resize-handle"),
    ).toHaveLength(0)
    expect(
      screen.queryByTestId("focus-builder-resize-handle-overlay"),
    ).not.toBeInTheDocument()
  })

  // ── 2026-05-20 hover-state refinement (Finding 1) ────────────────
  //
  // Per the read-only investigation
  // `docs/investigations/2026-05-20-resize-handle-ux-refinements.md`
  // §2 (Finding 1) — Q-10's investigation-time lock of "handles
  // visible only when selected" was refined by operator-experience
  // data to "handles visible on hover OR selection." The 8 handles
  // now render on pointerenter even before the operator commits to a
  // selection click.
  //
  // Operator-observable assertion canon (2026-05-19 late-evening):
  // tests assert on rendered DOM at the specific rendered element
  // (handle data-testid presence / absence on the
  // focus-builder-resize-handle elements themselves).
  // ─────────────────────────────────────────────────────────────────

  it("hover-state refinement — renders 8 handles on pointerenter (not selected)", () => {
    const placement: WidgetPlacement = {
      id: "w-ff-hover-1",
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
    // Default: not hovered, not selected → no handles.
    expect(
      screen.queryAllByTestId("focus-builder-resize-handle"),
    ).toHaveLength(0)

    const draggable = screen.getByTestId(
      "focus-builder-freeform-placed-widget-draggable",
    )
    fireEvent.pointerEnter(draggable)

    // After hover-in: 8 handles appear without a selection click.
    expect(
      screen.getAllByTestId("focus-builder-resize-handle"),
    ).toHaveLength(8)
  })

  it("hover-state refinement — renders 8 handles when both hovered AND selected", () => {
    const placement: WidgetPlacement = {
      id: "w-ff-hover-2",
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
        selected
        onSelect={() => {}}
        themeTokens={tokens}
      />,
    )
    const draggable = screen.getByTestId(
      "focus-builder-freeform-placed-widget-draggable",
    )
    fireEvent.pointerEnter(draggable)
    expect(
      screen.getAllByTestId("focus-builder-resize-handle"),
    ).toHaveLength(8)
  })

  it("hover-state refinement — pointerleave preserves handles when selected", () => {
    const placement: WidgetPlacement = {
      id: "w-ff-hover-3",
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
        selected
        onSelect={() => {}}
        themeTokens={tokens}
      />,
    )
    const draggable = screen.getByTestId(
      "focus-builder-freeform-placed-widget-draggable",
    )
    fireEvent.pointerEnter(draggable)
    fireEvent.pointerLeave(draggable)
    // Selection branch keeps handles visible even after hover-out.
    expect(
      screen.getAllByTestId("focus-builder-resize-handle"),
    ).toHaveLength(8)
  })

  it("hover-state refinement — pointerleave hides handles when NOT selected", () => {
    const placement: WidgetPlacement = {
      id: "w-ff-hover-4",
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
    fireEvent.pointerEnter(draggable)
    expect(
      screen.getAllByTestId("focus-builder-resize-handle"),
    ).toHaveLength(8)
    fireEvent.pointerLeave(draggable)
    expect(
      screen.queryAllByTestId("focus-builder-resize-handle"),
    ).toHaveLength(0)
  })

  it("hover-state refinement — touch/pointer-coarse fallback: selection still shows handles even without pointerenter", () => {
    // Touch devices may not fire pointerenter reliably. The selection
    // branch is the canonical fallback for those users; this test
    // documents the contract.
    const placement: WidgetPlacement = {
      id: "w-ff-hover-5",
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
        selected
        onSelect={() => {}}
        themeTokens={tokens}
      />,
    )
    // No pointerenter fired (simulating touch-tap-to-select). The
    // selected branch alone renders handles.
    expect(
      screen.getAllByTestId("focus-builder-resize-handle"),
    ).toHaveLength(8)
  })
})

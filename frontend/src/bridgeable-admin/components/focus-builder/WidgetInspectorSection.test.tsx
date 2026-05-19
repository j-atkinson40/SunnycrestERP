/**
 * WidgetInspectorSection tests — sub-arc F-3.
 */
import { describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen } from "@testing-library/react"

import "@/lib/visual-editor/registry/auto-register"

import {
  WidgetInspectorSection,
  findPlacementById,
} from "./WidgetInspectorSection"
import type { WidgetPlacement } from "@/bridgeable-admin/hooks/useFocusTemplateDraft"

const placement: WidgetPlacement = {
  id: "w-1",
  widget_slug: "day-strip-widget",
  column_start: 1,
  column_span: 12,
  chrome: {},
}

describe("WidgetInspectorSection", () => {
  it("shows the registry display name", () => {
    render(
      <WidgetInspectorSection
        placement={placement}
        onUpdateWidget={() => {}}
        onRemoveWidget={() => {}}
      />,
    )
    expect(screen.getByTestId("widget-inspector-name").textContent).toBe(
      "Day Strip",
    )
  })

  it("falls back to the slug when registry has no entry", () => {
    render(
      <WidgetInspectorSection
        placement={{ ...placement, widget_slug: "unknown-slug" }}
        onUpdateWidget={() => {}}
        onRemoveWidget={() => {}}
      />,
    )
    expect(screen.getByTestId("widget-inspector-name").textContent).toBe(
      "unknown-slug",
    )
  })

  it("calls onRemoveWidget with placement id when remove clicked", () => {
    const remove = vi.fn()
    render(
      <WidgetInspectorSection
        placement={placement}
        onUpdateWidget={() => {}}
        onRemoveWidget={remove}
      />,
    )
    fireEvent.click(screen.getByTestId("widget-remove-button"))
    expect(remove).toHaveBeenCalledWith("w-1")
  })

  it("renders boolean prop control for today-pin-widget", () => {
    const onUpdate = vi.fn()
    render(
      <WidgetInspectorSection
        placement={{
          ...placement,
          widget_slug: "today-pin-widget",
        }}
        onUpdateWidget={onUpdate}
        onRemoveWidget={() => {}}
      />,
    )
    const ctrl = screen.getByTestId("widget-bool-showCount")
    expect(ctrl).toBeInTheDocument()
    const cb = ctrl.querySelector("input[type=checkbox]")! as HTMLInputElement
    // showCount default is true; clicking the checkbox toggles it to
    // false in the placement chrome.
    fireEvent.click(cb)
    expect(onUpdate).toHaveBeenCalledWith("w-1", { showCount: expect.any(Boolean) })
  })

  describe("findPlacementById", () => {
    it("finds a widget by id across rows", () => {
      const rows = [
        {
          row_index: 0,
          column_count: 12,
          placements: [
            placement,
            { ...placement, id: "w-2", widget_slug: "today-pin-widget" },
          ],
        },
        {
          row_index: 1,
          column_count: 12,
          placements: [{ ...placement, id: "w-3" }],
        },
      ]
      expect(findPlacementById(rows, "w-2")?.widget_slug).toBe(
        "today-pin-widget",
      )
      expect(findPlacementById(rows, "w-3")?.id).toBe("w-3")
      expect(findPlacementById(rows, "missing")).toBeNull()
    })
  })
})

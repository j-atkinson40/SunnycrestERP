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

  // ─────────────────────────────────────────────────────────────────
  // F-3.1b — Chrome section: per-placement chrome editing controls
  // ─────────────────────────────────────────────────────────────────
  describe("Chrome section (F-3.1b)", () => {
    function mountWith(p: Partial<WidgetPlacement> = {}, onUpdate = vi.fn()) {
      render(
        <WidgetInspectorSection
          placement={{ ...placement, ...p }}
          onUpdateWidget={onUpdate}
          onRemoveWidget={() => {}}
          themeTokens={{
            "surface-frosted": "#fafaf8",
            "border-subtle": "#e6e2dc",
            "space-3": "12px",
          }}
        />,
      )
      return onUpdate
    }

    it("renders the Chrome section when a widget is selected", () => {
      mountWith()
      // ChromePresetPicker renders preset pills with testids
      // following the canonical pattern; the section title is rendered
      // by PropertySection.
      expect(screen.getByText("Chrome")).toBeInTheDocument()
    })

    it("Chrome section is expanded by default", () => {
      mountWith()
      // When expanded, the elevation row is present; ScrubbableButton
      // renders an accessible label.
      expect(screen.getByLabelText(/elevation/i)).toBeInTheDocument()
    })

    it("Chrome section can be collapsed via the header toggle", () => {
      mountWith()
      // Find the Chrome section title and click its toggle.
      const chromeHeader = screen.getByText("Chrome")
      // The header is a button-row in PropertySection; click it.
      fireEvent.click(chromeHeader)
      // After collapsing, the elevation control should disappear.
      expect(screen.queryByLabelText(/elevation/i)).not.toBeInTheDocument()
    })

    it("fires onUpdateWidget with { elevation } when elevation changes", () => {
      const onUpdate = mountWith()
      const elevation = screen.getByLabelText(/elevation/i) as HTMLButtonElement
      // ScrubbableButton supports keyboard arrow-up to increment.
      fireEvent.keyDown(elevation, { key: "ArrowRight" })
      expect(onUpdate).toHaveBeenCalledWith(
        "w-1",
        expect.objectContaining({ elevation: expect.any(Number) }),
      )
    })

    it("fires onUpdateWidget with { corner_radius } when corner radius changes", () => {
      const onUpdate = mountWith()
      const ctrl = screen.getByLabelText(/corner radius/i) as HTMLButtonElement
      fireEvent.keyDown(ctrl, { key: "ArrowRight" })
      expect(onUpdate).toHaveBeenCalledWith(
        "w-1",
        expect.objectContaining({ corner_radius: expect.any(Number) }),
      )
    })

    it("fires onUpdateWidget with { backdrop_blur } when backdrop blur changes", () => {
      const onUpdate = mountWith()
      const ctrl = screen.getByLabelText(/backdrop blur/i) as HTMLButtonElement
      fireEvent.keyDown(ctrl, { key: "ArrowRight" })
      expect(onUpdate).toHaveBeenCalledWith(
        "w-1",
        expect.objectContaining({ backdrop_blur: expect.any(Number) }),
      )
    })

    it("renders ChromePresetPicker preset pills (preset onChange wired)", () => {
      const onUpdate = mountWith()
      // The canonical Frosted preset is a documented option; the
      // picker exposes the active state via aria-pressed on each pill.
      // We just verify a "frosted"-labeled control is interactive.
      const frosted = screen.getByTestId("preset-pill-frosted")
      fireEvent.click(frosted)
      // Clicking the active pill clears it (toggle to null per
      // ChromePresetPicker contract).
      // Clicking the active pill toggles to null per ChromePresetPicker
      // contract; chromeView default is "frosted" so clicking Frosted
      // clears the preset.
      expect(onUpdate).toHaveBeenCalledWith("w-1", { preset: null })
    })

    it("renders TokenSwatchPicker for background/border/padding", () => {
      mountWith()
      expect(screen.getByText(/^background$/i)).toBeInTheDocument()
      expect(screen.getByText(/^border$/i)).toBeInTheDocument()
      expect(screen.getByText(/^padding$/i)).toBeInTheDocument()
    })

    it("falls back to canonical defaults when placement.chrome is empty", () => {
      mountWith({ chrome: {} })
      // Elevation default 50 should be the rendered value.
      const elevation = screen.getByLabelText(/elevation/i) as HTMLElement
      expect(elevation.textContent).toContain("50")
    })

    it("falls back to canonical defaults when placement.chrome is undefined", () => {
      mountWith({ chrome: undefined as unknown as Record<string, unknown> })
      const elevation = screen.getByLabelText(/elevation/i) as HTMLElement
      expect(elevation.textContent).toContain("50")
    })

    it("uses set chrome fields when present, defaults otherwise", () => {
      mountWith({
        chrome: {
          elevation: 88,
          // corner_radius omitted — should fall back to default 70
        },
      })
      const elevation = screen.getByLabelText(/elevation/i) as HTMLElement
      const cornerRadius = screen.getByLabelText(
        /corner radius/i,
      ) as HTMLElement
      expect(elevation.textContent).toContain("88")
      expect(cornerRadius.textContent).toContain("70")
    })
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

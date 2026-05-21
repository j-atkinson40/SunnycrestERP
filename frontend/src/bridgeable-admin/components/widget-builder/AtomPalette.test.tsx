/**
 * Tests for AtomPalette (WB-4a).
 */
import { DndContext } from "@dnd-kit/core"
import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { ATOM_SECTIONS, AtomPalette } from "./AtomPalette"


function renderWithDnd() {
  return render(
    <DndContext>
      <AtomPalette />
    </DndContext>,
  )
}


describe("AtomPalette", () => {
  it("renders both canonical sections", () => {
    renderWithDnd()
    expect(
      screen.getByTestId("widget-builder-atom-section-content"),
    ).toBeTruthy()
    expect(
      screen.getByTestId("widget-builder-atom-section-container"),
    ).toBeTruthy()
  })

  it("renders all 9 atoms", () => {
    renderWithDnd()
    const atoms = [
      "text_label",
      "value_display",
      "icon",
      "status_badge",
      "divider",
      "image",
      "button",
      "conditional_container",
      "repeater_atom",
    ]
    for (const a of atoms) {
      expect(screen.getByTestId(`widget-builder-atom-tile-${a}`)).toBeTruthy()
    }
  })

  it("groups atoms per Area 3 lock", () => {
    expect(ATOM_SECTIONS).toHaveLength(2)
    const content = ATOM_SECTIONS.find((s) => s.key === "content")
    const container = ATOM_SECTIONS.find((s) => s.key === "container")
    expect(content?.atom_types).toEqual([
      "text_label",
      "value_display",
      "icon",
      "status_badge",
      "divider",
      "image",
    ])
    expect(container?.atom_types).toEqual([
      "conditional_container",
      "repeater_atom",
      "button",
    ])
  })

  it("each tile is keyboard-focusable for KeyboardSensor coverage", () => {
    renderWithDnd()
    const tile = screen.getByTestId("widget-builder-atom-tile-text_label")
    // @dnd-kit's useDraggable adds tabIndex via attributes.
    expect(tile.tagName.toLowerCase()).toBe("button")
  })

  it("draggable tiles carry the atom_type in their data-atom-type", () => {
    renderWithDnd()
    const tile = screen.getByTestId("widget-builder-atom-tile-icon")
    expect(tile.getAttribute("data-atom-type")).toBe("icon")
  })
})

/**
 * Tests for WidgetCanvas (WB-4a).
 */
import { DndContext } from "@dnd-kit/core"
import { fireEvent, render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import type { CompositionBlob } from "@/lib/widget-builder/types/composition-blob"
import { WidgetCanvas } from "./WidgetCanvas"
import {
  insertAtomAt,
  makeDefaultAtomNode,
} from "./atom-tree-helpers"


function emptyBlob(): CompositionBlob {
  return {
    schema_version: 1,
    root_atom_id: "root",
    atom_tree: {
      root: {
        atom_id: "root",
        atom_type: "conditional_container",
        config: { direction: "column", gap_token: "sm" },
        children: [],
      },
    },
    variants: [],
    bindings_catalog: {},
  }
}


function renderCanvas(props: {
  blob: CompositionBlob
  selectedAtomId?: string | null
  onSelect?: (id: string | null) => void
}) {
  return render(
    <DndContext>
      <WidgetCanvas
        blob={props.blob}
        selectedAtomId={props.selectedAtomId ?? null}
        onSelect={props.onSelect ?? (() => {})}
      />
    </DndContext>,
  )
}


describe("WidgetCanvas", () => {
  it("renders the empty-state drop target on empty canvas", () => {
    renderCanvas({ blob: emptyBlob() })
    expect(
      screen.getByTestId("widget-builder-canvas-drop-target-root-0"),
    ).toBeTruthy()
    expect(
      screen.getByText(/drag atoms here to build/i),
    ).toBeTruthy()
  })

  it("renders an insertion indicator between siblings", () => {
    let blob = emptyBlob()
    const a = makeDefaultAtomNode("text_label")
    const b = makeDefaultAtomNode("icon")
    blob = insertAtomAt(blob, "root", 0, a).next
    blob = insertAtomAt(blob, "root", 1, b).next
    renderCanvas({ blob })
    expect(
      screen.getByTestId("widget-builder-canvas-drop-target-root-0"),
    ).toBeTruthy()
    expect(
      screen.getByTestId("widget-builder-canvas-drop-target-root-1"),
    ).toBeTruthy()
    expect(
      screen.getByTestId("widget-builder-canvas-drop-target-root-2"),
    ).toBeTruthy()
  })

  it("renders a container drop target on container atoms", () => {
    let blob = emptyBlob()
    const cont = makeDefaultAtomNode("conditional_container")
    blob = insertAtomAt(blob, "root", 0, cont).next
    renderCanvas({ blob })
    expect(
      screen.getByTestId(
        `widget-builder-canvas-container-drop-${cont.atom_id}`,
      ),
    ).toBeTruthy()
  })

  it("renders ComposedWidget for the WYSIWYG preview", () => {
    renderCanvas({ blob: emptyBlob() })
    expect(screen.getByTestId("widget-builder-canvas-render")).toBeTruthy()
  })

  it("click on atom calls onSelect with atom_id; click on canvas clears", () => {
    let blob = emptyBlob()
    const a = makeDefaultAtomNode("text_label")
    blob = insertAtomAt(blob, "root", 0, a).next
    const onSelect = vi.fn()
    renderCanvas({ blob, onSelect })
    const atomEl = screen.getByTestId(`widget-builder-canvas-atom-${a.atom_id}`)
    fireEvent.click(atomEl)
    expect(onSelect).toHaveBeenCalledWith(a.atom_id)
    fireEvent.click(screen.getByTestId("widget-builder-canvas"))
    expect(onSelect).toHaveBeenCalledWith(null)
  })

  it("applies selection chrome to the selected atom", () => {
    let blob = emptyBlob()
    const a = makeDefaultAtomNode("text_label")
    blob = insertAtomAt(blob, "root", 0, a).next
    renderCanvas({ blob, selectedAtomId: a.atom_id })
    const el = screen.getByTestId(`widget-builder-canvas-atom-${a.atom_id}`)
    expect(el.getAttribute("data-selected")).toBe("true")
  })
})

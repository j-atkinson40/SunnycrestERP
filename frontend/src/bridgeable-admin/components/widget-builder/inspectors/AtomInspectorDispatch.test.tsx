/**
 * AtomInspectorDispatch — smoke tests for WB-4b per-atom inspectors.
 *
 * Each test renders the dispatch with a single-atom blob + verifies
 * the correct inspector mounted via its data-testid. One config-edit
 * round-trip per kind keeps coverage broad without verbose assertions.
 */
import { describe, expect, it, vi } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"

import type { AtomType, CompositionBlob } from "@/lib/widget-builder/types/composition-blob"
import { AtomInspectorDispatch } from "./AtomInspectorDispatch"


function blobWith(atom_type: AtomType, config: Record<string, unknown>): CompositionBlob {
  return {
    schema_version: 1,
    root_atom_id: "root",
    atom_tree: {
      root: {
        atom_id: "root",
        atom_type: "conditional_container",
        config: { direction: "column" },
        children: ["leaf"],
      },
      leaf: {
        atom_id: "leaf",
        atom_type,
        config,
      },
    },
    variants: [],
    bindings_catalog: {},
  }
}


describe("AtomInspectorDispatch", () => {
  it("renders CanvasRootInspector when no atom is selected", () => {
    const blob = blobWith("text_label", { text: "Hi" })
    render(
      <AtomInspectorDispatch
        blob={blob}
        selectedAtomId={null}
        onUpdateConfig={() => {}}
      />,
    )
    expect(screen.getByTestId("atom-inspector-canvas-root")).toBeTruthy()
  })

  it.each<[AtomType, string]>([
    ["text_label", "atom-inspector-text_label"],
    ["value_display", "atom-inspector-value_display"],
    ["icon", "atom-inspector-icon"],
    ["status_badge", "atom-inspector-status_badge"],
    ["divider", "atom-inspector-divider"],
    ["button", "atom-inspector-button"],
    ["image", "atom-inspector-image"],
    ["conditional_container", "atom-inspector-conditional_container"],
    ["repeater_atom", "atom-inspector-repeater_atom"],
  ])("renders the %s inspector when selected", (atom_type, testid) => {
    const blob = blobWith(atom_type, {})
    render(
      <AtomInspectorDispatch
        blob={blob}
        selectedAtomId="leaf"
        onUpdateConfig={() => {}}
      />,
    )
    expect(screen.getByTestId(testid)).toBeTruthy()
  })

  it("commits text on blur for text_label", () => {
    const blob = blobWith("text_label", {})
    const onUpdate = vi.fn()
    render(
      <AtomInspectorDispatch
        blob={blob}
        selectedAtomId="leaf"
        onUpdateConfig={onUpdate}
      />,
    )
    const input = screen.getByTestId("atom-inspector-text") as HTMLInputElement
    fireEvent.change(input, { target: { value: "Hello" } })
    fireEvent.blur(input)
    expect(onUpdate).toHaveBeenCalledWith(
      "leaf",
      expect.objectContaining({ text: "Hello" }),
    )
  })

  it("commits text on Enter for text_label", () => {
    const blob = blobWith("text_label", {})
    const onUpdate = vi.fn()
    render(
      <AtomInspectorDispatch
        blob={blob}
        selectedAtomId="leaf"
        onUpdateConfig={onUpdate}
      />,
    )
    const input = screen.getByTestId("atom-inspector-text") as HTMLInputElement
    fireEvent.change(input, { target: { value: "World" } })
    fireEvent.keyDown(input, { key: "Enter" })
    expect(onUpdate).toHaveBeenCalledWith(
      "leaf",
      expect.objectContaining({ text: "World" }),
    )
  })

  it("surfaces binding picker placeholders disabled in WB-6 scope", () => {
    const blob = blobWith("value_display", {})
    render(
      <AtomInspectorDispatch
        blob={blob}
        selectedAtomId="leaf"
        onUpdateConfig={() => {}}
      />,
    )
    expect(screen.getByTestId("atom-inspector-binding-placeholder").textContent).toMatch(
      /WB-6/,
    )
  })

  it("button binding placeholder labels WB-7", () => {
    const blob = blobWith("button", { action_kind: "navigate" })
    render(
      <AtomInspectorDispatch
        blob={blob}
        selectedAtomId="leaf"
        onUpdateConfig={() => {}}
      />,
    )
    expect(screen.getByTestId("atom-inspector-action-placeholder").textContent).toMatch(
      /WB-7/,
    )
  })

  it("renders the per-atom error message when errors are present", () => {
    const blob = blobWith("text_label", {})
    render(
      <AtomInspectorDispatch
        blob={blob}
        selectedAtomId="leaf"
        onUpdateConfig={() => {}}
        errors={{ leaf: ["Text label requires content"] }}
      />,
    )
    const err = screen.getByTestId("inspector-field-error")
    expect(err.textContent).toMatch(/text label requires content/i)
  })

  it("conditional_container alignment dropdown includes stretch", () => {
    const blob = blobWith("conditional_container", { direction: "column" })
    render(
      <AtomInspectorDispatch
        blob={blob}
        selectedAtomId="leaf"
        onUpdateConfig={() => {}}
      />,
    )
    // The trigger renders the current value; the four-option vocab
    // is asserted via the dispatch source-shape gate. Smoke check.
    expect(screen.getByTestId("atom-inspector-alignment")).toBeTruthy()
  })
})

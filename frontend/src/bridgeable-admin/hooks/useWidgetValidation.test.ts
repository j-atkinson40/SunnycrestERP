/**
 * useWidgetValidation tests — WB-4b client-side composition validator.
 *
 * Covers each atom kind's required-field rule plus the no-errors
 * baseline. Parity with the backend strict validator is exercised
 * indirectly through the source-shape gates that pin the field names.
 */
import { describe, it, expect } from "vitest"

import type { CompositionBlob } from "@/lib/widget-builder/types/composition-blob"
import { validateCompositionBlob } from "./useWidgetValidation"


function blobWith(atom_type: string, config: Record<string, unknown>): CompositionBlob {
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
        atom_type: atom_type as never,
        config,
      },
    },
    variants: [],
    bindings_catalog: {},
  }
}


describe("useWidgetValidation — composition-blob client-side validator", () => {
  it("text_label without text or binding raises an error", () => {
    const blob = blobWith("text_label", {})
    const r = validateCompositionBlob(blob)
    expect(r.hasErrors).toBe(true)
    expect(r.errorsByAtom.leaf.length).toBeGreaterThan(0)
  })

  it("text_label with static text is clean", () => {
    const blob = blobWith("text_label", { text: "Hi" })
    const r = validateCompositionBlob(blob)
    expect(r.hasErrors).toBe(false)
  })

  it("button without label raises an error", () => {
    const blob = blobWith("button", { action_kind: "navigate" })
    const r = validateCompositionBlob(blob)
    expect(r.hasErrors).toBe(true)
    expect(r.errorsByAtom.leaf[0]).toMatch(/label/i)
  })

  it("image without alt raises an error", () => {
    const blob = blobWith("image", { src: "x" })
    const r = validateCompositionBlob(blob)
    expect(r.hasErrors).toBe(true)
    expect(r.errorsByAtom.leaf[0]).toMatch(/alt/i)
  })

  it("status_badge without label raises an error", () => {
    const blob = blobWith("status_badge", {})
    const r = validateCompositionBlob(blob)
    expect(r.hasErrors).toBe(true)
  })

  it("icon without icon_name raises an error", () => {
    const blob = blobWith("icon", {})
    const r = validateCompositionBlob(blob)
    expect(r.hasErrors).toBe(true)
    expect(r.errorsByAtom.leaf[0]).toMatch(/icon_name/i)
  })

  it("value_display without binding raises an error", () => {
    const blob = blobWith("value_display", { format: "number" })
    const r = validateCompositionBlob(blob)
    expect(r.hasErrors).toBe(true)
  })

  it("repeater without binding_id raises an error", () => {
    const blob = blobWith("repeater_atom", {
      children: [],
      binding_id: "",
    })
    const r = validateCompositionBlob(blob)
    expect(r.hasErrors).toBe(true)
  })

  it("baseline (root only) is clean", () => {
    const blob: CompositionBlob = {
      schema_version: 1,
      root_atom_id: "root",
      atom_tree: {
        root: {
          atom_id: "root",
          atom_type: "conditional_container",
          config: { direction: "column" },
          children: [],
        },
      },
      variants: [],
      bindings_catalog: {},
    }
    const r = validateCompositionBlob(blob)
    expect(r.hasErrors).toBe(false)
    expect(r.errorList).toHaveLength(0)
  })

  it("null blob is clean", () => {
    const r = validateCompositionBlob(null)
    expect(r.hasErrors).toBe(false)
  })

  it("errorList includes atom_type for each entry", () => {
    const blob = blobWith("text_label", {})
    const r = validateCompositionBlob(blob)
    expect(r.errorList[0].atom_type).toBe("text_label")
  })

  it("multiple atoms with errors aggregate properly", () => {
    const blob: CompositionBlob = {
      schema_version: 1,
      root_atom_id: "root",
      atom_tree: {
        root: {
          atom_id: "root",
          atom_type: "conditional_container",
          config: {},
          children: ["a", "b"],
        },
        a: { atom_id: "a", atom_type: "text_label", config: {} },
        b: { atom_id: "b", atom_type: "button", config: {} },
      },
      variants: [],
      bindings_catalog: {},
    }
    const r = validateCompositionBlob(blob)
    expect(r.errorList.length).toBe(2)
    expect(Object.keys(r.errorsByAtom).sort()).toEqual(["a", "b"])
  })
})

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


describe("useWidgetValidation — WB-6 bidirectional binding-shape checks", () => {
  it("rejects literal binding carrying iteration_mode (Check 4)", () => {
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
      bindings_catalog: {
        b1: {
          binding_id: "b1",
          binding_type: "literal",
          literal_value: "X",
          iteration_mode: "single_record",
        },
      },
    }
    const r = validateCompositionBlob(blob)
    expect(r.hasErrors).toBe(true)
    expect(
      r.errorList.some((e) => e.message.includes("cannot carry iteration_mode")),
    ).toBe(true)
  })

  it("rejects field_path binding missing iteration_mode (Check 5)", () => {
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
      bindings_catalog: {
        b1: {
          binding_id: "b1",
          binding_type: "field_path",
          saved_view_id: "sv1",
          field_path: "x",
        },
      },
    }
    const r = validateCompositionBlob(blob)
    expect(
      r.errorList.some((e) => e.message.includes("needs an iteration mode")),
    ).toBe(true)
  })

  it("rejects field_path binding missing saved_view_id (Check 5)", () => {
    const blob: CompositionBlob = {
      schema_version: 1,
      root_atom_id: "root",
      atom_tree: {
        root: {
          atom_id: "root",
          atom_type: "conditional_container",
          config: {},
          children: [],
        },
      },
      variants: [],
      bindings_catalog: {
        b1: {
          binding_id: "b1",
          binding_type: "field_path",
          field_path: "x",
          iteration_mode: "single_record",
        },
      },
    }
    const r = validateCompositionBlob(blob)
    expect(
      r.errorList.some((e) => e.message.includes("needs a saved view")),
    ).toBe(true)
  })

  it("rejects leaf atom with per_row binding (Check 3)", () => {
    const blob: CompositionBlob = {
      schema_version: 1,
      root_atom_id: "root",
      atom_tree: {
        root: {
          atom_id: "root",
          atom_type: "conditional_container",
          config: {},
          children: ["v"],
        },
        v: {
          atom_id: "v",
          atom_type: "value_display",
          config: { format: "currency" },
          binding_refs: { value: "b1" },
        },
      },
      variants: [],
      bindings_catalog: {
        b1: {
          binding_id: "b1",
          binding_type: "field_path",
          saved_view_id: "sv1",
          field_path: "x",
          iteration_mode: "per_row",
        },
      },
    }
    const r = validateCompositionBlob(blob)
    expect(r.errorsByAtom["v"]).toBeDefined()
    expect(
      r.errorsByAtom["v"].some((m) => m.includes("per_row")),
    ).toBe(true)
  })

  it("flags orphan per_row binding not consumed by a repeater (Check 2)", () => {
    const blob: CompositionBlob = {
      schema_version: 1,
      root_atom_id: "root",
      atom_tree: {
        root: {
          atom_id: "root",
          atom_type: "conditional_container",
          config: {},
          children: [],
        },
      },
      variants: [],
      bindings_catalog: {
        b1: {
          binding_id: "b1",
          binding_type: "field_path",
          saved_view_id: "sv1",
          field_path: "x",
          iteration_mode: "per_row",
        },
      },
    }
    const r = validateCompositionBlob(blob)
    expect(
      r.errorList.some((e) =>
        e.message.includes("must be consumed by a repeater"),
      ),
    ).toBe(true)
  })

  it("accepts a well-formed value_display + single_record binding", () => {
    const blob: CompositionBlob = {
      schema_version: 1,
      root_atom_id: "root",
      atom_tree: {
        root: {
          atom_id: "root",
          atom_type: "conditional_container",
          config: {},
          children: ["v"],
        },
        v: {
          atom_id: "v",
          atom_type: "value_display",
          config: { format: "currency", format_config: { currency_code: "USD" } },
          binding_refs: { value: "b1" },
        },
      },
      variants: [],
      bindings_catalog: {
        b1: {
          binding_id: "b1",
          binding_type: "field_path",
          saved_view_id: "sv1",
          field_path: "amount",
          iteration_mode: "single_record",
        },
      },
    }
    const r = validateCompositionBlob(blob)
    expect(r.hasErrors).toBe(false)
  })
})

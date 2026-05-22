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


// ── WB-7 ActionRef mirrors ─────────────────────────────────────────


function blobWithButtonAction(action: Record<string, unknown>): CompositionBlob {
  return {
    schema_version: 1,
    root_atom_id: "root",
    atom_tree: {
      root: {
        atom_id: "root",
        atom_type: "conditional_container",
        config: { direction: "column" },
        children: ["btn"],
      },
      btn: {
        atom_id: "btn",
        atom_type: "button",
        config: { label: "X", action_kind: "navigate", action_config: {}, action },
      },
    },
    variants: [],
    bindings_catalog: {},
  }
}


function blobWithRepeaterButton(action: Record<string, unknown>): CompositionBlob {
  return {
    schema_version: 1,
    root_atom_id: "root",
    atom_tree: {
      root: {
        atom_id: "root",
        atom_type: "conditional_container",
        config: { direction: "column" },
        children: ["rep"],
      },
      rep: {
        atom_id: "rep",
        atom_type: "repeater_atom",
        config: { binding_id: "rows", children: ["btn"] },
        children: ["btn"],
      },
      btn: {
        atom_id: "btn",
        atom_type: "button",
        config: { label: "X", action_kind: "mutate", action_config: {}, action },
      },
    },
    variants: [],
    bindings_catalog: {
      rows: {
        binding_id: "rows",
        binding_type: "field_path",
        saved_view_id: "v",
        field_path: "rows",
        iteration_mode: "per_row",
      },
    },
  }
}


describe("useWidgetValidation — WB-7 ActionRef structural mirrors", () => {
  it("navigate missing href is flagged", () => {
    const r = validateCompositionBlob(
      blobWithButtonAction({ action_kind: "navigate", href: "" }),
    )
    expect(r.hasErrors).toBe(true)
    expect(r.errorsByAtom.btn.join(" ")).toMatch(/href/)
  })
  it("open_focus missing slug is flagged", () => {
    const r = validateCompositionBlob(
      blobWithButtonAction({ action_kind: "open_focus", focus_template_slug: "" }),
    )
    expect(r.hasErrors).toBe(true)
    expect(r.errorsByAtom.btn.join(" ")).toMatch(/focus_template_slug/)
  })
  it("trigger_workflow missing slug is flagged", () => {
    const r = validateCompositionBlob(
      blobWithButtonAction({
        action_kind: "trigger_workflow",
        workflow_slug: "",
      }),
    )
    expect(r.hasErrors).toBe(true)
    expect(r.errorsByAtom.btn.join(" ")).toMatch(/workflow_slug/)
  })
  it("mutate with disallowed kind is flagged", () => {
    const r = validateCompositionBlob(
      blobWithRepeaterButton({
        action_kind: "mutate",
        mutate_kind: "delete_row",
        target_id_binding: {
          name: "id",
          source: "current_row",
          row_field: "id",
        },
      }),
    )
    expect(r.hasErrors).toBe(true)
    expect(r.errorsByAtom.btn.join(" ")).toMatch(/anomaly_acknowledge/)
  })
  it("mutate without target_id_binding is flagged", () => {
    const r = validateCompositionBlob(
      blobWithRepeaterButton({
        action_kind: "mutate",
        mutate_kind: "anomaly_acknowledge",
      }),
    )
    expect(r.hasErrors).toBe(true)
    expect(r.errorsByAtom.btn.join(" ")).toMatch(/target_id_binding/)
  })
  it("valid mutate inside repeater is clean", () => {
    const r = validateCompositionBlob(
      blobWithRepeaterButton({
        action_kind: "mutate",
        mutate_kind: "anomaly_acknowledge",
        target_id_binding: {
          name: "id",
          source: "current_row",
          row_field: "id",
        },
      }),
    )
    // The mutate-related errors are clean — the button label
    // assertion shouldn't fail because we set label="X".
    const btnErrs = r.errorsByAtom.btn ?? []
    expect(btnErrs.join(" ")).not.toMatch(/mutate/)
    expect(btnErrs.join(" ")).not.toMatch(/target_id_binding/)
  })
  it("current_row binding outside repeater is flagged", () => {
    const r = validateCompositionBlob(
      blobWithButtonAction({
        action_kind: "open_peek",
        peek_view_type: "fh_case",
        initial_context: [
          {
            name: "entity_id",
            source: "current_row",
            row_field: "id",
          },
        ],
      }),
    )
    expect(r.hasErrors).toBe(true)
    expect(r.errorsByAtom.btn.join(" ")).toMatch(/current_row/i)
    expect(r.errorsByAtom.btn.join(" ")).toMatch(/not inside a repeater/i)
  })
  it("current_row binding inside repeater is clean", () => {
    const r = validateCompositionBlob(
      blobWithRepeaterButton({
        action_kind: "open_peek",
        peek_view_type: "fh_case",
        initial_context: [
          {
            name: "entity_id",
            source: "current_row",
            row_field: "id",
          },
        ],
      }),
    )
    const btnErrs = r.errorsByAtom.btn ?? []
    expect(btnErrs.join(" ")).not.toMatch(/current_row/)
  })

  // ── WB-8 variant validation ────────────────────────────────────────

  it("default_variant_id referencing unknown variant surfaces a variantError", () => {
    const blob = blobWith("text_label", { text: "x" })
    blob.variants = [
      {
        variant_id: "brief",
        variant_name: "Brief",
        target_surface: "focus_canvas",
      },
    ]
    blob.default_variant_id = "detail"
    const r = validateCompositionBlob(blob)
    expect(r.variantErrors.length).toBe(1)
    expect(r.hasErrors).toBe(true)
  })

  it("default_variant_id referencing declared variant is clean", () => {
    const blob = blobWith("text_label", { text: "x" })
    blob.variants = [
      {
        variant_id: "brief",
        variant_name: "Brief",
        target_surface: "focus_canvas",
      },
    ]
    blob.default_variant_id = "brief"
    const r = validateCompositionBlob(blob)
    expect(r.variantErrors).toEqual([])
  })

  it("target_surface mismatch surfaces a variantWarning (NOT blocking)", () => {
    const blob = blobWith("text_label", { text: "x" })
    blob.variants = [
      {
        variant_id: "brief",
        variant_name: "Brief",
        target_surface: "focus_canvas",
      },
    ]
    const r = validateCompositionBlob(blob, ["dashboard_grid"])
    expect(r.variantWarnings.brief?.length).toBeGreaterThan(0)
    // Pure mismatch is NOT blocking at draft.
    expect(r.variantErrors).toEqual([])
  })

  it("spaces_pin without Glance variant raises blocking variantError (Lock 3a.2)", () => {
    const blob = blobWith("text_label", { text: "x" })
    blob.variants = [
      {
        variant_id: "brief",
        variant_name: "Brief",
        target_surface: "focus_canvas",
      },
    ]
    const r = validateCompositionBlob(blob, ["spaces_pin", "focus_canvas"])
    expect(r.variantErrors.some((e) => /Glance/.test(e))).toBe(true)
    expect(r.hasErrors).toBe(true)
  })

  it("focus_canvas without Brief variant raises blocking variantError (Lock 3a.3)", () => {
    const blob = blobWith("text_label", { text: "x" })
    blob.variants = [
      {
        variant_id: "detail",
        variant_name: "Detail",
        target_surface: "focus_canvas",
      },
    ]
    const r = validateCompositionBlob(blob, ["focus_canvas"])
    expect(r.variantErrors.some((e) => /Brief/.test(e))).toBe(true)
  })

  it("focus_canvas with empty variants[] does NOT trigger Lock 3a.3 (graceful)", () => {
    const blob = blobWith("text_label", { text: "x" })
    const r = validateCompositionBlob(blob, ["focus_canvas"])
    expect(r.variantErrors).toEqual([])
  })

  it("backward-compat: no supportedSurfaces arg, no variant warnings emitted", () => {
    const blob = blobWith("text_label", { text: "x" })
    blob.variants = [
      {
        variant_id: "brief",
        variant_name: "Brief",
        target_surface: "focus_canvas",
      },
    ]
    const r = validateCompositionBlob(blob)
    expect(r.variantWarnings).toEqual({})
    expect(r.variantErrors).toEqual([])
  })

  it("validation result always exposes WB-8 fields (even on null blob)", () => {
    const r = validateCompositionBlob(null)
    expect(r.variantWarnings).toEqual({})
    expect(r.variantErrors).toEqual([])
  })
})

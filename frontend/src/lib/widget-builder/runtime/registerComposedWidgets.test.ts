/**
 * registerComposedWidgets — WB-8 resolution-chain unit tests.
 *
 * Covers:
 *   • resolveEffectiveVariantId picks default_variant_id first.
 *   • Falls through to variants[0].variant_id when default absent.
 *   • Falls through to undefined when variants[] is empty.
 *   • Backward-compat: widgets without variants[] / without
 *     default_variant_id resolve to undefined ("all atoms").
 *   • Non-object / null blob → undefined (defensive).
 */
import { describe, it, expect } from "vitest"

import { resolveEffectiveVariantId } from "./registerComposedWidgets"


describe("WB-8 resolveEffectiveVariantId resolution chain", () => {
  it("returns default_variant_id when set", () => {
    const blob = {
      schema_version: 1,
      root_atom_id: "root",
      atom_tree: {},
      bindings_catalog: {},
      variants: [
        {
          variant_id: "brief",
          variant_name: "Brief",
          target_surface: "focus_canvas",
        },
        {
          variant_id: "detail",
          variant_name: "Detail",
          target_surface: "focus_canvas",
        },
      ],
      default_variant_id: "detail",
    }
    expect(resolveEffectiveVariantId(blob)).toBe("detail")
  })

  it("falls through to variants[0].variant_id when default absent", () => {
    const blob = {
      schema_version: 1,
      root_atom_id: "root",
      atom_tree: {},
      bindings_catalog: {},
      variants: [
        {
          variant_id: "glance",
          variant_name: "Glance",
          target_surface: "focus_canvas",
        },
        {
          variant_id: "brief",
          variant_name: "Brief",
          target_surface: "focus_canvas",
        },
      ],
    }
    expect(resolveEffectiveVariantId(blob)).toBe("glance")
  })

  it("returns undefined when variants[] is empty", () => {
    const blob = {
      schema_version: 1,
      root_atom_id: "root",
      atom_tree: {},
      bindings_catalog: {},
      variants: [],
    }
    expect(resolveEffectiveVariantId(blob)).toBeUndefined()
  })

  it("backward-compat: blob lacking variants field resolves to undefined", () => {
    const blob = {
      schema_version: 1,
      root_atom_id: "root",
      atom_tree: {},
      bindings_catalog: {},
    }
    expect(resolveEffectiveVariantId(blob)).toBeUndefined()
  })

  it("backward-compat: blob lacking default_variant_id resolves via variants[0]", () => {
    const blob = {
      variants: [
        {
          variant_id: "deep",
          variant_name: "Deep",
          target_surface: "focus_canvas",
        },
      ],
    }
    expect(resolveEffectiveVariantId(blob)).toBe("deep")
  })

  it("null blob → undefined (defensive)", () => {
    expect(resolveEffectiveVariantId(null)).toBeUndefined()
  })

  it("non-object blob → undefined", () => {
    expect(resolveEffectiveVariantId("not-an-object")).toBeUndefined()
    expect(resolveEffectiveVariantId(42)).toBeUndefined()
  })

  it("default_variant_id empty string falls through to variants[0]", () => {
    const blob = {
      variants: [
        {
          variant_id: "brief",
          variant_name: "Brief",
          target_surface: "focus_canvas",
        },
      ],
      default_variant_id: "",
    }
    expect(resolveEffectiveVariantId(blob)).toBe("brief")
  })
})

/**
 * useVariantAuthoring tests — WB-8 variant CRUD operations.
 *
 * Operator-observable assertion canon: tests assert on the resulting
 * draft payload shape that flows into setDraft, not on hook internals.
 */
import { renderHook, act } from "@testing-library/react"
import { describe, it, expect, vi } from "vitest"

import type { CompositionBlob } from "@/lib/widget-builder/types/composition-blob"
import { useVariantAuthoring } from "./useVariantAuthoring"


function mkBlob(): CompositionBlob {
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
        atom_type: "text_label",
        config: { text: "hi" },
      },
    },
    variants: [],
    bindings_catalog: {},
  }
}


describe("useVariantAuthoring", () => {
  it("declareVariant appends a new variant with canonical name + focus_canvas default", () => {
    const blob = mkBlob()
    const setDraft = vi.fn()
    const { result } = renderHook(() => useVariantAuthoring(blob, setDraft))
    act(() => result.current.declareVariant("brief"))
    const next = setDraft.mock.calls[0][0] as CompositionBlob
    expect(next.variants).toEqual([
      {
        variant_id: "brief",
        variant_name: "Brief",
        target_surface: "focus_canvas",
      },
    ])
  })

  it("declareVariant is idempotent (no double-declare)", () => {
    const blob = mkBlob()
    blob.variants = [
      {
        variant_id: "brief",
        variant_name: "Brief",
        target_surface: "focus_canvas",
      },
    ]
    const setDraft = vi.fn()
    const { result } = renderHook(() => useVariantAuthoring(blob, setDraft))
    act(() => result.current.declareVariant("brief"))
    expect(setDraft).not.toHaveBeenCalled()
  })

  it("renameVariant updates only the matching variant_name", () => {
    const blob = mkBlob()
    blob.variants = [
      {
        variant_id: "brief",
        variant_name: "Brief",
        target_surface: "focus_canvas",
      },
    ]
    const setDraft = vi.fn()
    const { result } = renderHook(() => useVariantAuthoring(blob, setDraft))
    act(() => result.current.renameVariant("brief", "Quick view"))
    const next = setDraft.mock.calls[0][0] as CompositionBlob
    expect(next.variants[0].variant_name).toBe("Quick view")
    expect(next.variants[0].variant_id).toBe("brief")
  })

  it("setTargetSurface updates the matching variant", () => {
    const blob = mkBlob()
    blob.variants = [
      {
        variant_id: "brief",
        variant_name: "Brief",
        target_surface: "focus_canvas",
      },
    ]
    const setDraft = vi.fn()
    const { result } = renderHook(() => useVariantAuthoring(blob, setDraft))
    act(() => result.current.setTargetSurface("brief", "page_canvas"))
    const next = setDraft.mock.calls[0][0] as CompositionBlob
    expect(next.variants[0].target_surface).toBe("page_canvas")
  })

  it("setCanonicalDimensions writes width/height; null removes the field", () => {
    const blob = mkBlob()
    blob.variants = [
      {
        variant_id: "brief",
        variant_name: "Brief",
        target_surface: "focus_canvas",
      },
    ]
    const setDraft = vi.fn()
    const { result, rerender } = renderHook(
      ({ b }) => useVariantAuthoring(b, setDraft),
      { initialProps: { b: blob } },
    )
    act(() =>
      result.current.setCanonicalDimensions("brief", { width: 320, height: 200 }),
    )
    let next = setDraft.mock.calls[0][0] as CompositionBlob
    expect(next.variants[0].canonical_dimensions).toEqual({
      width: 320,
      height: 200,
    })
    rerender({ b: next })
    act(() => result.current.setCanonicalDimensions("brief", null))
    next = setDraft.mock.calls[1][0] as CompositionBlob
    expect(next.variants[0].canonical_dimensions).toBeUndefined()
  })

  it("setDefaultVariantId only accepts declared variant_ids", () => {
    const blob = mkBlob()
    blob.variants = [
      {
        variant_id: "brief",
        variant_name: "Brief",
        target_surface: "focus_canvas",
      },
    ]
    const setDraft = vi.fn()
    const { result } = renderHook(() => useVariantAuthoring(blob, setDraft))
    // Unknown variant → no-op.
    act(() => result.current.setDefaultVariantId("detail"))
    expect(setDraft).not.toHaveBeenCalled()
    // Declared variant → setDraft fires.
    act(() => result.current.setDefaultVariantId("brief"))
    const next = setDraft.mock.calls[0][0] as CompositionBlob
    expect(next.default_variant_id).toBe("brief")
  })

  it("setDefaultVariantId(null) clears the field", () => {
    const blob = mkBlob()
    blob.variants = [
      {
        variant_id: "brief",
        variant_name: "Brief",
        target_surface: "focus_canvas",
      },
    ]
    blob.default_variant_id = "brief"
    const setDraft = vi.fn()
    const { result } = renderHook(() => useVariantAuthoring(blob, setDraft))
    act(() => result.current.setDefaultVariantId(null))
    const next = setDraft.mock.calls[0][0] as CompositionBlob
    expect(next.default_variant_id).toBeUndefined()
  })

  it("removeVariant blocks deletion of current default", () => {
    const blob = mkBlob()
    blob.variants = [
      {
        variant_id: "brief",
        variant_name: "Brief",
        target_surface: "focus_canvas",
      },
    ]
    blob.default_variant_id = "brief"
    const setDraft = vi.fn()
    const { result } = renderHook(() => useVariantAuthoring(blob, setDraft))
    act(() => result.current.removeVariant("brief"))
    expect(setDraft).not.toHaveBeenCalled()
  })

  it("removeVariant cascade-cleans atom.visible_in_variants references", () => {
    const blob = mkBlob()
    blob.variants = [
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
    ]
    blob.atom_tree.leaf.visible_in_variants = ["brief", "detail"]
    const setDraft = vi.fn()
    const { result } = renderHook(() => useVariantAuthoring(blob, setDraft))
    act(() => result.current.removeVariant("detail"))
    const next = setDraft.mock.calls[0][0] as CompositionBlob
    expect(next.variants.map((v) => v.variant_id)).toEqual(["brief"])
    expect(next.atom_tree.leaf.visible_in_variants).toEqual(["brief"])
  })

  it("removeVariant drops visible_in_variants when last reference removed", () => {
    const blob = mkBlob()
    blob.variants = [
      {
        variant_id: "detail",
        variant_name: "Detail",
        target_surface: "focus_canvas",
      },
    ]
    blob.atom_tree.leaf.visible_in_variants = ["detail"]
    const setDraft = vi.fn()
    const { result } = renderHook(() => useVariantAuthoring(blob, setDraft))
    act(() => result.current.removeVariant("detail"))
    const next = setDraft.mock.calls[0][0] as CompositionBlob
    expect(next.atom_tree.leaf.visible_in_variants).toBeUndefined()
  })

  it("toggleAtomVariantVisibility adds/removes; empty drops field", () => {
    const blob = mkBlob()
    blob.variants = [
      {
        variant_id: "brief",
        variant_name: "Brief",
        target_surface: "focus_canvas",
      },
    ]
    const setDraft = vi.fn()
    const { result, rerender } = renderHook(
      ({ b }) => useVariantAuthoring(b, setDraft),
      { initialProps: { b: blob } },
    )
    act(() => result.current.toggleAtomVariantVisibility("leaf", "brief"))
    let next = setDraft.mock.calls[0][0] as CompositionBlob
    expect(next.atom_tree.leaf.visible_in_variants).toEqual(["brief"])
    rerender({ b: next })
    act(() => result.current.toggleAtomVariantVisibility("leaf", "brief"))
    next = setDraft.mock.calls[1][0] as CompositionBlob
    expect(next.atom_tree.leaf.visible_in_variants).toBeUndefined()
  })

  it("reorderVariant moves a variant within the list", () => {
    const blob = mkBlob()
    blob.variants = [
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
      {
        variant_id: "detail",
        variant_name: "Detail",
        target_surface: "focus_canvas",
      },
    ]
    const setDraft = vi.fn()
    const { result } = renderHook(() => useVariantAuthoring(blob, setDraft))
    act(() => result.current.reorderVariant("glance", 2))
    const next = setDraft.mock.calls[0][0] as CompositionBlob
    expect(next.variants.map((v) => v.variant_id)).toEqual([
      "brief",
      "detail",
      "glance",
    ])
  })

  it("setCurrentVariantId switches the previewed variant", () => {
    const { result } = renderHook(() =>
      useVariantAuthoring(mkBlob(), vi.fn()),
    )
    expect(result.current.currentVariantId).toBeUndefined()
    act(() => result.current.setCurrentVariantId("brief"))
    expect(result.current.currentVariantId).toBe("brief")
    act(() => result.current.setCurrentVariantId(undefined))
    expect(result.current.currentVariantId).toBeUndefined()
  })
})

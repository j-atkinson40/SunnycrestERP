/**
 * resolveBinding tests — WB-6 substantiated behavior + WB-2 backward
 * compat for literals.
 *
 * Phase 1 (WB-2) placeholder string behavior for field_path bindings
 * has been replaced with real resolution. Literal binding_type
 * behavior is UNCHANGED (backward-compat per Area 4 lock).
 */

import { describe, it, expect } from "vitest"

import type { BindingRef } from "../types/composition-blob"
import {
  parseFieldPath,
  resolveBinding,
  walkFieldPath,
} from "./resolveBinding"


describe("resolveBinding — literal binding_type (backward-compat WB-2)", () => {
  it("returns literal_value for string", () => {
    const ref: BindingRef = {
      binding_id: "b1",
      binding_type: "literal",
      literal_value: "Hello",
    }
    expect(resolveBinding(ref)).toBe("Hello")
  })

  it("returns literal_value for number", () => {
    const ref: BindingRef = {
      binding_id: "b1",
      binding_type: "literal",
      literal_value: 42,
    }
    expect(resolveBinding(ref)).toBe(42)
  })

  it("returns undefined for unset literal_value", () => {
    const ref: BindingRef = { binding_id: "b1", binding_type: "literal" }
    expect(resolveBinding(ref)).toBeUndefined()
  })

  it("ignores dataContext for literal bindings", () => {
    const ref: BindingRef = {
      binding_id: "b1",
      binding_type: "literal",
      literal_value: "x",
    }
    expect(
      resolveBinding(ref, { __row: true, __index: 0, case: { name: "Smith" } }),
    ).toBe("x")
  })

  it("throws on unknown binding_type (defense-in-depth)", () => {
    const ref = {
      binding_id: "b4",
      binding_type: "expression",
    } as unknown as BindingRef
    expect(() => resolveBinding(ref)).toThrow(/unknown binding_type/)
  })
})


describe("parseFieldPath", () => {
  it("splits a dotted path into segments", () => {
    expect(parseFieldPath("a.b.c")).toEqual(["a", "b", "c"])
  })

  it("handles single-segment paths", () => {
    expect(parseFieldPath("name")).toEqual(["name"])
  })

  it("handles numeric segments", () => {
    expect(parseFieldPath("items.0.name")).toEqual(["items", "0", "name"])
  })

  it("throws on empty string", () => {
    expect(() => parseFieldPath("")).toThrow(/empty string/)
  })

  it("throws on leading dot", () => {
    expect(() => parseFieldPath(".a")).toThrow(/leading\/trailing dot/)
  })

  it("throws on trailing dot", () => {
    expect(() => parseFieldPath("a.")).toThrow(/leading\/trailing dot/)
  })

  it("throws on consecutive dots", () => {
    expect(() => parseFieldPath("a..b")).toThrow(/consecutive dots/)
  })
})


describe("walkFieldPath", () => {
  it("returns top-level value", () => {
    expect(walkFieldPath({ name: "Smith" }, ["name"])).toBe("Smith")
  })

  it("walks nested object", () => {
    expect(walkFieldPath({ case: { name: "Smith" } }, ["case", "name"])).toBe(
      "Smith",
    )
  })

  it("indexes into array via numeric segment", () => {
    expect(
      walkFieldPath({ items: [{ name: "A" }, { name: "B" }] }, [
        "items",
        "1",
        "name",
      ]),
    ).toBe("B")
  })

  it("returns null on missing intermediate", () => {
    expect(walkFieldPath({ a: null }, ["a", "b"])).toBeNull()
  })

  it("returns null on missing leaf", () => {
    expect(walkFieldPath({ a: { b: 1 } }, ["a", "c"])).toBeNull()
  })

  it("returns null on array index out of bounds", () => {
    expect(walkFieldPath({ items: [1, 2] }, ["items", "5"])).toBeNull()
  })

  it("returns null when expecting array but got object", () => {
    expect(walkFieldPath({ items: { a: 1 } }, ["items", "0"])).toBeNull()
  })

  it("returns null when target is null at root", () => {
    expect(walkFieldPath(null, ["a"])).toBeNull()
  })
})


describe("resolveBinding — field_path + per_row (WB-6)", () => {
  it("resolves a top-level field against a row context", () => {
    const ref: BindingRef = {
      binding_id: "b1",
      binding_type: "field_path",
      saved_view_id: "sv1",
      field_path: "amount",
      iteration_mode: "per_row",
    }
    const ctx = { __row: true, __index: 0, amount: 1250 }
    expect(resolveBinding(ref, ctx)).toBe(1250)
  })

  it("resolves a nested path against a row context", () => {
    const ref: BindingRef = {
      binding_id: "b1",
      binding_type: "field_path",
      saved_view_id: "sv1",
      field_path: "case.deceased_name",
      iteration_mode: "per_row",
    }
    const ctx = {
      __row: true,
      __index: 0,
      case: { deceased_name: "Smith" },
    }
    expect(resolveBinding(ref, ctx)).toBe("Smith")
  })

  it("indexes into an array via numeric segment", () => {
    const ref: BindingRef = {
      binding_id: "b1",
      binding_type: "field_path",
      saved_view_id: "sv1",
      field_path: "line_items.0.total",
      iteration_mode: "per_row",
    }
    const ctx = {
      __row: true,
      __index: 0,
      line_items: [{ total: 100 }, { total: 200 }],
    }
    expect(resolveBinding(ref, ctx)).toBe(100)
  })

  it("returns null on missing path", () => {
    const ref: BindingRef = {
      binding_id: "b1",
      binding_type: "field_path",
      saved_view_id: "sv1",
      field_path: "missing_field",
      iteration_mode: "per_row",
    }
    const ctx = { __row: true, __index: 0, amount: 1250 }
    expect(resolveBinding(ref, ctx)).toBeNull()
  })

  it("returns null when no per-row dataContext provided", () => {
    const ref: BindingRef = {
      binding_id: "b1",
      binding_type: "field_path",
      saved_view_id: "sv1",
      field_path: "amount",
      iteration_mode: "per_row",
    }
    expect(resolveBinding(ref)).toBeNull()
  })

  it("throws on malformed field_path syntax", () => {
    const ref: BindingRef = {
      binding_id: "b1",
      binding_type: "field_path",
      saved_view_id: "sv1",
      field_path: "a..b",
      iteration_mode: "per_row",
    }
    const ctx = { __row: true, __index: 0 }
    expect(() => resolveBinding(ref, ctx)).toThrow(/malformed field_path/)
  })
})


describe("resolveBinding — field_path + single_record (WB-6)", () => {
  it("resolves against the row dict (caller passes rows[0])", () => {
    const ref: BindingRef = {
      binding_id: "b1",
      binding_type: "field_path",
      saved_view_id: "sv1",
      field_path: "title",
      iteration_mode: "single_record",
    }
    const ctx = { __row: true, __index: 0, title: "First record" }
    expect(resolveBinding(ref, ctx)).toBe("First record")
  })

  it("returns null when no row context", () => {
    const ref: BindingRef = {
      binding_id: "b1",
      binding_type: "field_path",
      saved_view_id: "sv1",
      field_path: "title",
      iteration_mode: "single_record",
    }
    expect(resolveBinding(ref)).toBeNull()
  })
})


describe("resolveBinding — field_path + single_summary (WB-6)", () => {
  it("resolves a top-level aggregation field", () => {
    const ref: BindingRef = {
      binding_id: "b1",
      binding_type: "field_path",
      saved_view_id: "sv1",
      field_path: "value",
      iteration_mode: "single_summary",
    }
    const ctx = {
      __summary: true,
      aggregations: { value: 42, comparison_delta: 5 },
      total_count: 10,
    }
    expect(resolveBinding(ref, ctx)).toBe(42)
  })

  it("resolves the synthetic count shortcut to total_count", () => {
    const ref: BindingRef = {
      binding_id: "b1",
      binding_type: "field_path",
      saved_view_id: "sv1",
      field_path: "count",
      iteration_mode: "single_summary",
    }
    const ctx = { __summary: true, total_count: 17 }
    expect(resolveBinding(ref, ctx)).toBe(17)
  })

  it("resolves an explicit aggregations.* path against the full ctx", () => {
    const ref: BindingRef = {
      binding_id: "b1",
      binding_type: "field_path",
      saved_view_id: "sv1",
      field_path: "aggregations.buckets.0.y",
      iteration_mode: "single_summary",
    }
    const ctx = {
      __summary: true,
      aggregations: { buckets: [{ x: "Jan", y: 12 }, { x: "Feb", y: 18 }] },
    }
    expect(resolveBinding(ref, ctx)).toBe(12)
  })

  it("returns null on missing aggregation path", () => {
    const ref: BindingRef = {
      binding_id: "b1",
      binding_type: "field_path",
      saved_view_id: "sv1",
      field_path: "value",
      iteration_mode: "single_summary",
    }
    const ctx = { __summary: true, aggregations: {} }
    expect(resolveBinding(ref, ctx)).toBeNull()
  })

  it("returns null when no summary context", () => {
    const ref: BindingRef = {
      binding_id: "b1",
      binding_type: "field_path",
      saved_view_id: "sv1",
      field_path: "value",
      iteration_mode: "single_summary",
    }
    expect(resolveBinding(ref)).toBeNull()
  })
})


describe("resolveBinding — per-row context spreading (Area 4c)", () => {
  it("preserves parent dataContext fields when row is spread in", () => {
    // Per Area 4c lock — the rowDict is spread INTO dataContext along
    // with __row + __index. Operator can resolve row fields directly.
    const ref: BindingRef = {
      binding_id: "b1",
      binding_type: "field_path",
      saved_view_id: "sv1",
      field_path: "status",
      iteration_mode: "per_row",
    }
    const ctx = {
      __row: true,
      __index: 2,
      status: "Active",
      id: "row-2",
    }
    expect(resolveBinding(ref, ctx)).toBe("Active")
  })
})


describe("resolveBinding — empty field_path edge case (WB-2 compat)", () => {
  it("returns the placeholder when field_path is unset (draft state)", () => {
    // Strict validator rejects this at Publish, but draft state may
    // surface a field_path binding with no path yet — preserve the
    // legible placeholder for in-flight authoring.
    const ref: BindingRef = {
      binding_id: "b1",
      binding_type: "field_path",
    }
    expect(resolveBinding(ref)).toBe("[bound:<missing>]")
  })
})

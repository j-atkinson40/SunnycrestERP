/**
 * resolveBinding tests — WB-2 placeholder behavior gate.
 *
 * Locks the Phase 1 semantics so WB-6 (real saved-view resolution)
 * can swap the internals without breaking the consumer contract.
 */

import { describe, it, expect } from "vitest"

import type { BindingRef } from "../types/composition-blob"
import { resolveBinding } from "./resolveBinding"

describe("resolveBinding (WB-2)", () => {
  it("returns literal_value for binding_type='literal'", () => {
    const ref: BindingRef = {
      binding_id: "b1",
      binding_type: "literal",
      literal_value: "Hello",
    }
    expect(resolveBinding(ref)).toBe("Hello")
  })

  it("returns literal_value for non-string literals", () => {
    const ref: BindingRef = {
      binding_id: "b1",
      binding_type: "literal",
      literal_value: 42,
    }
    expect(resolveBinding(ref)).toBe(42)
  })

  it("returns literal_value=undefined when not provided", () => {
    const ref: BindingRef = {
      binding_id: "b1",
      binding_type: "literal",
    }
    expect(resolveBinding(ref)).toBeUndefined()
  })

  it("returns placeholder string for binding_type='field_path'", () => {
    const ref: BindingRef = {
      binding_id: "b2",
      binding_type: "field_path",
      saved_view_id: "sv-123",
      field_path: "case.deceased_name",
      iteration_mode: "single_record",
    }
    expect(resolveBinding(ref)).toBe("[bound:case.deceased_name]")
  })

  it("handles field_path missing field_path gracefully", () => {
    const ref: BindingRef = {
      binding_id: "b3",
      binding_type: "field_path",
    }
    expect(resolveBinding(ref)).toBe("[bound:<missing>]")
  })

  it("accepts an optional dataContext without using it (Phase 1)", () => {
    const ref: BindingRef = {
      binding_id: "b1",
      binding_type: "literal",
      literal_value: "x",
    }
    expect(resolveBinding(ref, { row: { case: { name: "Smith" } } })).toBe("x")
  })

  it("throws on malformed BindingRef (unknown binding_type)", () => {
    const ref = {
      binding_id: "b4",
      binding_type: "expression",
    } as unknown as BindingRef
    expect(() => resolveBinding(ref)).toThrow(/unknown binding_type/)
  })
})

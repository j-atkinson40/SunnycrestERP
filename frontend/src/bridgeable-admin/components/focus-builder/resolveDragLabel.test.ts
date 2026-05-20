/**
 * resolveDragLabel unit tests — covers all four drag-id shapes the
 * FocusBuilderPage DndContext sees, per the 2026-05-20 investigation
 * Finding 2 (UUID leak class-fix).
 */
import { describe, expect, it } from "vitest"

import { resolveDragLabel } from "./resolveDragLabel"

describe("resolveDragLabel", () => {
  it("palette widget id returns the slug suffix", () => {
    expect(resolveDragLabel("palette-widget:today-pin-widget")).toBe(
      "today-pin-widget",
    )
  })

  it("palette widget id with a multi-segment slug returns the full slug suffix", () => {
    expect(resolveDragLabel("palette-widget:map-placeholder-widget")).toBe(
      "map-placeholder-widget",
    )
  })

  it("resize handle id returns null (no UUID leak)", () => {
    expect(
      resolveDragLabel("ca8a4f8c-1234-5678-9abc-def012345678-handle-se"),
    ).toBeNull()
  })

  it("resize handle id for every position returns null", () => {
    for (const pos of ["n", "s", "e", "w", "ne", "nw", "se", "sw"]) {
      expect(resolveDragLabel(`some-placement-uuid-handle-${pos}`)).toBeNull()
    }
  })

  it("free-form whole-widget drag id (placement id with namespace) returns null", () => {
    expect(
      resolveDragLabel("free-form-placed-widget:ff-drag-1"),
    ).toBeNull()
  })

  it("bare placement uuid returns null", () => {
    expect(
      resolveDragLabel("ca8a4f8c-1234-5678-9abc-def012345678"),
    ).toBeNull()
  })

  it("empty string returns null", () => {
    expect(resolveDragLabel("")).toBeNull()
  })

  it("palette prefix only (no slug suffix) returns empty string (edge case — palette never emits this shape in practice)", () => {
    // Documented behavior: `slice("palette-widget:".length)` of the
    // bare prefix yields "". The DragOverlay's existing guard
    // (`activeDragLabel ? ... : null`) treats "" as falsy and
    // suppresses the overlay, so this edge case stays safe.
    expect(resolveDragLabel("palette-widget:")).toBe("")
  })

  it("unrecognized id shape returns null (safe default — no UUID leak by accident)", () => {
    expect(resolveDragLabel("some-future-drag-id-shape")).toBeNull()
    expect(resolveDragLabel("not-a-palette-id")).toBeNull()
  })
})

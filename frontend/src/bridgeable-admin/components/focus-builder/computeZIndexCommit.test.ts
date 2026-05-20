/**
 * Tests for `computeZIndexCommit` (sub-arc FF-5).
 *
 * Pure-function coverage per Q-40 (JSDOM weakness mitigation). No React,
 * no DOM, no @dnd-kit. Asserts the single output field (z_index)
 * explicitly per action variant.
 */
import { describe, expect, it } from "vitest"

import { computeZIndexCommit } from "./computeZIndexCommit"

describe("computeZIndexCommit — front", () => {
  it("with multiple widgets: target z_index = max(others) + 1", () => {
    const r = computeZIndexCommit({
      currentPlacement: { id: "a", z_index: 0 },
      allPlacements: [
        { id: "a", z_index: 0 },
        { id: "b", z_index: 3 },
        { id: "c", z_index: 2 },
      ],
      action: "front",
    })
    expect(r.z_index).toBe(4)
  })

  it("with only target widget: target z_index = 1", () => {
    const r = computeZIndexCommit({
      currentPlacement: { id: "a", z_index: 0 },
      allPlacements: [{ id: "a", z_index: 0 }],
      action: "front",
    })
    expect(r.z_index).toBe(1)
  })

  it("with no other placements (empty list defensive): target z_index = 1", () => {
    const r = computeZIndexCommit({
      currentPlacement: { id: "a", z_index: 5 },
      allPlacements: [],
      action: "front",
    })
    expect(r.z_index).toBe(1)
  })

  it("when target already at max: still bumps (max + 1)", () => {
    const r = computeZIndexCommit({
      currentPlacement: { id: "a", z_index: 7 },
      allPlacements: [
        { id: "a", z_index: 7 },
        { id: "b", z_index: 5 },
      ],
      action: "front",
    })
    // Others = [b@5]; max(others) + 1 = 6.
    expect(r.z_index).toBe(6)
  })
})

describe("computeZIndexCommit — back", () => {
  it("with multiple widgets: target z_index = min(others) - 1", () => {
    const r = computeZIndexCommit({
      currentPlacement: { id: "a", z_index: 0 },
      allPlacements: [
        { id: "a", z_index: 0 },
        { id: "b", z_index: 3 },
        { id: "c", z_index: 2 },
      ],
      action: "back",
    })
    expect(r.z_index).toBe(1)
  })

  it("with only target widget: target z_index = -1", () => {
    const r = computeZIndexCommit({
      currentPlacement: { id: "a", z_index: 0 },
      allPlacements: [{ id: "a", z_index: 0 }],
      action: "back",
    })
    expect(r.z_index).toBe(-1)
  })

  it("with negative z_index others: min - 1 = more-negative", () => {
    const r = computeZIndexCommit({
      currentPlacement: { id: "a", z_index: 0 },
      allPlacements: [
        { id: "a", z_index: 0 },
        { id: "b", z_index: -2 },
        { id: "c", z_index: 1 },
      ],
      action: "back",
    })
    expect(r.z_index).toBe(-3)
  })
})

describe("computeZIndexCommit — forward", () => {
  it("simple increment from positive value", () => {
    const r = computeZIndexCommit({
      currentPlacement: { id: "a", z_index: 3 },
      allPlacements: [
        { id: "a", z_index: 3 },
        { id: "b", z_index: 5 },
      ],
      action: "forward",
    })
    expect(r.z_index).toBe(4)
  })

  it("increment from zero", () => {
    const r = computeZIndexCommit({
      currentPlacement: { id: "a", z_index: 0 },
      allPlacements: [{ id: "a", z_index: 0 }],
      action: "forward",
    })
    expect(r.z_index).toBe(1)
  })

  it("increment from negative", () => {
    const r = computeZIndexCommit({
      currentPlacement: { id: "a", z_index: -2 },
      allPlacements: [{ id: "a", z_index: -2 }],
      action: "forward",
    })
    expect(r.z_index).toBe(-1)
  })
})

describe("computeZIndexCommit — backward", () => {
  it("simple decrement from positive value", () => {
    const r = computeZIndexCommit({
      currentPlacement: { id: "a", z_index: 3 },
      allPlacements: [
        { id: "a", z_index: 3 },
        { id: "b", z_index: 5 },
      ],
      action: "backward",
    })
    expect(r.z_index).toBe(2)
  })

  it("decrement from zero (yields negative)", () => {
    const r = computeZIndexCommit({
      currentPlacement: { id: "a", z_index: 0 },
      allPlacements: [{ id: "a", z_index: 0 }],
      action: "backward",
    })
    expect(r.z_index).toBe(-1)
  })
})

describe("computeZIndexCommit — undefined z_index treated as 0", () => {
  it("front: undefined target + undefined others → 1", () => {
    const r = computeZIndexCommit({
      currentPlacement: { id: "a" },
      allPlacements: [{ id: "a" }, { id: "b" }],
      action: "front",
    })
    // Others = [b@0]; max+1 = 1.
    expect(r.z_index).toBe(1)
  })

  it("back: undefined target + undefined others → -1", () => {
    const r = computeZIndexCommit({
      currentPlacement: { id: "a" },
      allPlacements: [{ id: "a" }, { id: "b" }],
      action: "back",
    })
    // Others = [b@0]; min-1 = -1.
    expect(r.z_index).toBe(-1)
  })

  it("forward: undefined target → 1", () => {
    const r = computeZIndexCommit({
      currentPlacement: { id: "a" },
      allPlacements: [{ id: "a" }],
      action: "forward",
    })
    expect(r.z_index).toBe(1)
  })

  it("backward: undefined target → -1", () => {
    const r = computeZIndexCommit({
      currentPlacement: { id: "a" },
      allPlacements: [{ id: "a" }],
      action: "backward",
    })
    expect(r.z_index).toBe(-1)
  })
})

describe("computeZIndexCommit — filters currentPlacement from allPlacements", () => {
  it("front: ignores currentPlacement's own z_index when computing max", () => {
    // Target at z=5; another widget at z=3. Front of target should
    // pick max(others=[3])+1 = 4, NOT max([5, 3])+1 = 6.
    const r = computeZIndexCommit({
      currentPlacement: { id: "a", z_index: 5 },
      allPlacements: [
        { id: "a", z_index: 5 },
        { id: "b", z_index: 3 },
      ],
      action: "front",
    })
    expect(r.z_index).toBe(4)
  })

  it("back: ignores currentPlacement's own z_index when computing min", () => {
    // Target at z=-5; another widget at z=2. Back of target should
    // pick min(others=[2])-1 = 1, NOT min([-5, 2])-1 = -6.
    const r = computeZIndexCommit({
      currentPlacement: { id: "a", z_index: -5 },
      allPlacements: [
        { id: "a", z_index: -5 },
        { id: "b", z_index: 2 },
      ],
      action: "back",
    })
    expect(r.z_index).toBe(1)
  })
})

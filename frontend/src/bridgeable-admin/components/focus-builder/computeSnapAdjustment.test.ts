/**
 * computeSnapAdjustment unit tests (sub-arc FF-7).
 *
 * Per Q-11 / Q-40: pure-function unit coverage of snap-to-alignment
 * helpers. The 6px threshold, alt-disable contract, multi-axis snap
 * composition, and canvas-centerline snap targets are all locked
 * here; the page-level dispatcher wires the helper into the drag-end
 * pipeline (see FocusBuilderCanvas dispatch).
 */
import { describe, expect, it } from "vitest"

import { computeSnapAdjustment } from "./computeSnapAdjustment"

const CANVAS = { width: 1200, height: 800 }

describe("computeSnapAdjustment", () => {
  it("alt key disables snap (returns dragPosition unchanged + empty snapLines)", () => {
    const result = computeSnapAdjustment({
      draggedPlacement: { id: "a", x: 100, y: 100, width: 200, height: 100 },
      otherPlacements: [{ id: "b", x: 104, y: 200, width: 200, height: 100 }],
      canvasDimensions: CANVAS,
      dragPosition: { x: 100, y: 100 },
      altKeyHeld: true,
    })
    expect(result.x).toBe(100)
    expect(result.y).toBe(100)
    expect(result.snapLines).toEqual([])
  })

  it("snaps left edge to other widget's left edge within 6px", () => {
    // Dragged at x=104; other widget at x=100. left-edge distance = 4
    // (within 6px threshold). Snap should pull x to 100.
    const result = computeSnapAdjustment({
      draggedPlacement: { id: "a", x: 104, y: 300, width: 200, height: 100 },
      otherPlacements: [{ id: "b", x: 100, y: 100, width: 200, height: 100 }],
      canvasDimensions: CANVAS,
      dragPosition: { x: 104, y: 300 },
      altKeyHeld: false,
    })
    expect(result.x).toBe(100)
    expect(result.snapLines.some((l) => l.axis === "vertical" && l.position === 100)).toBe(true)
  })

  it("snaps left edge to other widget's right edge within 6px", () => {
    // Other widget at x=100, width=200 → right edge = 300.
    // Dragged left at x=302 (distance=2). Snap pulls x to 300.
    const result = computeSnapAdjustment({
      draggedPlacement: { id: "a", x: 302, y: 300, width: 100, height: 100 },
      otherPlacements: [{ id: "b", x: 100, y: 100, width: 200, height: 100 }],
      canvasDimensions: CANVAS,
      dragPosition: { x: 302, y: 300 },
      altKeyHeld: false,
    })
    expect(result.x).toBe(300)
    expect(result.snapLines.some((l) => l.axis === "vertical" && l.position === 300)).toBe(true)
  })

  it("snaps right edge to other widget's left edge within 6px (side-by-side lineup)", () => {
    // Common case: dragged sits left of target, its right edge nearly
    // touches target's left. Other widget at x=500. Dragged at x=296
    // width 200 → right edge = 496 (distance 4). Snap moves dragged so
    // right edge aligns to 500 → dragged.x = 300.
    const result = computeSnapAdjustment({
      draggedPlacement: { id: "a", x: 296, y: 300, width: 200, height: 100 },
      otherPlacements: [{ id: "b", x: 500, y: 100, width: 100, height: 100 }],
      canvasDimensions: CANVAS,
      dragPosition: { x: 296, y: 300 },
      altKeyHeld: false,
    })
    expect(result.x).toBe(300)
    expect(result.snapLines.some((l) => l.axis === "vertical" && l.position === 500)).toBe(true)
  })

  it("snaps horizontal center to other widget's horizontal center within 6px", () => {
    // Other widget center X: x=100 + width=200/2 = 200.
    // Dragged width=100; for its center to align at 200, x must be 150.
    // Place dragged at x=153 (center=203; distance=3, within 6px).
    const result = computeSnapAdjustment({
      draggedPlacement: { id: "a", x: 153, y: 400, width: 100, height: 100 },
      otherPlacements: [{ id: "b", x: 100, y: 100, width: 200, height: 100 }],
      canvasDimensions: CANVAS,
      dragPosition: { x: 153, y: 400 },
      altKeyHeld: false,
    })
    expect(result.x).toBe(150)
    expect(result.snapLines.some((l) => l.axis === "vertical" && l.position === 200)).toBe(true)
  })

  it("snaps top edge to other widget's top edge within 6px", () => {
    // Other widget top at y=100. Dragged top at y=104 (distance=4).
    // Snap pulls y to 100.
    const result = computeSnapAdjustment({
      draggedPlacement: { id: "a", x: 400, y: 104, width: 200, height: 100 },
      otherPlacements: [{ id: "b", x: 100, y: 100, width: 200, height: 100 }],
      canvasDimensions: CANVAS,
      dragPosition: { x: 400, y: 104 },
      altKeyHeld: false,
    })
    expect(result.y).toBe(100)
    expect(result.snapLines.some((l) => l.axis === "horizontal" && l.position === 100)).toBe(true)
  })

  it("snaps vertical center to other widget's vertical center within 6px", () => {
    // Other widget center Y: y=100 + height=100/2 = 150.
    // Dragged height=80; for center to align at 150, y must be 110.
    // Place dragged at y=112 (center=152; distance=2).
    const result = computeSnapAdjustment({
      draggedPlacement: { id: "a", x: 400, y: 112, width: 100, height: 80 },
      otherPlacements: [{ id: "b", x: 100, y: 100, width: 200, height: 100 }],
      canvasDimensions: CANVAS,
      dragPosition: { x: 400, y: 112 },
      altKeyHeld: false,
    })
    expect(result.y).toBe(110)
    expect(result.snapLines.some((l) => l.axis === "horizontal" && l.position === 150)).toBe(true)
  })

  it("snaps to canvas horizontal center line within 6px", () => {
    // Canvas width 1200 → center X = 600.
    // Dragged width=200; for left edge to align at 600, x=600.
    // Place dragged at x=604; left distance=4. Snap pulls x to 600.
    // BUT — center X candidate also competes: dragged center at
    // x=604 → center=704 → distance to 600 = 104 (way out of
    // threshold). And right at x+200=804 → distance to 600 = 204
    // (out). So only left wins; result.x = 600.
    const result = computeSnapAdjustment({
      draggedPlacement: { id: "a", x: 604, y: 300, width: 200, height: 100 },
      otherPlacements: [],
      canvasDimensions: CANVAS,
      dragPosition: { x: 604, y: 300 },
      altKeyHeld: false,
    })
    expect(result.x).toBe(600)
    expect(
      result.snapLines.some(
        (l) => l.axis === "vertical" && l.position === 600,
      ),
    ).toBe(true)
  })

  it("snaps to canvas vertical center line within 6px", () => {
    // Canvas height 800 → center Y = 400.
    // Place dragged top edge at y=403 (distance=3). Snap pulls y=400.
    const result = computeSnapAdjustment({
      draggedPlacement: { id: "a", x: 100, y: 403, width: 200, height: 100 },
      otherPlacements: [],
      canvasDimensions: CANVAS,
      dragPosition: { x: 100, y: 403 },
      altKeyHeld: false,
    })
    expect(result.y).toBe(400)
    expect(
      result.snapLines.some(
        (l) => l.axis === "horizontal" && l.position === 400,
      ),
    ).toBe(true)
  })

  it("does NOT snap when distance > 6px", () => {
    // Dragged left at x=110; other widget left at x=100. Distance=10
    // (out of threshold). No snap; position unchanged; no snapLines.
    const result = computeSnapAdjustment({
      draggedPlacement: { id: "a", x: 110, y: 500, width: 200, height: 100 },
      otherPlacements: [{ id: "b", x: 100, y: 100, width: 200, height: 100 }],
      canvasDimensions: CANVAS,
      dragPosition: { x: 110, y: 500 },
      altKeyHeld: false,
    })
    expect(result.x).toBe(110)
    expect(result.y).toBe(500)
    expect(result.snapLines).toEqual([])
  })

  it("returns multiple snapLines when both horizontal AND vertical snap fire", () => {
    // Other widget at (100, 100, 200, 100). Dragged width=200 height=100.
    // Place dragged at (104, 104) — both left + top within 4px of
    // other's left + top. Both axes snap; result is (100, 100); 2
    // snap lines emitted.
    const result = computeSnapAdjustment({
      draggedPlacement: { id: "a", x: 104, y: 104, width: 200, height: 100 },
      otherPlacements: [{ id: "b", x: 100, y: 100, width: 200, height: 100 }],
      canvasDimensions: CANVAS,
      dragPosition: { x: 104, y: 104 },
      altKeyHeld: false,
    })
    expect(result.x).toBe(100)
    expect(result.y).toBe(100)
    expect(result.snapLines.length).toBeGreaterThanOrEqual(2)
    expect(
      result.snapLines.some((l) => l.axis === "vertical" && l.position === 100),
    ).toBe(true)
    expect(
      result.snapLines.some(
        (l) => l.axis === "horizontal" && l.position === 100,
      ),
    ).toBe(true)
  })

  it("empty otherPlacements: only canvas centerline snaps possible", () => {
    // No other placements. Dragged at x=596 (left distance to 600 = 4)
    // → snap to canvas center X. Y at 700 (well away from 400) → no snap.
    const result = computeSnapAdjustment({
      draggedPlacement: { id: "a", x: 596, y: 700, width: 100, height: 50 },
      otherPlacements: [],
      canvasDimensions: CANVAS,
      dragPosition: { x: 596, y: 700 },
      altKeyHeld: false,
    })
    expect(result.x).toBe(600)
    expect(result.y).toBe(700)
    expect(result.snapLines.some((l) => l.axis === "vertical")).toBe(true)
  })
})

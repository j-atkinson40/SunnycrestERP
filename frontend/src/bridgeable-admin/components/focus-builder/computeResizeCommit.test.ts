/**
 * Tests for `computeResizeCommit` (sub-arc FF-4).
 *
 * Organized as 8 per-handle describe blocks + global describe blocks
 * for min-dimension clamping and canvas-bounds clamping. Tests assert
 * the four output fields (x, y, width, height) explicitly.
 *
 * No React, no DOM, no @dnd-kit. Pure-function coverage per Q-40
 * (JSDOM weakness mitigation).
 */
import { describe, expect, it } from "vitest"

import { computeResizeCommit } from "./computeResizeCommit"

const CANVAS = { width: 1200, height: 800 }
const MIN = { width: 80, height: 40 }
const PLACEMENT = { x: 200, y: 200, width: 400, height: 200 }

describe("computeResizeCommit — handle: e (right edge)", () => {
  it("expands width on positive delta.x; x and y unchanged", () => {
    const r = computeResizeCommit({
      currentPlacement: PLACEMENT,
      handle: "e",
      delta: { x: 50, y: 0 },
      canvasDimensions: CANVAS,
      minDimensions: MIN,
    })
    expect(r).toEqual({ x: 200, y: 200, width: 450, height: 200 })
  })
  it("contracts width on negative delta.x", () => {
    const r = computeResizeCommit({
      currentPlacement: PLACEMENT,
      handle: "e",
      delta: { x: -60, y: 0 },
      canvasDimensions: CANVAS,
      minDimensions: MIN,
    })
    expect(r).toEqual({ x: 200, y: 200, width: 340, height: 200 })
  })
})

describe("computeResizeCommit — handle: w (left edge)", () => {
  it("expands width on negative delta.x and shifts x backward (right edge anchored)", () => {
    const r = computeResizeCommit({
      currentPlacement: PLACEMENT,
      handle: "w",
      delta: { x: -50, y: 0 },
      canvasDimensions: CANVAS,
      minDimensions: MIN,
    })
    // x = 200 + (-50) = 150; width = 400 - (-50) = 450; right edge
    // (150+450 = 600) matches original right edge (200+400 = 600).
    expect(r).toEqual({ x: 150, y: 200, width: 450, height: 200 })
  })
  it("contracts width on positive delta.x and shifts x forward", () => {
    const r = computeResizeCommit({
      currentPlacement: PLACEMENT,
      handle: "w",
      delta: { x: 80, y: 0 },
      canvasDimensions: CANVAS,
      minDimensions: MIN,
    })
    // x = 200 + 80 = 280; width = 400 - 80 = 320; right edge stays 600.
    expect(r).toEqual({ x: 280, y: 200, width: 320, height: 200 })
  })
})

describe("computeResizeCommit — handle: n (top edge)", () => {
  it("expands height on negative delta.y and shifts y up (bottom edge anchored)", () => {
    const r = computeResizeCommit({
      currentPlacement: PLACEMENT,
      handle: "n",
      delta: { x: 0, y: -30 },
      canvasDimensions: CANVAS,
      minDimensions: MIN,
    })
    expect(r).toEqual({ x: 200, y: 170, width: 400, height: 230 })
  })
  it("contracts height on positive delta.y and shifts y down", () => {
    const r = computeResizeCommit({
      currentPlacement: PLACEMENT,
      handle: "n",
      delta: { x: 0, y: 50 },
      canvasDimensions: CANVAS,
      minDimensions: MIN,
    })
    expect(r).toEqual({ x: 200, y: 250, width: 400, height: 150 })
  })
})

describe("computeResizeCommit — handle: s (bottom edge)", () => {
  it("expands height on positive delta.y; y unchanged", () => {
    const r = computeResizeCommit({
      currentPlacement: PLACEMENT,
      handle: "s",
      delta: { x: 0, y: 80 },
      canvasDimensions: CANVAS,
      minDimensions: MIN,
    })
    expect(r).toEqual({ x: 200, y: 200, width: 400, height: 280 })
  })
  it("contracts height on negative delta.y", () => {
    const r = computeResizeCommit({
      currentPlacement: PLACEMENT,
      handle: "s",
      delta: { x: 0, y: -50 },
      canvasDimensions: CANVAS,
      minDimensions: MIN,
    })
    expect(r).toEqual({ x: 200, y: 200, width: 400, height: 150 })
  })
})

describe("computeResizeCommit — handle: se (bottom-right corner)", () => {
  it("expands width and height; x and y unchanged", () => {
    const r = computeResizeCommit({
      currentPlacement: PLACEMENT,
      handle: "se",
      delta: { x: 60, y: 40 },
      canvasDimensions: CANVAS,
      minDimensions: MIN,
    })
    expect(r).toEqual({ x: 200, y: 200, width: 460, height: 240 })
  })
})

describe("computeResizeCommit — handle: sw (bottom-left corner)", () => {
  it("expands width on negative delta.x (shifts x back) and expands height on positive delta.y", () => {
    const r = computeResizeCommit({
      currentPlacement: PLACEMENT,
      handle: "sw",
      delta: { x: -40, y: 30 },
      canvasDimensions: CANVAS,
      minDimensions: MIN,
    })
    expect(r).toEqual({ x: 160, y: 200, width: 440, height: 230 })
  })
})

describe("computeResizeCommit — handle: ne (top-right corner)", () => {
  it("expands width and shifts y up (height grows; bottom anchored)", () => {
    const r = computeResizeCommit({
      currentPlacement: PLACEMENT,
      handle: "ne",
      delta: { x: 70, y: -20 },
      canvasDimensions: CANVAS,
      minDimensions: MIN,
    })
    expect(r).toEqual({ x: 200, y: 180, width: 470, height: 220 })
  })
})

describe("computeResizeCommit — handle: nw (top-left corner)", () => {
  it("expands width+height; shifts both x and y back so opposite corner anchored", () => {
    const r = computeResizeCommit({
      currentPlacement: PLACEMENT,
      handle: "nw",
      delta: { x: -20, y: -10 },
      canvasDimensions: CANVAS,
      minDimensions: MIN,
    })
    expect(r).toEqual({ x: 180, y: 190, width: 420, height: 210 })
  })
})

describe("computeResizeCommit — min-dimension clamp prevents collapse", () => {
  it("e handle: shrinking past min.width clamps to min.width", () => {
    const r = computeResizeCommit({
      currentPlacement: { x: 0, y: 0, width: 100, height: 60 },
      handle: "e",
      delta: { x: -200, y: 0 },
      canvasDimensions: CANVAS,
      minDimensions: MIN,
    })
    expect(r.width).toBe(MIN.width) // 80
    expect(r.x).toBe(0)
  })
  it("w handle: shrinking past min.width clamps width AND anchors right edge", () => {
    // current right edge = 200 + 400 = 600.
    // delta.x = 400 → would yield width = 0; clamp width = 80, x =
    // 600 - 80 = 520 (anchoring the right edge at 600).
    const r = computeResizeCommit({
      currentPlacement: PLACEMENT,
      handle: "w",
      delta: { x: 400, y: 0 },
      canvasDimensions: CANVAS,
      minDimensions: MIN,
    })
    expect(r.width).toBe(MIN.width) // 80
    expect(r.x).toBe(600 - MIN.width) // 520 — anchors right edge at 600
    expect(r.x + r.width).toBe(600) // right edge preserved
  })
  it("n handle: shrinking past min.height clamps AND anchors bottom edge", () => {
    // current bottom edge = 200 + 200 = 400.
    // delta.y = 300 → height = -100; clamp height = 40, y = 400 - 40 = 360.
    const r = computeResizeCommit({
      currentPlacement: PLACEMENT,
      handle: "n",
      delta: { x: 0, y: 300 },
      canvasDimensions: CANVAS,
      minDimensions: MIN,
    })
    expect(r.height).toBe(MIN.height) // 40
    expect(r.y).toBe(400 - MIN.height) // 360
    expect(r.y + r.height).toBe(400) // bottom edge preserved
  })
  it("s handle: shrinking past min.height clamps to min.height", () => {
    const r = computeResizeCommit({
      currentPlacement: PLACEMENT,
      handle: "s",
      delta: { x: 0, y: -300 },
      canvasDimensions: CANVAS,
      minDimensions: MIN,
    })
    expect(r.height).toBe(MIN.height) // 40
    expect(r.y).toBe(200) // unchanged
  })
  it("nw corner: both min clamps engage; both opposite edges anchored", () => {
    // current right edge = 600, bottom edge = 400.
    const r = computeResizeCommit({
      currentPlacement: PLACEMENT,
      handle: "nw",
      delta: { x: 400, y: 300 },
      canvasDimensions: CANVAS,
      minDimensions: MIN,
    })
    expect(r.width).toBe(MIN.width)
    expect(r.height).toBe(MIN.height)
    expect(r.x + r.width).toBe(600) // right anchored
    expect(r.y + r.height).toBe(400) // bottom anchored
  })
  it("se corner: both min clamps engage; x/y unchanged", () => {
    const r = computeResizeCommit({
      currentPlacement: PLACEMENT,
      handle: "se",
      delta: { x: -500, y: -300 },
      canvasDimensions: CANVAS,
      minDimensions: MIN,
    })
    expect(r.width).toBe(MIN.width)
    expect(r.height).toBe(MIN.height)
    expect(r.x).toBe(200)
    expect(r.y).toBe(200)
  })
})

describe("computeResizeCommit — canvas-bounds clamp prevents overflow", () => {
  it("e handle: width clamps so x + width ≤ canvas.width", () => {
    const r = computeResizeCommit({
      currentPlacement: { x: 1000, y: 100, width: 150, height: 100 },
      handle: "e",
      delta: { x: 500, y: 0 },
      canvasDimensions: CANVAS,
      minDimensions: MIN,
    })
    // x stays 1000; width clamped so x + width = 1200 → width = 200.
    expect(r.x).toBe(1000)
    expect(r.width).toBe(200)
    expect(r.x + r.width).toBe(CANVAS.width)
  })
  it("s handle: height clamps so y + height ≤ canvas.height", () => {
    const r = computeResizeCommit({
      currentPlacement: { x: 100, y: 700, width: 200, height: 80 },
      handle: "s",
      delta: { x: 0, y: 500 },
      canvasDimensions: CANVAS,
      minDimensions: MIN,
    })
    expect(r.y).toBe(700)
    expect(r.height).toBe(100) // 800 - 700
  })
  it("w handle: dragging past left edge clamps x at 0 and widens to original right edge", () => {
    // Start at x=200, width=400. Original right edge = 600.
    // delta.x = -300 → x = -100, width = 700. Lower-bound clamp:
    // x = 0; width = 600 (so right edge stays at 600).
    const r = computeResizeCommit({
      currentPlacement: PLACEMENT,
      handle: "w",
      delta: { x: -300, y: 0 },
      canvasDimensions: CANVAS,
      minDimensions: MIN,
    })
    expect(r.x).toBe(0)
    expect(r.width).toBe(600) // anchors original right edge
  })
  it("n handle: dragging past top edge clamps y at 0 and grows to original bottom", () => {
    // PLACEMENT y=200, height=200, original bottom = 400.
    const r = computeResizeCommit({
      currentPlacement: PLACEMENT,
      handle: "n",
      delta: { x: 0, y: -500 },
      canvasDimensions: CANVAS,
      minDimensions: MIN,
    })
    expect(r.y).toBe(0)
    expect(r.height).toBe(400) // anchors original bottom
  })
  it("nw corner: both lower bounds engage simultaneously", () => {
    const r = computeResizeCommit({
      currentPlacement: PLACEMENT,
      handle: "nw",
      delta: { x: -400, y: -400 },
      canvasDimensions: CANVAS,
      minDimensions: MIN,
    })
    expect(r.x).toBe(0)
    expect(r.y).toBe(0)
    expect(r.width).toBe(600)
    expect(r.height).toBe(400)
  })
  it("se corner: both upper bounds engage simultaneously", () => {
    const r = computeResizeCommit({
      currentPlacement: { x: 1000, y: 700, width: 150, height: 80 },
      handle: "se",
      delta: { x: 500, y: 500 },
      canvasDimensions: CANVAS,
      minDimensions: MIN,
    })
    expect(r.x).toBe(1000)
    expect(r.y).toBe(700)
    expect(r.x + r.width).toBe(CANVAS.width)
    expect(r.y + r.height).toBe(CANVAS.height)
  })
})

describe("computeResizeCommit — zero delta is a no-op", () => {
  const handles = ["nw", "n", "ne", "w", "e", "sw", "s", "se"] as const
  for (const h of handles) {
    it(`zero delta on ${h} returns the original placement`, () => {
      const r = computeResizeCommit({
        currentPlacement: PLACEMENT,
        handle: h,
        delta: { x: 0, y: 0 },
        canvasDimensions: CANVAS,
        minDimensions: MIN,
      })
      expect(r).toEqual(PLACEMENT)
    })
  }
})

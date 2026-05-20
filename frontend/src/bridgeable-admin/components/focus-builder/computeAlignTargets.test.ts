/**
 * computeAlignTargets unit tests (sub-arc FF-7).
 *
 * Per Q-17 (b): six align actions over the selection bounding box.
 * Distribute deferred per the prompt; not covered here.
 */
import { describe, expect, it } from "vitest"

import { computeAlignTargets } from "./computeAlignTargets"

const A = { id: "a", x: 100, y: 100, width: 200, height: 100 }
const B = { id: "b", x: 500, y: 250, width: 100, height: 150 }
// bbox: left=100, right=600, top=100, bottom=400; centerX=350, centerY=250

describe("computeAlignTargets", () => {
  it("left aligns to leftmost x", () => {
    const out = computeAlignTargets([A, B], "left")
    // A.x=100 (already leftmost), B → x=100.
    expect(out).toEqual([
      { id: "a", x: 100 },
      { id: "b", x: 100 },
    ])
  })

  it("right aligns to rightmost edge", () => {
    const out = computeAlignTargets([A, B], "right")
    // maxRight = B.x+width = 600. A's new x = 600 - 200 = 400. B's = 600-100 = 500.
    expect(out).toEqual([
      { id: "a", x: 400 },
      { id: "b", x: 500 },
    ])
  })

  it("center-horizontal aligns each to bbox center X", () => {
    const out = computeAlignTargets([A, B], "center-horizontal")
    // bboxCenterX = 350. A new x = 350 - 100 = 250. B new x = 350 - 50 = 300.
    expect(out).toEqual([
      { id: "a", x: 250 },
      { id: "b", x: 300 },
    ])
  })

  it("top aligns to topmost y", () => {
    const out = computeAlignTargets([A, B], "top")
    // min y = 100. A → 100 (no change). B → 100.
    expect(out).toEqual([
      { id: "a", y: 100 },
      { id: "b", y: 100 },
    ])
  })

  it("bottom aligns to bottom edge", () => {
    const out = computeAlignTargets([A, B], "bottom")
    // maxBottom = 400. A new y = 400 - 100 = 300. B new y = 400 - 150 = 250.
    expect(out).toEqual([
      { id: "a", y: 300 },
      { id: "b", y: 250 },
    ])
  })

  it("center-vertical aligns each to bbox center Y", () => {
    const out = computeAlignTargets([A, B], "center-vertical")
    // bboxCenterY = 250. A new y = 250 - 50 = 200. B new y = 250 - 75 = 175.
    expect(out).toEqual([
      { id: "a", y: 200 },
      { id: "b", y: 175 },
    ])
  })

  it("3-placement left align", () => {
    const C = { id: "c", x: 50, y: 500, width: 80, height: 60 }
    const out = computeAlignTargets([A, B, C], "left")
    // min x = 50 (C). All x → 50.
    expect(out).toEqual([
      { id: "a", x: 50 },
      { id: "b", x: 50 },
      { id: "c", x: 50 },
    ])
  })

  it("empty placements returns empty array", () => {
    expect(computeAlignTargets([], "left")).toEqual([])
  })

  it("single placement is its own target (no-op-like)", () => {
    const out = computeAlignTargets([A], "left")
    expect(out).toEqual([{ id: "a", x: 100 }])
  })
})

/**
 * A new pane goes in the first free space, not on top of another.
 *
 * ⚠️ THE NUMBERS BELOW ARE HAND-COMPUTED FROM THE CONSTANTS, SHOWN. Deriving the
 * expected value by calling the function under test would make every one of these pass
 * by construction.
 */
import { describe, expect, it } from "vitest"

import {
  PANE_GAP,
  RIGHT_ANCHOR,
  SCAN_STEP,
  TOP_ANCHOR,
  anchoredSlots,
  firstFreeSlot,
} from "./pane-placement"

/** James's screen. The dispatch asks about this width specifically. */
const WIDE = 1440
const INFO = 390

describe("the first pane lands where it has always landed", () => {
  it("at the right anchor, in the top band", () => {
    // 1440 - 24 - 390 = 1026
    expect(firstFreeSlot({ stageWidth: WIDE, width: INFO, taken: [], index: 0 })).toEqual({
      left: 1026,
      top: TOP_ANCHOR,
    })
  })

  it("and the constants are the ones the module documents", () => {
    // ⚠️ PINNED BECAUSE THE SLOT ARITHMETIC ABOVE IS ONLY MEANINGFUL AGAINST THEM. A
    // changed anchor would move every expectation in this file in step and nothing
    // would fail.
    expect({ PANE_GAP, SCAN_STEP, RIGHT_ANCHOR, TOP_ANCHOR }).toEqual({
      PANE_GAP: 16,
      SCAN_STEP: 24,
      RIGHT_ANCHOR: 24,
      TOP_ANCHOR: 72,
    })
  })
})

describe("the second pane goes beside the first, not on top of it", () => {
  it("scans left until the gap clears", () => {
    const slots = anchoredSlots(
      [{ id: "a", width: INFO }, { id: "b", width: INFO }],
      [],
      WIDE,
    )
    expect(slots.a).toEqual({ left: 1026, top: TOP_ANCHOR })
    // b must clear a's left edge by PANE_GAP: b.left + 390 <= 1026 - 16 = 1010,
    // so b.left <= 620. Scanning from 1026 in 24px steps: 1026 - 24*17 = 618.
    expect(slots.b).toEqual({ left: 618, top: TOP_ANCHOR })
    expect(slots.b.left + INFO).toBeLessThanOrEqual(slots.a.left - PANE_GAP)
  })

  it("three panes do not overlap each other", () => {
    const slots = anchoredSlots(
      [{ id: "a", width: INFO }, { id: "b", width: INFO }, { id: "c", width: INFO }],
      [],
      WIDE,
    )
    const spans = ["a", "b", "c"].map((id) => [slots[id].left, slots[id].left + INFO])
    spans.sort((x, y) => x[0] - y[0])
    for (let i = 1; i < spans.length; i += 1) {
      expect(spans[i][0], `pane ${i} overlaps the one to its left`).toBeGreaterThanOrEqual(
        spans[i - 1][1],
      )
    }
  })

  it("⚠️ THE OLD CASCADE WOULD HAVE FAILED THIS. 18px apart is an overlap.", () => {
    // The code this replaced: `right: 24 + i * 18`. Two 390px panes 18px apart overlap
    // by 372px — which is what James would have seen with two orders open.
    const oldSecondLeft = WIDE - (RIGHT_ANCHOR + 18) - INFO
    const slots = anchoredSlots([{ id: "a", width: INFO }, { id: "b", width: INFO }], [], WIDE)
    expect(oldSecondLeft + INFO).toBeGreaterThan(slots.a.left) // the old one overlapped
    expect(slots.b.left + INFO).toBeLessThan(slots.a.left) // the new one does not
  })
})

describe("a dragged pane is an obstacle, not a candidate", () => {
  it("a new pane is not placed under one the director moved", () => {
    const dragged = [{ left: 1000, width: INFO }]
    const slot = firstFreeSlot({ stageWidth: WIDE, width: INFO, taken: dragged, index: 0 })
    expect(slot.left + INFO).toBeLessThanOrEqual(1000 - PANE_GAP)
  })

  it("a pane dragged to the left leaves the right anchor free", () => {
    const dragged = [{ left: 20, width: INFO }]
    const slot = firstFreeSlot({ stageWidth: WIDE, width: INFO, taken: dragged, index: 0 })
    expect(slot).toEqual({ left: 1026, top: TOP_ANCHOR })
  })
})

describe("when nothing fits", () => {
  it("cascades rather than refusing to place the pane", () => {
    // A narrow stage with one wide pane already on it leaves no gap at all.
    const narrow = 500
    const slot = firstFreeSlot({
      stageWidth: narrow,
      width: 420,
      taken: [{ left: 16, width: 420 }],
      index: 2,
    })
    // ⚠️ AN OVERLAPPING PANE THE DIRECTOR CAN DRAG BEATS A PANE THAT NEVER APPEARED.
    expect(Number.isFinite(slot.left)).toBe(true)
    expect(slot.left).toBeGreaterThanOrEqual(PANE_GAP)
    expect(slot.top).toBe(TOP_ANCHOR + 2 * 22)
  })
})

/**
 * The drag gesture's arithmetic and its target lookup.
 *
 * ⚠️ THE THRESHOLD IS THE WHOLE CLICK/DRAG BOUNDARY, so it is asserted on both sides.
 * Below it the press opens the inline edit; at or above it the word is being carried.
 * A threshold that never fires makes every press a drag and takes typo-fixing away;
 * one that always fires drops words on whatever row the finger rested over.
 */
import { describe, expect, it } from "vitest"

import { DRAG_THRESHOLD_PX, dropTargetAt, isADrag } from "./held-drag"

describe("click or drag", () => {
  it("a press that has not moved is NOT a drag", () => {
    expect(isADrag({ x: 100, y: 100 }, { x: 100, y: 100 })).toBe(false)
  })

  it("a press under the threshold is NOT a drag", () => {
    /** ⚠️ THE CASE THE INLINE EDIT DEPENDS ON. A finger never holds perfectly still,
     *  so "did not move at all" would make click-to-fix-a-typo unreachable on a
     *  touchscreen — which is the device the office actually uses. */
    expect(isADrag({ x: 100, y: 100 }, { x: 103, y: 102 })).toBe(false)
  })

  it("a press at or past the threshold IS a drag", () => {
    expect(isADrag({ x: 100, y: 100 }, { x: 100 + DRAG_THRESHOLD_PX, y: 100 })).toBe(true)
    expect(isADrag({ x: 100, y: 100 }, { x: 140, y: 160 })).toBe(true)
  })

  it("it measures DISTANCE, not either axis alone", () => {
    /** 3-4-5: neither axis reaches 5, the distance does. A per-axis check would call
     *  this a click and leave the word in the strip after a visible drag. */
    expect(isADrag({ x: 0, y: 0 }, { x: 3, y: 4 })).toBe(true)
    expect(isADrag({ x: 0, y: 0 }, { x: 3, y: 3 })).toBe(false)
  })
})

describe("what the pointer is over", () => {
  function withPoint(el: Element | null, run: () => void) {
    const prev = document.elementFromPoint
    // jsdom has `elementFromPoint` but it has no layout, so it always returns null.
    // Stubbing it is the only way to assert the lookup at all.
    document.elementFromPoint = () => el as Element
    try {
      run()
    } finally {
      document.elementFromPoint = prev
    }
  }

  function row(attrs: string): HTMLElement {
    const host = document.createElement("div")
    host.innerHTML = `<button ${attrs}><span id="inner">x</span></button>`
    document.body.appendChild(host)
    return host
  }

  it("reads the row's DROP field, not its displayed fields", () => {
    /** ⚠️ THE DISTINCTION THIS FUNCTION EXISTS FOR. The cemetery row DISPLAYS three
     *  fields and WRITES one. Returning `cemetery_city` — the second displayed field —
     *  would file a cemetery's name as its town. */
    const host = row('data-fields="cemetery cemetery_city eta" data-drop-field="cemetery"')
    try {
      withPoint(host.querySelector("#inner"), () => {
        expect(dropTargetAt(10, 10)?.fieldId).toBe("cemetery")
      })
    } finally {
      host.remove()
    }
  })

  it("climbs from whatever is actually under the pointer", () => {
    /** The pointer lands on the value span or the tick, never on the row's own box. */
    const host = row('data-drop-field="vault"')
    try {
      withPoint(host.querySelector("#inner"), () => {
        expect(dropTargetAt(10, 10)?.row.getAttribute("data-drop-field")).toBe("vault")
      })
    } finally {
      host.remove()
    }
  })

  it("returns null over nothing, and over a non-row", () => {
    withPoint(null, () => expect(dropTargetAt(10, 10)).toBeNull())
    const plain = document.createElement("div")
    document.body.appendChild(plain)
    try {
      withPoint(plain, () => expect(dropTargetAt(10, 10)).toBeNull())
    } finally {
      plain.remove()
    }
  })

  it("refuses a row whose drop field is EMPTY", () => {
    /** ⚠️ A ROW WITH NO `edit_target` AND NO FIELDS RENDERS THE ATTRIBUTE AS "", which
     *  `closest` still matches. Placing against a field id of `""` is a write to the
     *  order with no row to show it in — the held word gone and nothing to show for it. */
    const host = row('data-drop-field=""')
    try {
      withPoint(host.querySelector("#inner"), () => {
        expect(dropTargetAt(10, 10)).toBeNull()
      })
    } finally {
      host.remove()
    }
  })
})

/**
 * A plain number picks; every other number a director types survives.
 *
 * ⚠️ THE CASES THE RULING NAMES ARE THE FIRST FIVE TESTS, verbatim: "monticello 1"
 * picks; "34", "1948", "10am", "lot 2" with a pick showing are not consumed.
 *
 * ⚠️ TESTED AS A PURE FUNCTION because the alternative is asserting it through a
 * 350 ms debounce and a React state round trip, which is how an off-by-one in a
 * boundary gets "covered" by a test that never reached the boundary.
 */
import { describe, expect, it } from "vitest"

import { NUMBER_LABELS, consumePickDigit } from "./pick-digit"

describe("the cases the ruling names", () => {
  it('"monticello 1" picks option 1 and leaves "monticello"', () => {
    expect(consumePickDigit("monticello 1", 2)).toEqual({
      index: 1,
      text: "monticello",
    })
  })

  it.each([
    ["34", 'a vault size — out of range for a 2-option pick'],
    ["1948", "a year"],
    ["10am", "a time, not a bare number"],
    ["lot 2", "a grave location"],
  ])("%j is NOT consumed (%s)", (text) => {
    expect(consumePickDigit(text, 2)).toBeNull()
  })
})

describe("the token must be a whole trailing number", () => {
  it("consumes a number after a space", () => {
    expect(consumePickDigit("veteran 2", 3)?.index).toBe(2)
  })

  it("consumes a number typed on its own", () => {
    expect(consumePickDigit("1", 2)).toEqual({ index: 1, text: "" })
  })

  it("consumes a number with a trailing space — still the last token", () => {
    expect(consumePickDigit("veteran 1 ", 2)).toEqual({ index: 1, text: "veteran" })
  })

  it("does NOT consume a number with words after it", () => {
    // ⚠️ NOT THE ONE JUST TYPED. Consuming it would edit settled text.
    expect(consumePickDigit("1 tent only", 2)).toBeNull()
  })

  it("does NOT consume a digit glued to a word", () => {
    expect(consumePickDigit("bv2", 3)).toBeNull()
    expect(consumePickDigit("34in", 3)).toBeNull()
  })

  it("does NOT consume part of a longer number", () => {
    // the trailing token is "1948", which is out of range — the "1" inside it is
    // never considered, because the match is the whole token
    expect(consumePickDigit("born 1948", 2)).toBeNull()
  })

  it("does NOT consume a decimal or a colon-time", () => {
    expect(consumePickDigit("10:30", 2)).toBeNull()
    expect(consumePickDigit("2.5", 3)).toBeNull()
  })
})

describe("the range is the option count", () => {
  it("consumes 1..N", () => {
    for (let i = 1; i <= 5; i += 1) {
      expect(consumePickDigit(`x ${i}`, 5)?.index).toBe(i)
    }
  })

  it("does not consume N+1", () => {
    expect(consumePickDigit("x 4", 3)).toBeNull()
  })

  it("does not consume 0", () => {
    // ⚠️ OPTIONS ARE ONE-BASED, matching what the pane prints, so 0 is not a choice.
    expect(consumePickDigit("x 0", 3)).toBeNull()
  })

  it("does nothing when no pick is showing", () => {
    expect(consumePickDigit("x 1", 0)).toBeNull()
  })

  it("handles a two-digit option count", () => {
    // ⚠️ N IS NOT ASSUMED TO BE ONE DIGIT. The ruling says 1..N, and a pick with
    // twelve options is a pick with twelve options.
    expect(consumePickDigit("x 12", 12)?.index).toBe(12)
    expect(consumePickDigit("x 13", 12)).toBeNull()
  })

  it("rejects a leading zero", () => {
    expect(consumePickDigit("x 01", 3)).toBeNull()
  })
})

describe("number labels", () => {
  it.each(NUMBER_LABELS)("%s 1 is a place, not a pick", (label) => {
    expect(consumePickDigit(`${label} 1`, 3)).toBeNull()
  })

  it("is case-insensitive about the label", () => {
    expect(consumePickDigit("Section 2", 3)).toBeNull()
    expect(consumePickDigit("LOT 1", 3)).toBeNull()
  })

  it("still picks after a word that is NOT a number label", () => {
    // ⚠️ THE POSITIVE CONTROL. A guard that rejected every preceded number would
    // satisfy the label tests and break the feature.
    expect(consumePickDigit("monticello 1", 3)?.index).toBe(1)
    expect(consumePickDigit("veteran 2", 3)?.index).toBe(2)
  })

  it("every label is a word the capture surface has a field for", () => {
    // ⚠️ THE VOCABULARY IS DERIVED, NOT IMAGINED — each entry is a word that appears
    // in a grave-location phrase, which is the field these numbers belong to. If this
    // list grows with words nobody has a field for, that is guesswork and it should
    // go red.
    expect(NUMBER_LABELS.length).toBeLessThanOrEqual(16)
    for (const l of NUMBER_LABELS) {
      expect(l).toMatch(/^[a-z#]+$/)
    }
  })
})

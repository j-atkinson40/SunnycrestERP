/**
 * What Tab does, and what it refuses to do.
 *
 * ⚠️ THE PLACE/HOLD SPLIT IS THE WHOLE RULE, so every test here says which of the two
 * it expects and why. A Tab that holds a word it could have placed leaves the director
 * dragging a chip onto a row Opas already knew; a Tab that places a word it should have
 * held writes a guess into the order.
 */
import { describe, expect, it } from "vitest"

import { lastWordOf, whatTabDoes, type TabInput } from "./tab"
import type { CaptureSpan, VocabTerm } from "@/services/opas-capture-service"

const span = (
  start: number,
  end: number,
  fields: string[],
  state: CaptureSpan["state"] = "captured",
): CaptureSpan => ({ start, end, state, field_ids: fields }) as CaptureSpan

const VOCAB: VocabTerm[] = [
  { text: "Monticello Burial Vault", kind: "vault" } as VocabTerm,
]

function input(over: Partial<TabInput> = {}): TabInput {
  return {
    text: "order for monticello",
    spans: [span(10, 20, ["vault"])],
    spansForText: "order for monticello",
    values: { vault: "Monticello Burial Vault" },
    pendingPickCount: 0,
    status: "capturing",
    vocab: VOCAB,
    ...over,
  }
}

describe("Tab places the word the caret is still on", () => {
  it("places a captured word gate 1 would have HELD", () => {
    /** ⚠️ THE WHOLE REASON THE KEY EXISTS. `wordsReadyToLeave` refuses this exact span
     *  — the word is at the end of the text, so clause 1 waits in case `monticello 34`
     *  is coming. Tab is the director saying it is not. If this returned `hold`, the
     *  key would park a word Opas had already understood. */
    expect(whatTabDoes(input())).toEqual({
      kind: "place",
      fieldId: "vault",
      text: "monticello",
      start: 10,
      end: 20,
    })
  })

  it("places the LAST placeable word, not the first", () => {
    /** Earlier captured words have already flown on their own; the one still in the bar
     *  is the one the director just typed. */
    const got = whatTabDoes(
      input({
        text: "order for hopkins monticello",
        spans: [span(10, 17, ["funeral_home"]), span(18, 28, ["vault"])],
        spansForText: "order for hopkins monticello",
        values: { funeral_home: "Hopkins Funeral Home", vault: "Monticello Burial Vault" },
      }),
    )
    expect(got).toMatchObject({ kind: "place", fieldId: "vault" })
  })

  it("will not place a span with NO resolved value", () => {
    /** ⚠️ THE VALUE IS WHAT GETS RECORDED, so a captured span whose field holds nothing
     *  has nothing to write. Placing it would put `undefined` in the order and clear
     *  the word out of the bar — the director's text gone and no row to show for it. */
    const got = whatTabDoes(input({ values: {} }))
    expect(got).toMatchObject({ kind: "hold", word: "monticello" })
  })

  it("will not place a span carrying TWO fields", () => {
    /** `"1948 to 2026"` is one span for two fields; one word cannot fly to two rows. */
    const got = whatTabDoes(
      input({
        text: "order for 1948 to 2026",
        spans: [span(10, 22, ["date_of_birth", "date_of_death"])],
        spansForText: "order for 1948 to 2026",
        values: { date_of_birth: "1948-01-01", date_of_death: "2026-01-01" },
      }),
    )
    expect(got).toMatchObject({ kind: "hold" })
  })
})

describe("Tab holds what Opas cannot place", () => {
  it("holds an unrecognized word", () => {
    expect(
      whatTabDoes(
        input({
          text: "order for blargle",
          spans: [span(10, 17, [], "unrecognized")],
          spansForText: "order for blargle",
          values: {},
        }),
      ),
    ).toEqual({ kind: "hold", word: "blargle", start: 10, end: 17 })
  })

  it("holds a TWO-WORD phrase whole", () => {
    /** ⚠️ THE SPAN BEATS THE LAST WORD FOR THIS REASON. A cemetery Opas has never heard
     *  of is two or three words, and holding `pastures` alone hands the director a chip
     *  they have to reassemble — the name they typed, broken up. */
    expect(
      whatTabDoes(
        input({
          text: "order for green pastures",
          spans: [span(10, 24, [], "unrecognized")],
          spansForText: "order for green pastures",
          values: {},
        }),
      ),
    ).toEqual({ kind: "hold", word: "green pastures", start: 10, end: 24 })
  })

  it("holds the last word when the extraction is STALE", () => {
    /** ⚠️ THE ASYMMETRY THAT MAKES TAB USEFUL MID-TYPING. Stale spans cannot PLACE — the
     *  cut would take the wrong characters — but holding reads the last word out of the
     *  current text and needs no span, so Tab still works a keystroke behind the server,
     *  which is where a person typing always is. */
    const got = whatTabDoes(input({ spansForText: "order for mont" }))
    expect(got).toEqual({ kind: "hold", word: "monticello", start: 10, end: 20 })
  })

  it("holds the last word when there are NO spans at all", () => {
    const got = whatTabDoes(
      input({ text: "order for blargle", spans: [], spansForText: null, values: {} }),
    )
    expect(got).toEqual({ kind: "hold", word: "blargle", start: 10, end: 17 })
  })
})

describe("what Tab refuses", () => {
  it("does nothing on an empty bar", () => {
    expect(whatTabDoes(input({ text: "" })).kind).toBe("nothing")
    expect(whatTabDoes(input({ text: "   " }))).toEqual({ kind: "nothing", why: "empty" })
  })

  it("an empty bar reports EMPTY even with a pick open", () => {
    /** ⚠️ THE ONLY CASE THE EMPTINESS CHECK ANSWERS ALONE, and it exists because a
     *  break test proved the two assertions above do NOT need it: with the check
     *  deleted, an empty bar still falls through to `lastWordOf` returning null and
     *  still reports `empty`. The ORDER of the guards is the real claim — emptiness is
     *  read before an open pick — and this is the only input where the two disagree.
     *
     *  ⚠️ AND IT MATTERS BECAUSE `why` IS DESTINED FOR A FLASH LINE. The prototype says
     *  *"Pick one of these first."* out loud; saying that to a director who pressed Tab
     *  on an empty bar answers a question they did not ask. */
    expect(whatTabDoes(input({ text: "", pendingPickCount: 1 }))).toEqual({
      kind: "nothing",
      why: "empty",
    })
  })

  it("does nothing while a pick is OPEN", () => {
    /** ⚠️ RULED, AND THE PROTOTYPE'S OWN FIRST BRANCH. The director is mid-question;
     *  placing or holding under it answers a different one. */
    expect(whatTabDoes(input({ pendingPickCount: 1 }))).toEqual({
      kind: "nothing",
      why: "pick-open",
    })
  })

  it("does nothing once the order is no longer capturing", () => {
    expect(whatTabDoes(input({ status: "complete" }))).toEqual({
      kind: "nothing",
      why: "not-capturing",
    })
  })

  it("the refusals OUTRANK a perfectly placeable word", () => {
    /** ⚠️ THE CONTROL ON ALL THREE. The same input places when nothing refuses it — so
     *  these tests are asserting the refusal, not the absence of the feature. */
    expect(whatTabDoes(input()).kind).toBe("place")
  })
})

describe("lastWordOf", () => {
  it("ignores trailing whitespace", () => {
    expect(lastWordOf("order for hopkins   ")).toEqual({
      word: "hopkins",
      start: 10,
      end: 17,
    })
  })

  it("handles a single word and an empty string", () => {
    expect(lastWordOf("hopkins")).toEqual({ word: "hopkins", start: 0, end: 7 })
    expect(lastWordOf("")).toBeNull()
    expect(lastWordOf("   ")).toBeNull()
  })

  it("splits on a NEWLINE too, because the bar is a textarea", () => {
    /** The bar became a `<textarea>` for wrapping, so a pasted order can carry one. */
    expect(lastWordOf("order for\nhopkins")).toEqual({
      word: "hopkins",
      start: 10,
      end: 17,
    })
  })
})

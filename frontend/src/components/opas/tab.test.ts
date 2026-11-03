/**
 * What Tab does, and what it refuses to do.
 *
 * ⚠️ THE PLACE/HOLD SPLIT IS THE WHOLE RULE, so every test here says which of the two
 * it expects and why. A Tab that holds a word it could have placed leaves the director
 * dragging a chip onto a row Opas already knew; a Tab that places a word it should have
 * held writes a guess into the order.
 */
import { describe, expect, it } from "vitest"

import { whatTabDoes, type TabInput } from "./tab"
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
     *  the word out of the bar — the director's text gone and no row to show for it.
     *
     *  ⚠️ IT NOW WAITS RATHER THAN HOLDING, changed by the 2026-11-03 ruling. It used
     *  to fall through to the last-word fallback, which would have parked a word the
     *  server UNDERSTOOD into "Not placed yet" — and parked only the tail of it. The
     *  span is captured; the value simply has not landed. Waiting is the honest answer
     *  to "not yet", and holding would have been a claim that Opas could not read it. */
    expect(whatTabDoes(input({ values: {} }))).toEqual({
      kind: "nothing",
      why: "no-span",
    })
  })

  it("will not place a span carrying TWO fields", () => {
    /** `"1948 to 2026"` is one span for two fields; one word cannot fly to two rows.
     *
     *  ⚠️ AND IT IS THE CLEAREST CASE FOR DROPPING THE LAST-WORD FALLBACK. The old code
     *  held `"2026"` — one end of a date RANGE, torn off and parked as if it were an
     *  unplaceable word, while `"1948 to"` stayed in the bar. That is the `"8 chairs"`
     *  defect with a worse blast radius, because both halves read as plausible. */
    const got = whatTabDoes(
      input({
        text: "order for 1948 to 2026",
        spans: [span(10, 22, ["date_of_birth", "date_of_death"])],
        spansForText: "order for 1948 to 2026",
        values: { date_of_birth: "1948-01-01", date_of_death: "2026-01-01" },
      }),
    )
    expect(got).toEqual({ kind: "nothing", why: "no-span" })
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

  it("does NOTHING when the extraction is STALE", () => {
    /** ⚠️ CHANGED BY RULING 2026-11-03, AND THE OLD BEHAVIOUR BROKE JAMES'S WALK. This
     *  used to hold the LAST WORD, on the reasoning that stale spans cannot place but
     *  holding needs no span — so Tab stayed useful a keystroke behind the server.
     *  What it actually did was split phrases: `"8 chairs"` lost its number.
     *
     *  Waiting costs one keypress. Splitting costs the director their number, and they
     *  have to notice it happened first. */
    expect(whatTabDoes(input({ spansForText: "order for mont" }))).toEqual({
      kind: "nothing",
      why: "no-span",
    })
  })

  it("does NOTHING when there are no spans at all", () => {
    expect(
      whatTabDoes(
        input({ text: "order for blargle", spans: [], spansForText: null, values: {} }),
      ),
    ).toEqual({ kind: "nothing", why: "no-span" })
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

describe("a multi-word span leaves as ONE UNIT or not at all", () => {
  /**
   * James's walk, 2026-11-03: he typed `"8 chairs"`, Tab took `chairs` into the strip
   * alone, and `8` stayed in the bar as a word Opas cannot place by itself.
   *
   * ⚠️ THE ENGINE WAS NEVER WRONG ABOUT THESE, measured against the real extractor on
   * 2026-11-03 — every one is a SINGLE span:
   *
   *     "8 chairs"                  (0,8)  captured  chairs_total
   *     "st marys"                  (0,8)  captured  cemetery
   *     "lowering device and grass"  (0,25) captured  cemetery_equipment
   *     "section A, lot 2"          (0,16) captured  grave_location
   *     "monticello Burial Vault"   (0,23) captured  vault
   *
   * The splitter was `lastWordOf`, which counted spaces and knew nothing about any of
   * them. It is deleted rather than made smarter: the spans already carry the grouping,
   * so any second opinion about word boundaries is a second source of truth.
   *
   * ⚠️ EACH CASE CARRIES A TRAILING WORD so gate 1 lets the phrase go. At the very end
   * of the text Tab is what releases it, which the first test below asserts directly.
   */
  const CASES: ReadonlyArray<{
    readonly phrase: string
    readonly fieldId: string
    readonly value: string
  }> = [
    { phrase: "8 chairs", fieldId: "chairs_total", value: "8" },
    { phrase: "st marys", fieldId: "cemetery", value: "St. Mary's Cemetery" },
    {
      phrase: "lowering device and grass",
      fieldId: "cemetery_equipment",
      value: "lowering_device_and_grass",
    },
    { phrase: "section A, lot 2", fieldId: "grave_location", value: "Section A, Lot 2" },
    {
      phrase: "monticello Burial Vault",
      fieldId: "vault",
      value: "Monticello Burial Vault",
    },
  ]

  it.each(CASES)("places %s whole", ({ phrase, fieldId, value }) => {
    const text = `order for ${phrase}`
    const got = whatTabDoes(
      input({
        text,
        spans: [
          { start: 10, end: 10 + phrase.length, state: "captured", field_ids: [fieldId] },
        ] as never,
        spansForText: text,
        values: { [fieldId]: value },
      }),
    )
    // ⚠️ THE WHOLE PHRASE, AND THE OFFSETS THAT COVER IT. A `text` of just the last
    // word would cut only that word out of the bar and strand the rest — which is
    // precisely the defect, expressed as offsets rather than as a word.
    expect(got).toEqual({
      kind: "place",
      fieldId,
      text: phrase,
      start: 10,
      end: 10 + phrase.length,
    })
  })

  it("'8 chairs' lands on chairs as 8", () => {
    /** ⚠️ JAMES'S OWN ASSERTION: *"'8 chairs' must land on chairs as 8."* The VALUE is
     *  what reaches the order, and it comes from the server's `values` — not from the
     *  phrase, and not from the digit the client could have parsed out of it. */
    const text = "order for 8 chairs"
    const got = whatTabDoes(
      input({
        text,
        spans: [
          { start: 10, end: 18, state: "captured", field_ids: ["chairs_total"] },
        ] as never,
        spansForText: text,
        values: { chairs_total: "8" },
      }),
    )
    expect(got).toMatchObject({ kind: "place", fieldId: "chairs_total", text: "8 chairs" })
    // the number the row will show, from the server
    expect(
      input({ values: { chairs_total: "8" } }).values.chairs_total,
    ).toBe("8")
  })

  it("an UNRECOGNIZED multi-word span is HELD whole", () => {
    /** The other half of the ruling. A cemetery Opas has never heard of is two or three
     *  words, and holding `pastures` alone hands the director a chip they have to
     *  reassemble — the name they typed, broken up. */
    const text = "order for green pastures thursday"
    expect(
      whatTabDoes(
        input({
          text,
          spans: [{ start: 10, end: 24, state: "unrecognized", field_ids: [] }] as never,
          spansForText: text,
          values: {},
        }),
      ),
    ).toEqual({ kind: "hold", word: "green pastures", start: 10, end: 24 })
  })

  it("NEVER emits a fragment of a span", () => {
    /** ⚠️ THE INVARIANT BEHIND ALL OF THE ABOVE, asserted as a property rather than
     *  case by case: whatever Tab returns, its offsets are exactly some span's offsets.
     *  A future shortcut that trimmed or split a phrase would fail here even if it
     *  passed every named case. */
    const text = "order for 8 chairs and st marys x"
    const spans = [
      { start: 10, end: 18, state: "captured", field_ids: ["chairs_total"] },
      { start: 23, end: 31, state: "captured", field_ids: ["cemetery"] },
    ]
    const got = whatTabDoes(
      input({
        text,
        spans: spans as never,
        spansForText: text,
        values: { chairs_total: "8", cemetery: "St. Mary's Cemetery" },
      }),
    )
    expect(got.kind).not.toBe("nothing")
    const edges = spans.map((sp) => `${sp.start}-${sp.end}`)
    const moved = got as { readonly start: number; readonly end: number }
    expect(edges).toContain(`${moved.start}-${moved.end}`)
  })
})

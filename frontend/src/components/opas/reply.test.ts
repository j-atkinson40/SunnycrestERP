/**
 * Answering a question by typing words that tell the options apart.
 *
 * ⚠️ THE EXAMPLES ARE JAMES'S OWN, verbatim from the dispatch: "typing words that match
 * one option ('smith', 'friday', 'the confirmed one')". They are the cases, not
 * illustrations of them.
 */
import { describe, expect, it } from "vitest"

import {
  FILLER,
  MIN_PREFIX,
  REPLY_FADE_MS,
  REPLY_GAP_ABOVE_BAR,
  answerTokens,
  matchAnswer,
  optionMatches,
  tokenHitsWord,
  type ReplyOption,
} from "./reply"

/** The dispatch's own scenario: Hopkins has two orders. */
const HOPKINS: ReplyOption[] = [
  { id: "o1", label: "Smith", detail: "SO-2026-0001 · Fri Oct 16 · draft" },
  { id: "o3", label: "Smith", detail: "SO-2026-0003 · Fri Oct 23 · confirmed" },
]

const MIXED: ReplyOption[] = [
  { id: "o3", label: "Smith", detail: "SO-2026-0003 · Fri Oct 23 · confirmed" },
  { id: "o4", label: "Hart", detail: "SO-2026-0004 · Wed Oct 28 · confirmed" },
]

describe("the constants come from the prototype", () => {
  it("fades after the prototype's own saidTimer, and sits its own gap above the bar", () => {
    // ⚠️ PINNED BECAUSE THEY ARE MEASURED, NOT CHOSEN. The prototype's
    // `setTimeout(…,4200)` and `placeSaid`'s `innerHeight - r.top + 10`.
    expect(REPLY_FADE_MS).toBe(4200)
    expect(REPLY_GAP_ABOVE_BAR).toBe(10)
  })
})

describe("tokens", () => {
  it("drops filler and punctuation, keeps the discriminating words", () => {
    expect(answerTokens("the Friday one")).toEqual(["friday"])
    expect(answerTokens("the confirmed one")).toEqual(["confirmed"])
    expect(answerTokens("  SMITH.  ")).toEqual(["smith"])
    expect(answerTokens("smith, friday")).toEqual(["smith", "friday"])
  })

  it("is empty when every word was filler", () => {
    // ⚠️ AND THAT MEANS "none", NOT "the first one". "the one" names nothing.
    expect(answerTokens("the one")).toEqual([])
    expect(answerTokens("that order")).toEqual([])
    expect(matchAnswer(HOPKINS, "the one")).toEqual({ kind: "none" })
  })

  it("FILLER contains every word the dispatch's own examples lean on", () => {
    for (const w of ["the", "one", "order"]) expect(FILLER).toContain(w)
  })
})

describe("prefix matching, in both directions", () => {
  it("reaches an abbreviation from the full word and back", () => {
    expect(tokenHitsWord("friday", "fri")).toBe(true)
    expect(tokenHitsWord("fri", "friday")).toBe(true)
    expect(tokenHitsWord("oct", "october")).toBe(true)
  })

  it("⚠️ IS NOT A SUBSTRING RULE", () => {
    // "id" is inside "Friday" and is not an answer to anything.
    expect(tokenHitsWord("id", "friday")).toBe(false)
    expect(tokenHitsWord("mit", "smith")).toBe(false)
  })

  it(`⚠️ AND THE SHORTER SIDE MUST REACH ${MIN_PREFIX}, or the loose direction is a wildcard`, () => {
    // Without the floor, an option containing "a" would match every token starting a.
    expect(tokenHitsWord("anything", "a")).toBe(false)
    expect(tokenHitsWord("a", "anything")).toBe(false)
    // exact equality is still a match at any length
    expect(tokenHitsWord("a", "a")).toBe(true)
  })
})

describe("one match is an answer", () => {
  it('"friday" picks the Friday order when only one is on a Friday', () => {
    expect(matchAnswer(MIXED, "friday")).toEqual({ kind: "one", index: 0 })
  })

  it('"smith" picks the Smith order when only one is Smith', () => {
    expect(matchAnswer(MIXED, "smith")).toEqual({ kind: "one", index: 0 })
    expect(matchAnswer(MIXED, "hart")).toEqual({ kind: "one", index: 1 })
  })

  it('"the confirmed one" picks when only one is confirmed', () => {
    expect(matchAnswer(HOPKINS, "the confirmed one")).toEqual({ kind: "one", index: 1 })
  })

  it("matches on the order number too, which is the one unambiguous handle", () => {
    expect(matchAnswer(HOPKINS, "0003")).toEqual({ kind: "one", index: 1 })
  })
})

describe("several matches narrow, and the question stays", () => {
  it('"smith" on two Smiths is still ambiguous', () => {
    // ⚠️ THE DISPATCH'S OWN CASE. Hopkins has two orders, both for Smith, so the
    // obvious answer is not an answer — and guessing the first would open the wrong
    // order silently.
    expect(matchAnswer(HOPKINS, "smith")).toEqual({ kind: "many", indices: [0, 1] })
  })

  it("and two words together resolve it", () => {
    expect(matchAnswer(HOPKINS, "smith friday oct 23")).toEqual({ kind: "one", index: 1 })
    expect(matchAnswer(HOPKINS, "smith draft")).toEqual({ kind: "one", index: 0 })
  })
})

describe("no match is a new request", () => {
  it("an unrelated phrase matches nothing", () => {
    expect(matchAnswer(HOPKINS, "the catalog")).toEqual({ kind: "none" })
    expect(matchAnswer(HOPKINS, "riverside")).toEqual({ kind: "none" })
  })

  it("⚠️ A NEW REQUEST THAT HAPPENS TO CONTAIN A DISCRIMINATING WORD IS STILL A NEW REQUEST", () => {
    // ⚠️ MY FIRST EXPECTATION HERE WAS WRONG AND THE TEST CAUGHT IT. I wrote
    // `{kind:"many", indices:[0,1]}` for "going out friday", reasoning that "friday"
    // hits both options. It does — but "going" and "out" hit neither, and EVERY token
    // must land, so the phrase resolves to `none` and the host treats it as the order
    // question it is. That is the behaviour James asked for, and the strictness of
    // `every` is what produces it.
    expect(matchAnswer(HOPKINS, "going out friday")).toEqual({ kind: "none" })
    expect(matchAnswer(HOPKINS, "hopkins orders this month")).toEqual({ kind: "none" })
  })

  it("⚠️ AND THE ASYMMETRY IS DELIBERATE: a stray word loses the QUESTION, never opens the WRONG ORDER", () => {
    // "the smith one on friday" reads as an answer to a person and is treated as a new
    // request, because "on" is not filler. That is the cost of the strict rule, and it
    // is the cheap direction: a question mis-read as a request is retyped, an order
    // opened by a mis-read answer is wrong and silent.
    //
    // ⚠️ SO `FILLER` IS NOT WIDENED WITH PREPOSITIONS, which was the obvious fix and
    // the wrong one. Adding "in" would make "orders in october" — a list question —
    // reduce to ["october"], which HITS both options and would be eaten as an answer.
    // Measured: with "in" absent it is `none`; with "in" present it is `many`.
    expect(matchAnswer(HOPKINS, "the smith one on friday")).toEqual({ kind: "none" })
    expect(FILLER).not.toContain("in")
    expect(FILLER).not.toContain("on")
    expect(matchAnswer(HOPKINS, "orders in october")).toEqual({ kind: "none" })
  })

  it("⚠️ THE CONTROL: the matcher is not simply returning none", () => {
    // Three of the four assertions above are negatives. Without this the file is
    // satisfied by `matchAnswer = () => ({kind:"none"})`.
    expect(matchAnswer(HOPKINS, "draft")).toEqual({ kind: "one", index: 0 })
  })

  it("an empty option list never matches", () => {
    expect(matchAnswer([], "smith")).toEqual({ kind: "none" })
    expect(optionMatches(HOPKINS[0], [])).toBe(false)
  })
})

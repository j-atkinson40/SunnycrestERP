/**
 * The opening has to be as forgiving as people are. James, production, 2026-10-16.
 *
 * ⚠️ HE TYPED "order hopk" AND GOT NOTHING — no pane, no question line, no ghost.
 * Nothing had regressed; `CAPTURE_START` simply required a VERB before "order"
 * ("new order…") or the exact phrase "order for". Measured that day:
 *
 *     "order hopk"       -> no capture      "order for hopk"  -> capture
 *     "order from hopk"  -> no capture      "new order hopk"  -> capture
 *
 * ⚠️ AND THE COST COMPOUNDED, WHICH IS WHY IT READ AS A DEAD FEATURE. The ghost only
 * runs in entry mode, so an opening that fails takes the completion down with it. The
 * bar was least able to help at the exact moment the director was typing a name it
 * knew — which is the moment James tried it.
 *
 * ⚠️ THE GATE IS THE VOCABULARY, NOT "order" PLUS ANYTHING. `isOrderListPhrase`
 * matches `\borders?\b`, so a blanket rule would route "order list" into a capture.
 */
import { describe, expect, it } from "vitest"

import { CAPTURE_START, startsCaptureWithParty } from "./opas-routing"
import { isOrderListPhrase } from "./order-list/order-list-routing"

const FH = ["Hopkins Funeral Home", "Riverside Funeral Home", "Smith & Sons Funeral Home"]
const opens = (p: string) =>
  CAPTURE_START.test(p.toLowerCase()) || startsCaptureWithParty(p, FH)

describe("the openings James named", () => {
  it.each([
    ["order hopk", "his own failing phrase"],
    ["order for hopk", "worked before"],
    ["new order hopk", "worked before"],
    ["order from hopk", "he listed it"],
    ["orders for hopk", "plural reads the same to a person"],
    ["start an order for Hopkins", "the long-standing form"],
  ])("%s starts capture (%s)", (phrase) => {
    expect(opens(phrase)).toBe(true)
  })

  it("'hopk' alone does NOT start capture", () => {
    // ⚠️ REPORTED RATHER THAN ASSUMED. Every opener James listed contains an order
    // word; a bare name does not, and a bar that captured on any funeral-home prefix
    // could not be used to ASK about one.
    expect(opens("hopk")).toBe(false)
  })
})

describe("what must NOT be swallowed", () => {
  it.each(["order list", "orders this month", "order status", "how much this month"])(
    "%s does not start a capture",
    (phrase) => {
      expect(opens(phrase)).toBe(false)
    },
  )

  it("leaves the order-list phrases to the order list", () => {
    // ⚠️ THE REGRESSION THIS GUARDS. `isOrderListPhrase` matches `\borders?\b`, and
    // capture is checked FIRST — so a broadened opener silently steals list queries.
    for (const p of ["orders this month", "order list"]) {
      expect(isOrderListPhrase(p), p).toBe(true)
      expect(opens(p), p).toBe(false)
    }
  })

  it("does not capture on a word that is not a funeral home", () => {
    expect(opens("order blargle")).toBe(false)
  })
})

describe("the vocabulary is the gate", () => {
  it("offers nothing before the names have loaded", () => {
    // ⚠️ THE REASON THE FETCH MOVED TO OPAS-OPEN. With an empty list the forgiving
    // opener cannot fire, so a capture that depended on it would never start —
    // which is the chicken-and-egg the old `entryMode` fetch created.
    expect(startsCaptureWithParty("order hopk", [])).toBe(false)
  })

  it("still starts on the old forms with no vocabulary at all", () => {
    // The original regex is untouched, so a failed vocabulary fetch degrades to
    // exactly the behaviour that shipped yesterday rather than to nothing.
    expect(CAPTURE_START.test("order for hopk")).toBe(true)
    expect(CAPTURE_START.test("new order hopk")).toBe(true)
  })
})

describe("⚠️ THE WHOLE SENTENCE IN ONE BREATH (James, 2026-10-20)", () => {
  /**
   * ⚠️ FOUND BY MEASURING, NOT BY REPORT. The 2026-10-20 investigation scored 59
   * phrasings against the shipped rules and this was one of three misses: the
   * dispatch's own capture example did not start a capture.
   *
   * ⚠️ THE OLD RULE ASKED ABOUT THE WHOLE REMAINDER. `"order hopk"` passed because
   * "hopkins funeral home" starts with "hopk". `"order hopk monti thursday 10 st
   * marys"` failed because that name does not start with the whole sentence and the
   * sentence does not start with "hopkins" — so the test was true for the shortest
   * input and false for the realistic one.
   *
   * ⚠️ AND THE FAILURE WAS NOT SILENT, IT WAS WORSE THAN SILENT. The phrase contains
   * "order", so `isOrderListPhrase` claimed it and the list answered "Try: Hopkins
   * orders this month" — the bar telling a director who had just typed a complete
   * order that it understood nothing.
   */
  it("James's own phrase starts a capture", () => {
    expect(opens("order hopk monti thursday 10 st marys")).toBe(true)
  })

  it.each([
    "order hopkins funeral home monticello full equipment going to st marys",
    "order for Riverside Memorial Chapel monticello burial vault graveside wednesday",
    "order smith & sons monticello friday 11 am",
    "orders for hopk monti thursday",
    "order riverside monti 10 am",
  ])("and so does %j", (phrase) => {
    expect(opens(phrase)).toBe(true)
  })

  it("⚠️ THE SHORT FORM STILL WORKS — the fix is a widening, not a replacement", () => {
    expect(opens("order hopk")).toBe(true)
    expect(opens("order for hopkins")).toBe(true)
  })

  it("⚠️ AND THE LIST PHRASES ARE UNTOUCHED, which is the whole risk of widening", () => {
    // A head-of-sentence scan could have swallowed these: each begins with an order
    // word and continues with something. None of their first words prefixes a home.
    for (const p of ["order list", "orders this month", "order status",
                     "orders since june", "order list on the lens", "orders"]) {
      expect(opens(p), p).toBe(false)
    }
    // ⚠️ THE CONTROL: the three that matter are still CLAIMED by the list, so "does
    // not start a capture" is about routing rather than about a dead predicate.
    for (const p of ["order list", "orders this month", "orders since june"]) {
      expect(isOrderListPhrase(p), p).toBe(true)
    }
  })

  it("⚠️ A ONE-LETTER HEAD IS STILL NOT A NAME", () => {
    // The old guard refused `rest.length < 2`; the floor moved onto the HEAD so that
    // "order h monticello" cannot match every home beginning with h.
    expect(opens("order h")).toBe(false)
    expect(startsCaptureWithParty("order h monticello friday", FH)).toBe(false)
  })

  it("⚠️ AND A WORD THAT IS NOT A NAME DOES NOT BECOME ONE BY HAVING WORDS AFTER IT", () => {
    expect(opens("order blargle monticello thursday")).toBe(false)
    expect(opens("order zzz")).toBe(false)
  })

  it("⚠️ THE FIRST WORD DECIDES, AND NOTHING AFTER IT CAN CHANGE THE ANSWER", () => {
    // ⚠️ RE-POINTED. This test used to assert that the scan "goes no further than the
    // longest name", over a multi-word loop. A break test hardcoding that bound to 1
    // turned NOTHING red — because prefix matching is monotone: if two words are a
    // prefix of a name, the first word is too. The loop could never add a match and is
    // deleted. What is testable, and is the behaviour, is that only the first word
    // matters.
    const FH1 = ["Hopkins Funeral Home"]
    for (const tail of ["", " monticello", " monticello thursday 10 st marys",
                        " funeral home monticello"]) {
      expect(startsCaptureWithParty(`order hopk${tail}`, FH1), tail).toBe(true)
    }
    // ⚠️ AND A FIRST WORD THAT NAMES NOTHING STAYS FALSE HOWEVER MUCH FOLLOWS IT. The
    // second case is the one that matters: " hopkins" AFTER a non-name must not rescue
    // it. A rule that looked anywhere in the sentence would pass that.
    for (const tail of ["", " monticello", " hopkins"]) {
      expect(startsCaptureWithParty(`order blargle${tail}`, FH1), tail).toBe(false)
    }
  })
})

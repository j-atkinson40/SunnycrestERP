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

/**
 * Stale extraction responses are dropped, and the client is what drops them.
 *
 * ⚠️ TESTED HERE RATHER THAN THROUGH THE PANE because through the pane every one of
 * these cases runs behind a 350 ms debounce and two fake-timer advances — which is how
 * an off-by-one in a race gets "covered" by a test that never raced. The pane test
 * asserts the WIRING (that the sequencer is consulted at all); this asserts the RULE.
 */
import { describe, expect, it } from "vitest"

import { EXTRACT_DEBOUNCE_MS, createSequencer } from "./capture-sequence"

describe("issue", () => {
  it("hands out strictly increasing numbers starting at 1", () => {
    const s = createSequencer()
    expect([s.issue(), s.issue(), s.issue()]).toEqual([1, 2, 3])
  })

  it("two sequencers do not share state", () => {
    const a = createSequencer()
    const b = createSequencer()
    a.issue()
    a.issue()
    expect(b.issue()).toBe(1)
  })
})

describe("accept", () => {
  it("accepts the first response", () => {
    const s = createSequencer()
    expect(s.accept(1)).toBe(true)
    expect(s.applied()).toBe(1)
  })

  it("DROPS A RESPONSE THAT ARRIVES BEHIND A NEWER ONE — the whole point", () => {
    const s = createSequencer()
    // the pane issued 1 then 2; 2 came back first
    expect(s.accept(2)).toBe(true)
    expect(s.accept(1)).toBe(false)
    expect(s.applied()).toBe(2)
  })

  it("drops a DUPLICATE delivery of the response already applied", () => {
    // ⚠️ `>` NOT `>=`. Re-applying carries nothing new and re-renders the pane for
    // no reason, which on a pane that re-renders per keystroke is visible.
    const s = createSequencer()
    expect(s.accept(3)).toBe(true)
    expect(s.accept(3)).toBe(false)
  })

  it("accepts an in-order run and nothing else", () => {
    const s = createSequencer()
    expect([1, 2, 3, 4].map(s.accept)).toEqual([true, true, true, true])
    expect([1, 2, 3, 4].map(s.accept)).toEqual([false, false, false, false])
  })

  it("accepts a GAP — a dropped request must not wedge the sequence", () => {
    // ⚠️ A REQUEST CAN FAIL AND NEVER COME BACK. If `accept` required seq ===
    // applied + 1, one lost response would make every later one stale and the pane
    // would freeze on the last reading it got — worse than the bug being fixed.
    const s = createSequencer()
    expect(s.accept(1)).toBe(true)
    expect(s.accept(9)).toBe(true)
    expect(s.applied()).toBe(9)
  })

  it("applied() is 0 before anything is applied", () => {
    expect(createSequencer().applied()).toBe(0)
  })

  it("accept does NOT compare against what was issued", () => {
    // ⚠️ THE OTHER WAY TO WRITE THIS WRONG. Comparing against `issued` would accept
    // every response in flight, because they were all issued — which is no filter
    // at all. A response for a number never issued is still applied if it is higher;
    // the sequencer's job is ordering, not authentication.
    const s = createSequencer()
    s.issue()
    s.issue()
    s.issue()
    expect(s.accept(2)).toBe(true)
    expect(s.accept(1)).toBe(false)
  })
})

describe("the debounce", () => {
  it("is 350 ms, in one place", () => {
    // ⚠️ PINNED SO A CHANGE IS DELIBERATE. The reasoning lives in the module
    // docstring: a fast typist's gap is 150–250 ms, and one re-extraction costs
    // p50 15.2 ms, so the wait dominates the work and 350 ms buys certainty cheaply.
    expect(EXTRACT_DEBOUNCE_MS).toBe(350)
  })

  it("is longer than a fast typist's inter-keystroke gap", () => {
    expect(EXTRACT_DEBOUNCE_MS).toBeGreaterThan(250)
  })

  it("is short enough that the pane does not feel detached", () => {
    expect(EXTRACT_DEBOUNCE_MS).toBeLessThanOrEqual(500)
  })
})

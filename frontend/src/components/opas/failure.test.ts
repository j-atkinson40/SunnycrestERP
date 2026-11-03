/**
 * What a failure is called, and whether it is worth asking again.
 *
 * ⚠️ THE COPY IS THE SUBJECT HERE, NOT DECORATION. Sweep item 2 exists because one
 * `catch` said "The order did not reach the server" for every failure, and the failure
 * it described on 2026-11-03 was a deterministic HTTP 500 — the order HAD reached the
 * server, been understood, and crashed the serializer on the way back out. A message
 * naming the wrong layer is the most expensive kind of wrong, because it is the first
 * evidence anyone has.
 */
import { describe, expect, it } from "vitest"

import { classifyFailure, stalledNotice, statusOf } from "./failure"

/** What axios gives you when the server answered. */
const answered = (status: number) => ({ response: { status, data: {} } })

/** What axios gives you when it never did. */
const neverArrived = () => new Error("Network Error")

describe("a request that never arrived", () => {
  it("is a network failure, and retries", () => {
    const f = classifyFailure(neverArrived())
    expect(f.kind).toBe("network")
    expect(f.retry).toBe(true)
    expect(f.status).toBeUndefined()
  })

  it("says RECONNECTING, which is a claim about the connection", () => {
    expect(classifyFailure(neverArrived()).notice).toMatch(/reconnecting/i)
  })

  it("treats a malformed error as network, because that is the retrying side", () => {
    /** ⚠️ A RESPONSE WITH NO STATUS IS NOT EVIDENCE THE SERVER ANSWERED. The safe
     *  default is the one that tries again — refusing to retry on a garbled error
     *  object would turn a transient blip into a dead bar. */
    for (const bad of [null, undefined, "boom", 42, {}, { response: null }, { response: {} }]) {
      expect(classifyFailure(bad).kind).toBe("network")
    }
  })
})

describe("a server that answered with an error", () => {
  it("is a SERVER error, names the status, and retries", () => {
    const f = classifyFailure(answered(500))
    expect(f.kind).toBe("server")
    expect(f.status).toBe(500)
    expect(f.retry).toBe(true)
  })

  it("says Opas hit an error — NOT a connection message", () => {
    /** ⚠️ JAMES'S OWN WORDING: *"A 500 is 'Opas hit an error — your order is safe', not
     *  a connection message."* The negative assertion is the one that matters: the old
     *  copy would satisfy a test that only checked for "safe". */
    const f = classifyFailure(answered(500))
    expect(f.notice).toMatch(/Opas hit an error \(500\)/)
    expect(f.notice).not.toMatch(/reconnect/i)
    expect(f.notice).not.toMatch(/reach the server/i)
  })

  it("carries the status into the text, for the next bug report", () => {
    expect(classifyFailure(answered(502)).notice).toContain("(502)")
    expect(classifyFailure(answered(503)).notice).toContain("(503)")
  })
})

describe("a server that refused", () => {
  it("does NOT retry a 4xx", () => {
    /** ⚠️ THE SERVER READ IT AND SAID NO. Asking again unchanged gets the same no, so
     *  three attempts are three ways of not listening — and they delay the notice the
     *  director needs by the whole backoff. */
    const f = classifyFailure(answered(400))
    expect(f.kind).toBe("refused")
    expect(f.retry).toBe(false)
  })

  it("still says the order is safe, because it is", () => {
    expect(classifyFailure(answered(409)).notice).toMatch(/your order is safe/i)
    expect(classifyFailure(answered(409)).notice).toContain("(409)")
  })

  it("but 408 and 429 DO retry, because both mean ask again", () => {
    /** ⚠️ THE TWO 4xx THAT ARE NOT REFUSALS. 408 Request Timeout and 429 Too Many
     *  Requests both say "try later" in so many words; lumping them with 400 would
     *  turn a rate limit into a dead bar until the next keystroke. */
    expect(classifyFailure(answered(408)).retry).toBe(true)
    expect(classifyFailure(answered(429)).retry).toBe(true)
  })
})

describe("the three kinds are never the same sentence", () => {
  it("network, server and refused all read differently", () => {
    /** ⚠️ THE SWEEP ITEM AS ONE ASSERTION: *"never one message for both"*. Asserted as
     *  distinctness rather than three string checks, so a future edit that collapses
     *  two of them fails here even if each individual wording still looks fine. */
    const lines = [
      classifyFailure(neverArrived()).notice,
      classifyFailure(answered(500)).notice,
      classifyFailure(answered(400)).notice,
    ]
    expect(new Set(lines).size).toBe(3)
  })

  it("and they stay distinct once every attempt has failed", () => {
    const settled = [
      stalledNotice(classifyFailure(neverArrived())),
      stalledNotice(classifyFailure(answered(500))),
      stalledNotice(classifyFailure(answered(400))),
    ]
    expect(new Set(settled).size).toBe(3)
    // ⚠️ AND EVERY ONE STILL SAYS THE ORDER IS SAFE. That is the invariant across all
    // of them, and the only part of the old copy worth keeping.
    for (const line of settled) expect(line).toMatch(/your order is safe/i)
  })

  it("the settled line says the words have not been read yet", () => {
    /** It is the one actionable fact: retype the last few words. */
    expect(stalledNotice(classifyFailure(answered(500)))).toMatch(
      /have not been read yet/i,
    )
  })
})

describe("statusOf", () => {
  it("reads the status when the server answered", () => {
    expect(statusOf(answered(418))).toBe(418)
  })

  it("is undefined for everything else", () => {
    expect(statusOf(neverArrived())).toBeUndefined()
    expect(statusOf({ response: { status: "500" } })).toBeUndefined()
  })
})

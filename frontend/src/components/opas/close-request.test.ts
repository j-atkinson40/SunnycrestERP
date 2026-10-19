/**
 * "close" closes the front pane. "close it out" does something else entirely.
 */
import { describe, expect, it } from "vitest"

import { CLOSE_PHRASES, isCloseRequest } from "./close-request"

describe("what closes a pane", () => {
  it.each(CLOSE_PHRASES)("%s closes", (phrase) => {
    expect(isCloseRequest(phrase)).toBe(true)
  })

  it("is insensitive to case, surrounding space and a full stop", () => {
    expect(isCloseRequest("  CLOSE.  ")).toBe(true)
    expect(isCloseRequest("Close This Pane")).toBe(true)
  })
})

describe("⚠️ WHAT MUST NOT CLOSE A PANE", () => {
  it('"close it out" is an order action, not a pane gesture', () => {
    // ⚠️ THE WHOLE REASON THIS IS AN EXACT LIST. `stage.FLAG_COPY` labels a delivered,
    // unclosed order "Delivered, not closed out" with the action "Close it out". A
    // `\bclose\b` rule would close the pane instead of acting on the order — two
    // meanings eight characters apart.
    expect(isCloseRequest("close it out")).toBe(false)
    expect(isCloseRequest("close out SO-2026-0002")).toBe(false)
    expect(CLOSE_PHRASES).not.toContain("close it out")
  })

  it("an order question that happens to contain the word is left alone", () => {
    expect(isCloseRequest("hopkins orders close to friday")).toBe(false)
    expect(isCloseRequest("closed orders")).toBe(false)
  })

  it("and nothing unrelated matches", () => {
    expect(isCloseRequest("orders")).toBe(false)
    expect(isCloseRequest("")).toBe(false)
    expect(isCloseRequest("the catalog")).toBe(false)
  })
})

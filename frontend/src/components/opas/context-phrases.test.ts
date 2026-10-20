/**
 * The exact phrasings, asserted as the table the dispatch asked to have listed.
 */
import { describe, expect, it } from "vitest"

import {
  CONTEXT_PHRASES,
  contextIntent,
  isContextPhrase,
  normalizePhrase,
} from "./context-phrases"

describe("the phrases that ACT on the order in front", () => {
  it.each([
    ["the vault", "vault"],
    ["Vault", "vault"],
    ["open the vault", "vault"],
    ["the funeral home", "customer"],
    ["the customer", "customer"],
    ["the cemetery", "cemetery"],
    ["undo confirm", "undo-confirm"],
    ["Undo Confirm.", "undo-confirm"],
    ["unconfirm", "undo-confirm"],
    ["make it a draft", "undo-confirm"],
  ])("%s -> act %s", (phrase, action) => {
    expect(contextIntent(phrase)).toEqual({ kind: "act", action })
  })
})

describe("the phrases that are ANSWERED without opening anything", () => {
  it.each([
    ["when's the service?", "service"],
    ["whens the service", "service"],
    ["when is the service", "service"],
    ["what's the total", "total"],
    ["the total", "total"],
    ["how much", "total"],
    ["who's it for", "who"],
    ["who is it for", "who"],
    ["where is it going", "where"],
    ["what's the status", "status"],
  ])("%s -> answer %s", (phrase, question) => {
    expect(contextIntent(phrase)).toEqual({ kind: "answer", question })
  })
})

describe("normalisation is why one spelling is enough", () => {
  it("strips punctuation and case and collapses space", () => {
    expect(normalizePhrase("  When's   the SERVICE?? ")).toBe("whens the service")
  })

  it("so every key in the table is already in normal form", () => {
    // ⚠️ A KEY THAT IS NOT NORMALISED CAN NEVER BE REACHED, and nothing else would say
    // so — the lookup would just quietly never hit it. An apostrophe in a key is the
    // exact mistake this catches.
    for (const key of Object.keys(CONTEXT_PHRASES)) {
      expect(normalizePhrase(key), `"${key}" is unreachable`).toBe(key)
    }
  })
})

describe("⚠️ WHAT MUST NOT BE A CONTEXT PHRASE", () => {
  it("a catalog request that merely contains the word", () => {
    // The reason this is a table and not a `\bvault\b` scan.
    expect(isContextPhrase("monticello vault")).toBe(false)
    expect(isContextPhrase("urn vault")).toBe(false)
    expect(isContextPhrase("the catalog")).toBe(false)
  })

  it("an order capture opener", () => {
    expect(isContextPhrase("order for hopkins monticello vault")).toBe(false)
    expect(isContextPhrase("new order")).toBe(false)
  })

  it("an order-list question", () => {
    expect(isContextPhrase("hopkins orders this month")).toBe(false)
    expect(isContextPhrase("going out friday")).toBe(false)
    expect(isContextPhrase("riverside order")).toBe(false)
  })

  it("a close request, and an order number", () => {
    expect(isContextPhrase("close")).toBe(false)
    expect(isContextPhrase("SO-2026-0004")).toBe(false)
  })

  it("⚠️ THE CONTROL: the table is not simply empty", () => {
    // Nine assertions above are negatives. Without this the file passes against
    // `CONTEXT_PHRASES = {}`.
    expect(isContextPhrase("the vault")).toBe(true)
    expect(Object.keys(CONTEXT_PHRASES).length).toBeGreaterThan(20)
  })
})

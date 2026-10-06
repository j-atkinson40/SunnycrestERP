/**
 * The label rule, with constructed pairs.
 *
 * ⚠️ CONSTRUCTED, NOT MEASURED-OVER-LIVE-DATA. The live catalog hides 50 of 52, so a test
 * driven by it would pass under almost any rule that mostly hides. These pairs are chosen
 * so each one fails for a different reason if the rule changes.
 */
import { describe, expect, it } from "vitest"

import { labelIsRedundant, labelWords } from "./option-label"

describe("labelIsRedundant — hides only what the name already says", () => {
  it.each([
    ["Bronze", "Wilbert Bronze Burial Vault"],
    ["Monticello", "Monticello Burial Vault"],
    ["Single", "Single Lowering Device"],
    ["Chairs", "Chairs"],
    ["Graveliner", "Graveliner Urn Vault"],
  ])("hides %j on %j", (label, name) => {
    expect(labelIsRedundant(label, name)).toBe(true)
  })

  it.each([
    ["Standard", "Continental Burial Vault"],
    ["Standard", "Graveliner"],
    ["Social Service", "Graveliner Burial Vault"],
    ["38 inch", "Graveliner Standard"],
  ])("shows %j on %j", (label, name) => {
    expect(labelIsRedundant(label, name)).toBe(false)
  })

  describe("inch-marks fold to the word inch", () => {
    it.each(['Continental 34"', "Continental 34”", "Continental 34 inch"])(
      "hides '34 inch' on %j",
      (name) => expect(labelIsRedundant("34 inch", name)).toBe(true),
    )

    it("and the fold works in the other direction too", () => {
      expect(labelIsRedundant('34"', "Continental 34 inch")).toBe(true)
    })

    it("⚠️ a DIFFERENT size still shows — the fold must not collapse 34 and 38", () => {
      expect(labelIsRedundant("38 inch", 'Continental 34"')).toBe(false)
    })
  })

  describe("the edges", () => {
    it("an absent label is not redundant — there is nothing to hide", () => {
      expect(labelIsRedundant(undefined, "Anything")).toBe(false)
    })

    it("a blank label is not redundant either", () => {
      expect(labelIsRedundant("   ", "Anything")).toBe(false)
    })

    it("⚠️ EVERY word must match, not any — a partial overlap SHOWS", () => {
      // Without this, "Social Service" would hide on any name containing "Service".
      expect(labelIsRedundant("Social Service", "Service Vault")).toBe(false)
    })

    it("case and punctuation do not matter", () => {
      expect(labelIsRedundant("social service", "Graveliner (Social Service)")).toBe(true)
    })

    it("labelWords is exported so the fold is inspectable, not buried", () => {
      expect(labelWords('Continental 34"')).toEqual(["continental", "34", "inch"])
    })
  })
})

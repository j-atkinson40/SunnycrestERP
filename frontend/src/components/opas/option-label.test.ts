/**
 * The label rule, with constructed pairs.
 *
 * ⚠️ CONSTRUCTED, NOT MEASURED-OVER-LIVE-DATA. The live catalog hides 50 of 52, so a test
 * driven by it would pass under almost any rule that mostly hides. These pairs are chosen
 * so each one fails for a different reason if the rule changes.
 */
import { describe, expect, it } from "vitest"

import { labelIsRedundant, labelWords, resolveRowLabels } from "./option-label"

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

describe("resolveRowLabels — collisions become the line name", () => {
  const row = (
    id: string, name: string, kind: string, option_label?: string, product_name?: string,
  ) => ({ variant_template_id: id, name, kind, option_label, product_name })

  it("⚠️ THE MEASURED CASE: two urns whose labels both hid, so the rows became identical", () => {
    // Both carry option_label equal to their own name, so rule 1 hides both and the rows
    // collide. Checking RAW labels would have found no collision — they differ from nothing.
    const out = resolveRowLabels([
      row("a", "Cream & Gold", "urn", "Cream & Gold", "Regal Line"),
      row("b", "Cream & Gold", "urn", "Cream & Gold", "Tribute Line"),
    ])
    expect(out.a).toBe("Regal Line")
    expect(out.b).toBe("Tribute Line")
  })

  it("a row with no collision keeps rule 1's answer", () => {
    const out = resolveRowLabels([
      row("a", "Continental Burial Vault", "burial_vault", "Standard", "Continental"),
      row("b", "Monticello Burial Vault", "burial_vault", "Monticello", "Monticello"),
    ])
    expect(out.a).toBe("Standard")        // adds something — kept
    expect(out.b).toBeUndefined()         // redundant — still hidden
  })

  it("⚠️ GENERAL, NOT AN URN RULE — a burial-vault collision is handled too", () => {
    const out = resolveRowLabels([
      row("a", "Twin", "burial_vault", "Twin", "Line One"),
      row("b", "Twin", "burial_vault", "Twin", "Line Two"),
    ])
    expect(out.a).toBe("Line One")
    expect(out.b).toBe("Line Two")
  })

  it("⚠️ the same name in DIFFERENT groups is not a collision", () => {
    // A collision is defined within a group; the groups are rendered under separate
    // headings, so two identical rows under different headings are already distinguished.
    const out = resolveRowLabels([
      row("a", "Graveliner", "grave_liner", "Graveliner", "Graveliner"),
      row("b", "Graveliner", "urn_vault", "Graveliner", "Graveliner Urn Vault"),
    ])
    expect(out.a).toBeUndefined()
    expect(out.b).toBeUndefined()
  })

  it("the same name with DIFFERENT surviving labels is not a collision", () => {
    const out = resolveRowLabels([
      row("a", "Graveliner", "grave_liner", "Standard", "Graveliner"),
      row("b", "Graveliner", "grave_liner", "Social Service", "Graveliner"),
    ])
    expect(out.a).toBe("Standard")
    expect(out.b).toBe("Social Service")
  })

  it("three-way collisions all get their line name", () => {
    const out = resolveRowLabels([
      row("a", "X", "urn", "X", "One"),
      row("b", "X", "urn", "X", "Two"),
      row("c", "X", "urn", "X", "Three"),
    ])
    expect([out.a, out.b, out.c]).toEqual(["One", "Two", "Three"])
  })

  it("⚠️ a missing line name shows NOTHING rather than an id", () => {
    // There is nothing honest to disambiguate with. The rows stay identical, and that stays
    // visibly true instead of being papered over with noise.
    const out = resolveRowLabels([
      row("a", "X", "urn", "X", undefined),
      row("b", "X", "urn", "X", undefined),
    ])
    expect(out.a).toBeUndefined()
    expect(out.b).toBeUndefined()
  })

  it("⚠️ DIFFERENT raw labels that BOTH hide ARE a collision", () => {
    // This is the case that discriminates rule-1-keying from raw-keying, and it did not
    // exist until a break test keying on the raw label came back green. Both labels are
    // redundant against the name, so both hide and the rows render identically — even
    // though the raw strings differ.
    const out = resolveRowLabels([
      row("a", "Jewel", "urn", "Jewel", "Regal Line"),
      row("b", "Jewel", "urn", "jewel", "Tribute Line"),
    ])
    expect(out.a).toBe("Regal Line")
    expect(out.b).toBe("Tribute Line")
  })

  it("a single row is never given a line name", () => {
    const out = resolveRowLabels([row("a", "Alone", "urn", "Alone", "Some Line")])
    expect(out.a).toBeUndefined()
  })
})


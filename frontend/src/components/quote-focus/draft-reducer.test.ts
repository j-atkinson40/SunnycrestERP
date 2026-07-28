/**
 * S-3b draft reducer — the LOCAL edit state. Pins seed-from-extraction,
 * every mutation (add / remove / qty / override), and the persisted-blob
 * round-trip that survives reload.
 */

import { describe, expect, it } from "vitest"

import type { ExtractionContext } from "@/components/command-bar-surfaces/types"
import {
  draftFromPersisted,
  draftReducer,
  seedFromExtraction,
  type QuoteDraft,
} from "./draft-reducer"

const extraction: ExtractionContext = {
  entryIntent: "quote",
  customer: { id: "c1", name: "Hopkins Funeral Home" },
  lines: [
    { productRef: "Monticello", quantity: 2 },
    { productRef: "Continental", productId: "p2", quantity: 1 },
  ],
  rawInput: "quote",
}

describe("seedFromExtraction", () => {
  it("maps extraction lines into draft lines with stable ids", () => {
    const d = seedFromExtraction(extraction)
    expect(d.customer).toEqual({ id: "c1", name: "Hopkins Funeral Home" })
    expect(d.lines).toHaveLength(2)
    expect(d.lines[0].productRef).toBe("Monticello")
    expect(d.lines[0].quantity).toBe(2)
    expect(d.lines[1].productId).toBe("p2")
    // unique line ids
    expect(d.lines[0].lineId).not.toBe(d.lines[1].lineId)
  })

  it("null extraction yields an empty editable canvas", () => {
    const d = seedFromExtraction(null)
    expect(d).toEqual({ customer: null, lines: [] })
  })

  it("PARTIAL extraction does not crash (S-5 park handoff guard)", () => {
    // A park escalation can hand off a still-seeding / minimal draft (no
    // `lines`, no `customer`). The Focus must degrade to an empty canvas,
    // never throw on `undefined.map` (the staging witness caught this).
    expect(seedFromExtraction({} as never)).toEqual({
      customer: null,
      lines: [],
    })
    expect(
      seedFromExtraction({ customer: { name: "X" } } as never),
    ).toEqual({ customer: { name: "X" }, lines: [] })
    expect(seedFromExtraction(undefined)).toEqual({
      customer: null,
      lines: [],
    })
  })
})

describe("draftReducer", () => {
  const base = seedFromExtraction(extraction)

  it("addLine appends a line with qty default 1", () => {
    const next = draftReducer(base, {
      type: "addLine",
      productRef: "Widget",
      productId: "p9",
    })
    expect(next.lines).toHaveLength(3)
    expect(next.lines[2]).toMatchObject({
      productRef: "Widget",
      productId: "p9",
      quantity: 1,
    })
  })

  it("removeLine drops the targeted line only", () => {
    const target = base.lines[0].lineId
    const next = draftReducer(base, { type: "removeLine", lineId: target })
    expect(next.lines).toHaveLength(1)
    expect(next.lines[0].productRef).toBe("Continental")
  })

  it("setQuantity clamps to a floor of 1", () => {
    const id = base.lines[0].lineId
    expect(
      draftReducer(base, { type: "setQuantity", lineId: id, quantity: 5 })
        .lines[0].quantity,
    ).toBe(5)
    expect(
      draftReducer(base, { type: "setQuantity", lineId: id, quantity: 0 })
        .lines[0].quantity,
    ).toBe(1)
  })

  it("setOverride sets a string value and clears on empty", () => {
    const id = base.lines[0].lineId
    const withOverride = draftReducer(base, {
      type: "setOverride",
      lineId: id,
      value: "1200.00",
    })
    expect(withOverride.lines[0].unitPriceOverride).toBe("1200.00")
    const cleared = draftReducer(withOverride, {
      type: "setOverride",
      lineId: id,
      value: "  ",
    })
    expect(cleared.lines[0].unitPriceOverride).toBeUndefined()
  })

  it("hydrate replaces the whole draft", () => {
    const other: QuoteDraft = { customer: null, lines: [] }
    expect(draftReducer(base, { type: "hydrate", draft: other })).toBe(other)
  })
})

describe("draftFromPersisted (reload round-trip)", () => {
  it("parses a persisted blob back into a draft", () => {
    const seeded = seedFromExtraction(extraction)
    const roundTrip = draftFromPersisted(
      JSON.parse(JSON.stringify(seeded)) as Record<string, unknown>,
    )
    expect(roundTrip).not.toBeNull()
    expect(roundTrip?.lines).toHaveLength(2)
    expect(roundTrip?.lines[0].productRef).toBe("Monticello")
    // stable line ids survive the round-trip
    expect(roundTrip?.lines[0].lineId).toBe(seeded.lines[0].lineId)
  })

  it("returns null for a missing / malformed blob", () => {
    expect(draftFromPersisted(null)).toBeNull()
    expect(draftFromPersisted({})).toBeNull()
    expect(draftFromPersisted({ lines: "nope" })).toBeNull()
  })

  it("skips malformed line entries but keeps valid ones", () => {
    const parsed = draftFromPersisted({
      customer: { name: "X" },
      lines: [
        { productRef: "Good", quantity: 4 },
        { quantity: 2 }, // no productRef → skipped
        null,
      ],
    })
    expect(parsed?.lines).toHaveLength(1)
    expect(parsed?.lines[0]).toMatchObject({ productRef: "Good", quantity: 4 })
  })
})

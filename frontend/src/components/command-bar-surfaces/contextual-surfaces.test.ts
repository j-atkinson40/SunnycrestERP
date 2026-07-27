/**
 * CONTEXTUAL_SURFACES map + surfacesForIntent (S-2, §4.3).
 *
 * Pins the summon-map behavior: intent-keying, the suppress-until-a-
 * product-resolves rule for the price-list reference, and the
 * nothing-flashes-on-empty rule for the quote preview.
 */

import { describe, expect, it } from "vitest"

import { surfacesForIntent } from "./contextual-surfaces"
import type { ExtractionContext } from "./types"

const base: ExtractionContext = {
  entryIntent: "quote",
  customer: null,
  lines: [],
  rawInput: "",
}

describe("surfacesForIntent", () => {
  it("yields no surfaces for a non-quote intent", () => {
    const s = surfacesForIntent("order", {
      ...base,
      entryIntent: "order",
      customer: { name: "Hopkins" },
      lines: [{ productRef: "Monticello", quantity: 1 }],
    })
    expect(s).toEqual([])
  })

  it("yields nothing for a wholly-empty quote draft (no flash)", () => {
    expect(surfacesForIntent("quote", base)).toEqual([])
  })

  it("shows the quote preview once a customer is committed; price-list still suppressed", () => {
    const s = surfacesForIntent("quote", {
      ...base,
      customer: { name: "Hopkins" },
    })
    expect(s.map((x) => x.widgetId)).toEqual(["surface.quote-preview"])
  })

  it("shows the price-list reference once a product resolves", () => {
    const s = surfacesForIntent("quote", {
      ...base,
      customer: { id: "cust-1", name: "Hopkins" },
      lines: [{ productRef: "Monticello", quantity: 3 }],
    })
    expect(s.map((x) => x.widgetId)).toEqual([
      "surface.quote-preview",
      "surface.price-list-reference",
    ])
    const plr = s.find((x) => x.widgetId === "surface.price-list-reference")!
    expect(plr.config).toEqual({
      products: ["Monticello"],
      customerId: "cust-1",
    })
  })

  it("passes the lifted draft into the quote-preview config", () => {
    const ctx: ExtractionContext = {
      ...base,
      customer: { id: "c9", name: "Murphy FH" },
      lines: [{ productRef: "Continental", quantity: 2 }],
    }
    const s = surfacesForIntent("quote", ctx)
    const preview = s.find((x) => x.widgetId === "surface.quote-preview")!
    expect(preview.config).toEqual({
      customer: { id: "c9", name: "Murphy FH" },
      lines: [{ productRef: "Continental", quantity: 2 }],
    })
    expect(preview.variantId).toBe("brief")
  })
})

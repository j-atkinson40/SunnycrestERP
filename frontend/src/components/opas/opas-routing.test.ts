/**
 * What a typed request opens. Rule-based; no model call.
 *
 * ⚠️ THE MIDDLE BRANCH IS THE RULING THAT CHANGED. An earlier dispatch said several
 * candidates produced a FILTERED LIST; it was withdrawn in favour of a NUMBERED PICK, per
 * the spec ("ask with a numbered pick") and the prototype's `.pick` button list.
 */
import { describe, expect, it } from "vitest"

import { isCatalogRequest, normalizeRequest, routeResolution } from "./opas-routing"

const c = (...ids: string[]) => ids.map((variant_template_id) => ({ variant_template_id }))

describe("isCatalogRequest — fixed phrases, no model", () => {
  it.each(["catalog", "the catalog", "Show The Catalog", "open the catalog", "products"])(
    "accepts %j",
    (phrase) => expect(isCatalogRequest(phrase)).toBe(true),
  )

  it("tolerates trailing punctuation and doubled spaces", () => {
    expect(isCatalogRequest("the catalog.")).toBe(true)
    expect(isCatalogRequest("the  catalog")).toBe(true)
    expect(isCatalogRequest("  THE CATALOG!  ")).toBe(true)
  })

  it("⚠️ does NOT swallow a product phrase that merely contains a catalog word", () => {
    // Without this, "bronze catalog vault" would open the list instead of resolving, and
    // the resolver would never see a phrase it could have answered.
    expect(isCatalogRequest("bronze catalog vault")).toBe(false)
    expect(isCatalogRequest("catalog of urns")).toBe(false)
  })

  it("normalizeRequest is exported so the rule is inspectable, not buried", () => {
    expect(normalizeRequest("  The  Catalog?? ")).toBe("the catalog")
  })
})

describe("routeResolution — the three branches", () => {
  it("one candidate opens the Product pane", () => {
    expect(routeResolution({ phrase: "x", candidates: c("v1"), discriminators: [] })).toEqual({
      kind: "product",
      variantTemplateId: "v1",
    })
  })

  it("several candidates open a NUMBERED PICK carrying every id and the discriminators", () => {
    expect(
      routeResolution({ phrase: "Bronze Triune", candidates: c("v1", "v2"), discriminators: ["form"] }),
    ).toEqual({ kind: "numbered-pick", candidateIds: ["v1", "v2"], discriminators: ["form"] })
  })

  it("⚠️ it never picks — all candidates survive, in order", () => {
    const r = routeResolution({ phrase: "x", candidates: c("a", "b", "c"), discriminators: [] })
    expect(r.kind).toBe("numbered-pick")
    expect(r.kind === "numbered-pick" && r.candidateIds).toEqual(["a", "b", "c"])
  })

  it("no candidates open the unfiltered list, carrying the phrase that did not match", () => {
    expect(routeResolution({ phrase: "zzz", candidates: [], discriminators: [] })).toEqual({
      kind: "product-list-unmatched",
      phrase: "zzz",
    })
  })
})

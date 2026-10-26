/**
 * Opening a record that is already open focuses it. Never a duplicate.
 *
 * ⚠️ THE RUNTIME ENUMERATION IS NOT REDUNDANT WITH THE TYPE, the same argument as
 * `pane-mode.test.ts`: `PANE_IDENTITY` is `Record<OpasPaneKind, …>`, which catches a
 * missing row at compile time only while `OpasPaneKind` is a literal union. Widen it to
 * `string` and the Record constraint goes vacuous. The list below is DATA, so widening
 * fails here.
 */
import { describe, expect, it } from "vitest"

import type { OpasPane, OpasPaneKind } from "@/contexts/opas-context"
import { PANE_IDENTITY, findDuplicate, paneIdentity } from "./pane-identity"

/** ⚠️ WRITTEN OUT, NOT DERIVED FROM `PANE_IDENTITY` — deriving the expected set from
 *  the thing under test makes the test assert nothing. */
const EVERY_KIND: readonly OpasPaneKind[] = [
  "capture",
  "product",
  "product-list",
  "order-list",
  "sales-order",
  "customer",
  "cemetery",
  "rulebook",
]

function pane(kind: OpasPaneKind, extra: Partial<OpasPane> = {}): Omit<OpasPane, "id"> {
  return { kind, label: "L", ...extra }
}

describe("every pane kind is classified", () => {
  it("has a row for each kind in the union, and no extras", () => {
    expect(Object.keys(PANE_IDENTITY).sort()).toEqual([...EVERY_KIND].sort())
  })

  it("the union has not been widened to string", () => {
    const widened: string[] = EVERY_KIND as unknown as string[]
    expect(widened.every((k) => typeof k === "string" && k.length > 0)).toBe(true)
    // ⚠️ A DELIBERATE COUNT, NOT A DERIVED ONE, AND THE REASON IS WHY IT CANNOT BE
    // `EVERY_KIND.length`. The test above already checks the list against the map;
    // this one exists to catch someone SHORTENING the list to make that pass. Derived
    // from the list it would be vacuous.
    //
    // ⚠️ AND IT IS THE "count travelling separately from the list" SHAPE CLAUDE.md
    // names, so it will go stale again: bumping it is part of adding a kind. 6 as of
    // 2026-10-24 when `customer` landed; **7 as of 2026-10-26** when `cemetery` did —
    // and it went red on the way, which is the guard doing its job rather than a
    // nuisance. There is no duplicate-free check elsewhere, so it is here — a list with
    // a repeat would satisfy both this and the map check. **8 as of 2026-10-26** when
    // `rulebook` landed.
    expect(new Set(widened).size).toBe(widened.length)
    expect(widened).toHaveLength(8)
  })
})

describe("what has an identity and what does not", () => {
  it("two captures are two orders and never dedupe", () => {
    // ⚠️ THE ONE THAT WOULD HURT. Deduping captures would hand the second order the
    // first one's half-typed text.
    expect(paneIdentity(pane("capture", { openingLine: "order for hopkins" }))).toBeNull()
    expect(paneIdentity(pane("capture"))).toBeNull()
  })

  it("a product pane is identified by its variant, and an empty one by nothing", () => {
    expect(paneIdentity(pane("product", { variantTemplateId: "v1" }))).toBe("product:v1")
    expect(paneIdentity(pane("product"))).toBeNull()
  })

  it("a sales order pane is identified by its order", () => {
    expect(paneIdentity(pane("sales-order", { salesOrderId: "o1" }))).toBe("order:o1")
    expect(paneIdentity(pane("sales-order"))).toBeNull()
    // ⚠️ A CUSTOMER IS REACHABLE THREE WAYS IN SLICE 1 — the bar, the funeral home link
    // on an order, and "the customer" with an order in front — so order -> customer ->
    // order -> customer is the ordinary walk. Without this row it leaves a stack.
    expect(paneIdentity(pane("customer", { customerId: "c1" }))).toBe("customer:c1")
    expect(paneIdentity(pane("customer"))).toBeNull()
    // ⚠️ AND THE CEMETERY, for the walk James gave with the 2026-10-26 slice: cemetery
    // -> an order -> back to the cemetery through the order's own link. Without this row
    // that last step leaves two St. Mary's on the desk.
    expect(paneIdentity(pane("cemetery", { cemeteryId: "m1" }))).toBe("cemetery:m1")
    expect(paneIdentity(pane("cemetery"))).toBeNull()
    // ⚠️ AND THE RULEBOOK IS A SINGLETON, so "rules" twice focuses one pane. Two copies
    // could disagree about which rules are off the moment one was edited.
    expect(paneIdentity(pane("rulebook"))).toBe("rulebook")
  })

  it("the order list is a singleton and the catalog is not", () => {
    expect(paneIdentity(pane("order-list"))).toBe("order-list")
    // ⚠️ `product-list` CARRIES TWO DIFFERENT LISTS under one kind — the catalog, and an
    // unmatched phrase with its own "nothing matched" line. Deduping on kind would make
    // an unmatched phrase raise the plain catalog and lose the phrase.
    //
    // ⚠️ IT CARRIED THREE UNTIL 2026-10-20: the third was a numbered pick, filtered to
    // the resolver's candidates. That surface is retired — the pick is above the bar
    // now — and `candidateIds` is gone from `OpasPane` with it.
    //
    // ⚠️ AND TWO BECAME ONE ON 2026-10-23. The other was an UNMATCHED-PHRASE catalog,
    // asserted here as `pane("product-list", { unmatchedPhrase: "zzz" })`. James ruled
    // the whole-catalog fallback out, so `unmatchedPhrase` is gone from `OpasPane` and
    // a product-list pane has exactly one shape. The surviving claim is the one that
    // still has two cases to tell apart: a product-list pane never dedupes by kind.
    expect(paneIdentity(pane("product-list"))).toBeNull()
  })
})

describe("findDuplicate", () => {
  const open: OpasPane[] = [
    { id: "p1", kind: "product", label: "Product", variantTemplateId: "v1" },
    { id: "p2", kind: "sales-order", label: "Sales order", salesOrderId: "o1" },
    { id: "p3", kind: "capture", label: "Order" },
  ]

  it("finds the open pane for the same record", () => {
    expect(findDuplicate(open, pane("product", { variantTemplateId: "v1" }))?.id).toBe("p1")
    expect(findDuplicate(open, pane("sales-order", { salesOrderId: "o1" }))?.id).toBe("p2")
  })

  it("finds nothing for a different record of the same kind", () => {
    expect(findDuplicate(open, pane("product", { variantTemplateId: "v2" }))).toBeUndefined()
    expect(findDuplicate(open, pane("sales-order", { salesOrderId: "o2" }))).toBeUndefined()
  })

  it("never matches a capture, even against an open capture", () => {
    expect(findDuplicate(open, pane("capture"))).toBeUndefined()
  })

  it("does not match a kind with no identity to one of the same kind", () => {
    // ⚠️ A KIND COMPARISON WOULD GET THIS WRONG. An identity-less product pane
    // duplicates nothing, including another identity-less product pane.
    const anonymous: OpasPane[] = [{ id: "x", kind: "product", label: "Product" }]
    expect(findDuplicate(anonymous, pane("product"))).toBeUndefined()
  })
})

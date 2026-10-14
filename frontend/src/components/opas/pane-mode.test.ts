/**
 * Entry vs info is a property of the pane TYPE, and every type has one.
 *
 * ⚠️ THE RUNTIME CHECK IS NOT REDUNDANT WITH THE TYPE. `PANE_MODE` is declared
 * `Record<OpasPaneKind, PaneMode>`, which catches a missing row at compile time — but
 * only while `OpasPaneKind` stays a literal union. Widen it to `string` in
 * `opas-context.tsx` (which a well-meaning "make this extensible" edit would do) and
 * the Record constraint becomes vacuous, the type check keeps passing, and a new kind
 * is silently unclassified. This file enumerates the union's members as DATA, so that
 * widening fails here.
 */
import { describe, expect, it } from "vitest"

import type { OpasPaneKind } from "@/contexts/opas-context"
import { PANE_MODE, isEntryPane, paneMode } from "./pane-mode"

/** ⚠️ WRITTEN OUT, NOT DERIVED FROM `PANE_MODE`. Deriving the expected set from the
 *  thing under test is the fixtures-modelled-on-the-implementation defect: the two
 *  would agree by construction and the test would assert nothing. */
const EVERY_KIND: readonly OpasPaneKind[] = [
  "capture",
  "product",
  "product-list",
  "order-list",
  "sales-order",
]

describe("every pane kind is classified", () => {
  it("has exactly these kinds and no others", () => {
    expect(Object.keys(PANE_MODE).sort()).toEqual([...EVERY_KIND].sort())
  })

  it.each(EVERY_KIND)("%s has a mode that is entry or info", (kind) => {
    expect(["entry", "info"]).toContain(paneMode(kind))
  })

  it("classifies nothing by accident — no kind is undefined", () => {
    for (const kind of EVERY_KIND) {
      expect(PANE_MODE[kind]).toBeDefined()
    }
  })
})

describe("the classification itself", () => {
  it("capture is an ENTRY pane — the director is putting something in", () => {
    expect(isEntryPane("capture")).toBe(true)
  })

  it.each(["product", "product-list", "order-list", "sales-order"] as const)(
    "%s is an INFO pane — the director is reading",
    (kind) => {
      expect(isEntryPane(kind)).toBe(false)
    },
  )

  it("EXACTLY ONE kind is entry today, and that is worth pinning", () => {
    // ⚠️ IF THIS GOES RED, THE QUESTION IS WHETHER THE BAR WAS WIRED TO THE NEW PANE.
    // An entry pane whose input is still its own text box would look fine and would
    // break the one-input ruling, and nothing else would notice.
    const entries = EVERY_KIND.filter(isEntryPane)
    expect(entries).toEqual(["capture"])
  })
})

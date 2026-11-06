/**
 * The menu is built from the same rule the server enforces.
 *
 * James signed in as the real Payroll-role user on production on 2026-11-06 and
 * saw Home, Bridgeable Map, Payroll, Financials, Agents, Production, Resale,
 * Knowledge Base and Settings — while the server returned 403 on all 551
 * endpoints behind them. The server refuses by `roles.limited_to_areas`; the
 * sidebar was deciding by `employee_profiles.functional_areas`, a different
 * concept on a different table. Hers was `[]`, and `filterByPermission` read
 * empty as "unrestricted".
 *
 * ⚠️ **THE BREAK TEST JAMES ASKED FOR IS `test_a_payroll_limited_nav_is_exactly_payroll`
 * COMPARED AS A SET**, plus its mirror: an unlimited user's nav must be
 * untouched. One without the other is half a test — a filter that returns
 * nothing passes the first and fails the second, and a filter that returns
 * everything passes the second and fails the first.
 */
import { describe, expect, it } from "vitest"

import {
  getNavigation,
  landingRouteForAreas,
  restrictNavToAreas,
  type NavigationConfig,
} from "./navigation-service"

/** The sunnycrest shape, measured on production 2026-11-06. */
const MODULES = new Set([
  "core", "daily_production_log", "driver_delivery", "inventory",
  "purchasing", "safety", "safety_management", "sales",
])
const EXTENSIONS = new Set([
  "disinterment_management", "funeral_home_coordination",
  "funeral_kanban_scheduler", "legacy_print_generator", "urn_sales",
])
const PAYROLL_PERMS = new Set(["payroll.view"])
const OFFICE_PERMS = new Set([
  "payroll.view", "ar.view", "customers.view", "safety.view", "invoice.approve",
])

function nav(perms: Set<string>, areas: Set<string>): NavigationConfig {
  return getNavigation("manufacturing", MODULES, perms, {}, areas, false, EXTENSIONS)
}

/** Every label in the config, flattened, as a set. */
function labels(cfg: NavigationConfig): Set<string> {
  const out = new Set<string>()
  const walk = (items: { label: string; children?: { label: string }[] }[]) => {
    for (const i of items) {
      out.add(i.label)
      if (i.children) walk(i.children as never)
    }
  }
  cfg.sections.forEach((s) => walk(s.items as never))
  return out
}

describe("a payroll-limited user", () => {
  it("sees exactly the Payroll item and nothing else", () => {
    // ⚠️ `functional_areas` is EMPTY here on purpose — that is the production
    // state that produced the bug. The restriction must hold regardless of it,
    // because it is no longer what decides.
    const restricted = restrictNavToAreas(nav(PAYROLL_PERMS, new Set()), ["payroll"])
    expect(labels(restricted)).toEqual(new Set(["Payroll"]))
  })

  it("is not rescued by functional_areas being populated either", () => {
    // The other direction of the same independence: a stale soft hint must not
    // widen her menu back out.
    const restricted = restrictNavToAreas(
      nav(PAYROLL_PERMS, new Set(["invoicing_ar", "production_log", "full_admin"])),
      ["payroll"],
    )
    expect(labels(restricted)).toEqual(new Set(["Payroll"]))
  })

  it("loses the six hubs James actually saw", () => {
    const got = labels(restrictNavToAreas(nav(PAYROLL_PERMS, new Set()), ["payroll"]))
    for (const gone of [
      "Home", "Bridgeable Map", "Financials", "Agents",
      "Production", "Resale", "Knowledge Base", "Settings",
    ]) {
      expect(got.has(gone)).toBe(false)
    }
  })

  it("lands on Payroll, never on Home", () => {
    expect(landingRouteForAreas(nav(PAYROLL_PERMS, new Set()), ["payroll"])).toBe("/payroll")
  })
})

describe("an unlimited user", () => {
  it("has a nav that is not merely equal but IDENTICAL", () => {
    // ⚠️ Reference equality, not deep equality. The restriction returns the
    // same object for an unlimited user, so no filtering bug can reach them —
    // a deep-equality assertion would still pass if the function rebuilt the
    // tree and silently dropped something on a later edit.
    const built = nav(OFFICE_PERMS, new Set(["invoicing_ar"]))
    expect(restrictNavToAreas(built, null)).toBe(built)
    expect(restrictNavToAreas(built, undefined)).toBe(built)
  })

  it("keeps every item an office user had before the change", () => {
    const built = nav(OFFICE_PERMS, new Set(["invoicing_ar", "production_log"]))
    expect(labels(restrictNavToAreas(built, null))).toEqual(labels(built))
  })

  it("gets no area landing redirect", () => {
    expect(landingRouteForAreas(nav(OFFICE_PERMS, new Set()), null)).toBeNull()
    expect(landingRouteForAreas(nav(OFFICE_PERMS, new Set()), undefined)).toBeNull()
  })
})

describe("the null/empty distinction", () => {
  it("treats [] as limited to NOTHING, not as unlimited", () => {
    // ⚠️ THE EXACT SHAPE OF THE ORIGINAL BUG, asserted as a test. No admin can
    // configure `[]` today; if one ever can, it must not mean "show her
    // everything", which is what the old `areas.size > 0` guard did.
    const restricted = restrictNavToAreas(nav(OFFICE_PERMS, new Set()), [])
    expect(labels(restricted)).toEqual(new Set())
    expect(restricted.sections).toEqual([])
  })

  it("returns null for a landing route when she can reach nothing", () => {
    // Better to leave her on the default and let her see the honest error than
    // to invent a route or loop.
    expect(landingRouteForAreas(nav(OFFICE_PERMS, new Set()), [])).toBeNull()
  })
})

describe("untagged items are denied, mirroring the server", () => {
  it("drops an item whose area is not in the allowed set", () => {
    const restricted = restrictNavToAreas(nav(OFFICE_PERMS, new Set()), ["some_other_area"])
    expect(labels(restricted)).toEqual(new Set())
  })

  it("admits the Payroll item only for a set containing payroll", () => {
    expect(labels(restrictNavToAreas(nav(PAYROLL_PERMS, new Set()), ["payroll"])))
      .toContain("Payroll")
    expect(labels(restrictNavToAreas(nav(PAYROLL_PERMS, new Set()), ["mfa_enroll"])))
      .not.toContain("Payroll")
  })
})

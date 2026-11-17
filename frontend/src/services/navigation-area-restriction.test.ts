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
import { readFileSync } from "node:fs"
import { resolve } from "node:path"

import { describe, expect, it } from "vitest"

import {
  getNavigation,
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

/** The same, as an admin. `isAdmin` is the sixth argument and the one that
 *  decides every `adminOnly` item, so it gets its own builder rather than a
 *  boolean threaded through the one above — a test that passed `true` by
 *  position would be the next person's puzzle. */
function adminNav(perms: Set<string>, areas: Set<string>): NavigationConfig {
  return getNavigation("manufacturing", MODULES, perms, {}, areas, true, EXTENSIONS)
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
  it("sees her area, plus Today — and nothing else", () => {
    // ⚠️ `functional_areas` is EMPTY here on purpose — that is the production
    // state that produced the bug. The restriction must hold regardless of it,
    // because it is no longer what decides.
    //
    // ⚠️ "Today" JOINED THIS SET ON 2026-11-16, and the claim is unchanged:
    // she sees her area and nothing from anyone else's. Measured that day, a
    // payroll-limited user landed on `/home`, held exactly one nav item, and
    // had NO WAY BACK to the note — navigate away once and the week's dues
    // line, her only route into the Focus, was unreachable until she signed in
    // again. `/home` is hers since Payroll 5a made the note a composed
    // surface. It is NOT the "Home" hub at `/dashboard`, which the six-hubs
    // test below still asserts is gone.
    const restricted = restrictNavToAreas(nav(PAYROLL_PERMS, new Set()), ["payroll"])
    expect(labels(restricted)).toEqual(new Set(["Today", "Payroll"]))
  })

  it("is not rescued by functional_areas being populated either", () => {
    // The other direction of the same independence: a stale soft hint must not
    // widen her menu back out.
    const restricted = restrictNavToAreas(
      nav(PAYROLL_PERMS, new Set(["invoicing_ar", "production_log", "full_admin"])),
      ["payroll"],
    )
    expect(labels(restricted)).toEqual(new Set(["Today", "Payroll"]))
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

})

describe("untagged items are denied, mirroring the server", () => {
  it("drops an item whose area is not in the allowed set", () => {
    // ⚠️ The dropping is the claim, and it is unchanged: nothing of the
    // office nav survives a user limited to an area it does not carry. Only
    // "Today" remains, which belongs to no area and is her way back to the
    // note — see the first test in this file.
    const restricted = restrictNavToAreas(nav(OFFICE_PERMS, new Set()), ["some_other_area"])
    expect(labels(restricted)).toEqual(new Set(["Today"]))
  })

  it("⚠️ gives a user limited to NOTHING no nav at all, not even Today", () => {
    // `[]` is "limited to nothing" and is a real, deliberate state — distinct
    // from `null`, which is unlimited. A user who reaches no area does not
    // acquire a nav item from the Today injection.
    expect(labels(restrictNavToAreas(nav(PAYROLL_PERMS, new Set()), []))).toEqual(
      new Set(),
    )
  })

  it("admits the Payroll item only for a set containing payroll", () => {
    expect(labels(restrictNavToAreas(nav(PAYROLL_PERMS, new Set()), ["payroll"])))
      .toContain("Payroll")
    expect(labels(restrictNavToAreas(nav(PAYROLL_PERMS, new Set()), ["mfa_enroll"])))
      .not.toContain("Payroll")
  })
})


describe("Payroll setup — admin-only AND area-tagged", () => {
  // Both gates are load-bearing and they are enforced by DIFFERENT functions,
  // which is why this needs four cases rather than one. `adminOnly` is checked
  // by `filterByPermission`; `area` is checked by `restrictNavToAreas`. Drop
  // either and one of these four flips.

  it("Susan does NOT see it — she is payroll-limited and not an admin", () => {
    // Two of the three endpoints behind the page are `require_admin`, so she
    // would arrive at three cards that all 403.
    const got = labels(restrictNavToAreas(nav(PAYROLL_PERMS, new Set()), ["payroll"]))
    expect(got.has("Payroll setup")).toBe(false)
    expect(got.has("Payroll")).toBe(true)
  })

  it("⚠️ a payroll-limited ADMIN DOES see it — this is what the area tag buys", () => {
    // The case the `area: "payroll"` tag exists for. Without the tag,
    // `restrictNavToAreas` denies it as untagged and an admin who happens to
    // be area-limited to payroll loses the page that turns payroll on.
    const got = labels(
      restrictNavToAreas(adminNav(PAYROLL_PERMS, new Set()), ["payroll"]),
    )
    expect(got.has("Payroll setup")).toBe(true)
    expect(got.has("Payroll")).toBe(true)
  })

  it("an unlimited admin sees it", () => {
    expect(labels(adminNav(OFFICE_PERMS, new Set())).has("Payroll setup")).toBe(true)
  })

  it("an unlimited NON-admin does not", () => {
    // The permission half, measured away from the area machinery entirely.
    expect(labels(nav(OFFICE_PERMS, new Set())).has("Payroll setup")).toBe(false)
  })

  it("⚠️ its href resolves to a route that EXISTS in App.tsx", () => {
    // ⚠️ CHECKED AGAINST THE ROUTER, NOT AGAINST ITSELF. An href asserted only
    // against a literal in this same file is CLAUDE.md §11 shape 9: 55 green
    // assertions pinned `/dispatch` as four widgets' target for four and a
    // half months, and `/dispatch` was never a route in any revision. The
    // expected value has to come from outside the check, so App.tsx is read.
    const flat: { label: string; href: string }[] = []
    adminNav(OFFICE_PERMS, new Set()).sections.forEach((sec) =>
      sec.items.forEach((i) => flat.push({ label: i.label, href: i.href })),
    )
    const href = flat.find((i) => i.label === "Payroll setup")?.href
    expect(href).toBeDefined()

    const appTsx = readFileSync(resolve(process.cwd(), "src/App.tsx"), "utf8")
    // ⚠️ A POSITIVE CONTROL ON THE READ, BEFORE THE RESULT IT VOUCHES FOR.
    // An unreadable or empty App.tsx would make the `toContain` below fail for
    // a reason that has nothing to do with the route — and an empty string
    // containing nothing looks exactly like a missing route.
    expect(appTsx.length).toBeGreaterThan(10_000)
    expect(appTsx).toContain('path="payroll"')
    // Routes are declared relative to the tenant root, so an href of
    // `/payroll/setup` is `path="payroll/setup"` in the tree.
    const relative = href!.replace(/^\//, "")
    expect(appTsx).toContain(`path="${relative}"`)
  })
})

/**
 * Who gets the sphere, and which shell — the three-outcome rule as a truth table.
 *
 * ⚠️ **THE `[]` ROW IS THE WHOLE REASON THIS FILE EXISTS.** `limited_to_areas`
 * has three states and two of them are falsey, so `if (limitedToAreas)` would
 * put the limited-to-nothing role in the ADMIN shell — the opposite of ruling
 * 3. The server has `allowed_area_grants` guarding the same distinction; this
 * is the client half.
 */
import { describe, expect, it } from "vitest"

import { isAreaLimited, mayUseOpas } from "./may-use-opas"

describe("isAreaLimited", () => {
  it.each([
    ["null — no limit ever set", null, false],
    ["undefined — not loaded, or absent from the payload", undefined, false],
    ["[] — limited to NOTHING, a real deliberate state", [], true],
    ['["payroll"] — limited to one area', ["payroll"], true],
    ['["payroll:view"] — a level-qualified grant', ["payroll:view"], true],
    ["two areas", ["payroll", "orders"], true],
  ] as const)("%s -> %s", (_name, value, expected) => {
    expect(isAreaLimited(value as string[] | null | undefined)).toBe(expected)
  })

  it("⚠️ an empty list and no list are OPPOSITE answers", () => {
    // Spelled out separately because this is the pair a truthiness check
    // collapses, and a table can be read without noticing the two rows differ.
    expect(isAreaLimited([])).toBe(true)
    expect(isAreaLimited(null)).toBe(false)
    expect(isAreaLimited([])).not.toBe(isAreaLimited(null))
  })
})

describe("mayUseOpas", () => {
  it("an admin may, limited or not", () => {
    expect(mayUseOpas(true, null)).toBe(true)
    expect(mayUseOpas(true, ["payroll"])).toBe(true)
  })

  it("an area-limited non-admin may — she has no other entrance", () => {
    // Ruling 2, 2026-11-17. Before this the gate was `isAdmin` alone, which in
    // the new shell would have left her with no sidebar, no command bar and no
    // sphere.
    expect(mayUseOpas(false, ["payroll"])).toBe(true)
    expect(mayUseOpas(false, [])).toBe(true)
  })

  it("an unlimited non-admin may NOT — nothing changed for her", () => {
    expect(mayUseOpas(false, null)).toBe(false)
    expect(mayUseOpas(false, undefined)).toBe(false)
  })
})

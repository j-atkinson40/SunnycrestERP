/**
 * The wizard's role step — the bug James found while trying to create Sue.
 *
 * Users → Add Employee fetched the tenant's real roles from `/roles` and then
 * threw away any role without a hardcoded entry in `ROLE_TILES`. The Payroll
 * role — seeded in every tenant by r223, active, carrying
 * `limited_to_areas: ["payroll"]` — was therefore unselectable, so the one
 * person the whole payroll arc exists for could not be given her role. A
 * presentation map was doing admission control.
 *
 * ⚠️ **THE RULING THESE PIN IS "ROLE_TILES IS PRESENTATION ONLY, NEVER AN
 * ALLOWLIST"**, and the test that matters is the generic one: a role with no
 * tile must appear. Asserting only that *Payroll* appears would pass if
 * someone "fixed" it by adding a `payroll:` tile, leaving the next role to
 * vanish on the day it ships.
 */
import { describe, expect, it } from "vitest"

import {
  buildWizardSubmission,
  filterWizardRoles,
  wizardOutcome,
} from "./EmployeeCreationWizard"

type R = Parameters<typeof filterWizardRoles>[0][number]

function role(over: Partial<R> & { slug: string }): R {
  return {
    id: `id-${over.slug}`,
    name: over.slug,
    description: null,
    is_system: true,
    is_active: true,
    permission_keys: [],
    limited_to_areas: null,
    ...over,
  }
}

const OFFICE = "office_management" as Parameters<typeof filterWizardRoles>[1]
const PRODUCTION = "production_delivery" as Parameters<typeof filterWizardRoles>[1]

describe("filterWizardRoles", () => {
  it("offers a role that has no tile — the ruling, stated generically", () => {
    const out = filterWizardRoles([role({ slug: "a_role_nobody_has_tiled" })], OFFICE)
    expect(out.map((r) => r.slug)).toEqual(["a_role_nobody_has_tiled"])
  })

  it("offers the payroll role, which is the case that was broken", () => {
    const out = filterWizardRoles(
      [role({ slug: "payroll", name: "Payroll", limited_to_areas: ["payroll"] })],
      OFFICE,
    )
    expect(out).toHaveLength(1)
    // the badge is rendered from this, so the data must survive the filter
    expect(out[0].limited_to_areas).toEqual(["payroll"])
  })

  it("still offers the tiled office roles — the fix did not widen by discarding the old list", () => {
    const out = filterWizardRoles(
      [role({ slug: "office_staff" }), role({ slug: "accounting" }), role({ slug: "manager" })],
      OFFICE,
    )
    expect(out.map((r) => r.slug).sort()).toEqual(["accounting", "manager", "office_staff"])
  })

  it("keeps admin and employee out", () => {
    const out = filterWizardRoles(
      [role({ slug: "admin" }), role({ slug: "employee" }), role({ slug: "office_staff" })],
      OFFICE,
    )
    expect(out.map((r) => r.slug)).toEqual(["office_staff"])
  })

  it("keeps non-system roles out — role creation belongs in Roles admin", () => {
    const out = filterWizardRoles([role({ slug: "something_bespoke", is_system: false })], OFFICE)
    expect(out).toEqual([])
  })

  it("routes tiled roles by track", () => {
    const rs = [role({ slug: "office_staff" }), role({ slug: "driver" })]
    expect(filterWizardRoles(rs, OFFICE).map((r) => r.slug)).toEqual(["office_staff"])
    expect(filterWizardRoles(rs, PRODUCTION).map((r) => r.slug)).toEqual(["driver"])
  })

  it("does NOT offer an untiled role on the production track", () => {
    // ⚠️ Deliberate asymmetry: the production track authenticates by username
    // and PIN, so a role has to declare itself as production-side with a tile.
    // Defaulting an unknown role into that track would put someone on a
    // credential path nobody chose for them.
    const out = filterWizardRoles([role({ slug: "a_role_nobody_has_tiled" })], PRODUCTION)
    expect(out).toEqual([])
  })

  it("is empty for an empty list, not throwing", () => {
    expect(filterWizardRoles([], OFFICE)).toEqual([])
  })
})


describe("buildWizardSubmission", () => {
  const common = {
    firstName: "Sue", lastName: "Accountant", roleId: "role-payroll",
    email: "sue@example.com", username: "sacct", pin: "1234",
    consoles: [] as string[],
  }

  it("the office track posts to the INVITE endpoint", () => {
    const { endpoint } = buildWizardSubmission({ ...common, track: OFFICE })
    expect(endpoint).toBe("/users/invite")
  })

  it("the office track sends no password and no credential of any kind", () => {
    const { payload } = buildWizardSubmission({ ...common, track: OFFICE })
    expect(Object.keys(payload).sort()).toEqual(
      ["email", "first_name", "last_name", "role_id"],
    )
    for (const k of ["password", "pin", "username", "hashed_password", "token"]) {
      expect(payload).not.toHaveProperty(k)
    }
  })

  it("the production track still creates directly, with username and PIN", () => {
    const { endpoint, payload } = buildWizardSubmission({ ...common, track: PRODUCTION })
    // ⚠️ Deliberately NOT the invite endpoint: a driver has no email to
    // invite, so this track creates the account. It carries a PIN, which is
    // a credential — but one the operator sets for a shared-tablet login,
    // which is the case ruling 4 explicitly left alone.
    expect(endpoint).toBe("/users")
    expect(payload).not.toHaveProperty("password")
    expect(payload.username).toBe("sacct")
    expect(payload.pin).toBe("1234")
  })

  it("the office track does not leak the production fields", () => {
    const { payload } = buildWizardSubmission({
      ...common, track: OFFICE, username: "leaked", pin: "9999",
    })
    expect(payload).not.toHaveProperty("username")
    expect(payload).not.toHaveProperty("pin")
    expect(payload).not.toHaveProperty("track")
  })
})


describe("wizardOutcome", () => {
  const base = { firstName: "Sue", lastName: "Accountant", email: " sue@example.com " }

  it("a FAILED send never reports success — the defect James's question found", () => {
    const o = wizardOutcome({ ...base, track: OFFICE, emailSent: false })
    expect(o.kind).toBe("error")
    expect(o.text).toContain("NOT be sent")
    expect(o.text).toContain("no link")
    // ⚠️ The old code fired BOTH toasts, and this is the assertion that
    // matters: the outcome must not also claim the invite went out.
    expect(o.text).not.toContain("Invite sent")
  })

  it("a successful send names the recipient", () => {
    const o = wizardOutcome({ ...base, track: OFFICE, emailSent: true })
    expect(o.kind).toBe("success")
    expect(o.text).toContain("sue@example.com")
    expect(o.text).not.toContain("NOT be sent")
  })

  it("an absent field is not treated as failure", () => {
    // An older server that does not report `email_sent` must not make every
    // invite cry wolf. Only an explicit `false` is a failure.
    const o = wizardOutcome({ ...base, track: OFFICE, emailSent: undefined })
    expect(o.kind).toBe("success")
  })

  it("the production track is unaffected by the email field", () => {
    for (const emailSent of [true, false, undefined]) {
      const o = wizardOutcome({ ...base, track: PRODUCTION, emailSent })
      expect(o.kind).toBe("success")
      expect(o.text).toBe("Sue Accountant added")
    }
  })

  it("exactly one outcome exists for every input — there is no both", () => {
    for (const track of [OFFICE, PRODUCTION]) {
      for (const emailSent of [true, false, undefined]) {
        const o = wizardOutcome({ ...base, track, emailSent })
        expect(["success", "error"]).toContain(o.kind)
        expect(o.text.length).toBeGreaterThan(0)
      }
    }
  })
})

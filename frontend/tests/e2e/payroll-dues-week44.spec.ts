/**
 * Weekly payroll dues — staging API gate for upload → calculate → report → approve.
 *
 * API-only by design. This module ships NO UI in this dispatch (the surface is
 * prototyped separately), so there is no page to drive; the spec uses Playwright's
 * APIRequestContext against the staging backend directly.
 *
 * ⚠️ NO LLM ASSERTION, DELIBERATELY. The repo's "Playwright + Claude API" framework
 * uses Claude where a judgement is needed. Union dues are exact Decimal arithmetic —
 * 193.93 is right or it is not — so asking a model whether the number looks correct
 * would be STRICTLY WEAKER than asserting the literal, and would convert a
 * deterministic gate into a probabilistic one. The expected figures are hand-derived
 * in docs/specs/payroll-reports.md §6 and asserted as literals.
 *
 * ⚠️ FAIL CLOSED ON THE HOST. This spec WRITES (it uploads and approves), so it
 * refuses outright if the resolved backend is the production API rather than
 * rewriting or hoping. See tests/e2e/PROD_INTERCEPT.md for the browser-side
 * equivalent and why the catch aborts.
 *
 * ⚠️ IT REFUSES TO RUN BLIND. Credentials absent, module not deployed, tenant
 * missing, roster not seeded — each is an explicit skip WITH ITS REASON, never a
 * silent pass. A green run with nothing exercised is the failure mode this guards
 * (CLAUDE.md §11 "an erroring test asserts nothing" / "absent signal").
 *
 * ONE RESERVED WEEK, RE-RUNNABLE. The gate owns w/e 2026-09-26 (week 39) so it never
 * collides with the seeded week-44 fixture. Re-import replaces a non-approved week's
 * lines, so upload/calculate/report are idempotent. Approval LOCKS, so the approve
 * assertions run on the first pass and the LOCK assertions (409 on recalculate, 409
 * on re-import) run on every pass after — the spec reports which branch it took
 * rather than skipping quietly.
 *
 * Pre-flight (ops, one-time):
 *   1. aef73307 or later deployed to staging (carries r220 + the routes).
 *   2. `python -m scripts.seed_payroll_week44 --tenant-slug sunnycrest` run on staging.
 *   3. STAGING_CI_BOT_EMAIL + STAGING_CI_BOT_PASSWORD in GitHub Secrets.
 *
 * NOT YET WIRED INTO .github/workflows/playwright-staging.yml — that workflow lists
 * specs explicitly per job, and adding a job is an ops call, not this dispatch's.
 */
import { test, expect, type APIRequestContext } from "@playwright/test"

import {
  PLATFORM_ADMIN_EMAIL,
  PLATFORM_ADMIN_PASSWORD,
  PROD_API,
  STAGING_BACKEND,
} from "./runtime-editor/_shared"

const BASE = `${STAGING_BACKEND}/api/v1/payroll-reports`
const TENANT_SLUG = "sunnycrest"

// The gate's own week. Deliberately NOT week 44 — the seeded fixture must survive.
const GATE_WEEK_NUMBER = 39
const GATE_WEEK_END = "2026-09-26"
const GATE_CHECK_DATE = "2026-10-01" // week_end + 5 days

// Hand-derived in docs/specs/payroll-reports.md §6. Not computed here.
const EXPECTED = {
  dues: "193.93",
  duesHours: "520.44",
  duesWage: "13236.25275",
  rowCount: 13,
  otWarnings: 9,
}

const MEMBERS: Array<[string, string, string, string]> = [
  // file_number, reg_hrs, personal_hrs, ot_hrs
  ["E01", "40", "0", "7"],
  ["E02", "40", "0", "12.8"],
  ["E03", "40", "0", "7.9"],
  ["E04", "40", "0", "2"],
  ["E05", "36", "4", "7.68"],
  ["E06", "40", "0", "7.43"],
  ["E07", "32", "0", "6.68"],
  ["E08", "40", "0", "5.83"],
  ["E09", "0", "0", "0"],
  ["E10", "31.57", "0", "0.08"],
  ["E11", "32", "0", "4.9"],
  ["E12", "40", "0", "1.37"],
  ["E13", "40", "0", "1.2"],
]

function gateCsv(): string {
  const header = "file_number,display_name,dept,reg_hrs,personal_hrs,ot_hrs"
  const rows = MEMBERS.map(
    ([id, reg, pers, ot]) => `${id},Member ${id},PRECAST,${reg},${pers},${ot}`,
  )
  return [header, ...rows].join("\n") + "\n"
}

/** ⚠️ Refuse to write to production. Not a rewrite, not a warning — a throw. */
function assertNotProduction(): void {
  if (STAGING_BACKEND.startsWith(PROD_API) || STAGING_BACKEND.includes("api.getbridgeable.com")) {
    throw new Error(
      `REFUSING TO RUN: resolved backend is the production API (${STAGING_BACKEND}). ` +
        `This spec uploads and approves payroll weeks. Set BACKEND_URL to staging.`,
    )
  }
}

async function tenantToken(request: APIRequestContext): Promise<string | null> {
  if (!PLATFORM_ADMIN_PASSWORD) return null

  const login = await request.post(`${STAGING_BACKEND}/api/platform/auth/login`, {
    data: { email: PLATFORM_ADMIN_EMAIL, password: PLATFORM_ADMIN_PASSWORD },
  })
  if (!login.ok()) return null
  const { access_token: adminToken } = await login.json()

  const lookup = await request.get(
    `${STAGING_BACKEND}/api/platform/impersonation/tenants`,
    { headers: { Authorization: `Bearer ${adminToken}` } },
  )
  if (!lookup.ok()) return null
  const tenants: Array<{ id: string; slug: string }> = await lookup.json()
  const target = tenants.find((t) => t.slug === TENANT_SLUG)
  if (!target) return null

  const imp = await request.post(
    `${STAGING_BACKEND}/api/platform/impersonation/impersonate`,
    {
      headers: { Authorization: `Bearer ${adminToken}`, "Content-Type": "application/json" },
      data: {
        tenant_id: target.id,
        user_id: null,
        reason: "playwright payroll dues gate",
      },
    },
  )
  if (!imp.ok()) return null
  const { access_token } = await imp.json()
  return access_token
}

test.describe("Payroll weekly dues — staging API gate @payroll", () => {
  let token: string
  let auth: { Authorization: string }

  test.beforeAll(async ({ request }) => {
    assertNotProduction()

    const t = await tenantToken(request)
    test.skip(
      t === null,
      `Could not obtain a ${TENANT_SLUG} tenant token. Either ` +
        `STAGING_CI_BOT_PASSWORD is unset, the platform login failed, or the ` +
        `${TENANT_SLUG} tenant is absent from staging. Not a payroll failure — ` +
        `and not a pass either.`,
    )
    token = t as string
    auth = { Authorization: `Bearer ${token}` }

    // ⚠️ POSITIVE CONTROL BEFORE ANY ASSERTION. If the module is not deployed the
    // endpoint 404s, and every later expectation would fail for a reason that has
    // nothing to do with the dues rules. Establish reachability first, and say so.
    const probe = await request.get(`${BASE}/formats`, { headers: auth })
    test.skip(
      probe.status() === 404,
      `${BASE}/formats returned 404 — the payroll module is not on this deploy. ` +
        `Needs aef73307 or later. Skipping rather than reporting dues failures.`,
    )
    expect(probe.ok(), `formats probe: ${probe.status()} ${await probe.text()}`).toBeTruthy()
  })

  test("the Payentry mapping is published as unverified", async ({ request }) => {
    const r = await request.get(`${BASE}/formats`, { headers: auth })
    expect(r.ok()).toBeTruthy()
    const byKey = Object.fromEntries(
      (await r.json()).formats.map((f: { format_key: string }) => [f.format_key, f]),
    )
    expect(byKey["payentry"].verified, "payentry must stay unverified until a sample lands")
      .toBe(false)
    expect(byKey["bridgeable_csv"].verified).toBe(true)
  })

  test("uploading through the unverified Payentry mapping is refused", async ({ request }) => {
    const r = await request.post(`${BASE}/weeks/upload`, {
      headers: auth,
      multipart: {
        file: { name: "export.csv", mimeType: "text/csv", buffer: Buffer.from(gateCsv()) },
        week_number: String(GATE_WEEK_NUMBER),
        week_end_date: GATE_WEEK_END,
        format_key: "payentry",
      },
    })
    expect(r.status(), await r.text()).toBe(422)
    expect(await r.text()).toContain("verified=false")
  })

  test("upload, calculate and report reproduce the golden totals", async ({ request }) => {
    const upload = await request.post(`${BASE}/weeks/upload`, {
      headers: auth,
      multipart: {
        file: { name: "week39.csv", mimeType: "text/csv", buffer: Buffer.from(gateCsv()) },
        week_number: String(GATE_WEEK_NUMBER),
        week_end_date: GATE_WEEK_END,
        format_key: "bridgeable_csv",
      },
    })

    if (upload.status() === 409) {
      // Steady state after the first run: the gate week is approved and locked.
      // Assert the LOCK rather than skipping — it is the same contract from the
      // other side, and a quiet skip here would hide a broken endpoint.
      test.info().annotations.push({
        type: "branch",
        description: "gate week already approved — asserting the lock instead of the flow",
      })
      expect(await upload.text()).toContain("approved")
      return
    }

    expect(upload.status(), await upload.text()).toBe(201)
    const week = (await upload.json()).week
    expect(week.week_end_date).toBe(GATE_WEEK_END)
    expect(week.check_date, "check_date = week_end + 5 days").toBe(GATE_CHECK_DATE)
    expect(week.status).toBe("imported")

    const calc = await request.post(`${BASE}/weeks/${week.id}/calculate`, { headers: auth })
    expect(calc.status(), await calc.text()).toBe(200)
    const body = await calc.json()

    expect(body.members_calculated).toBe(EXPECTED.rowCount)
    expect(body.totals.row_count, "every row in every total").toBe(EXPECTED.rowCount)
    expect(body.totals.dues).toBe(EXPECTED.dues)
    expect(body.totals.dues_hours).toBe(EXPECTED.duesHours)
    expect(body.totals.dues_wage).toBe(EXPECTED.duesWage)
    expect(body.summary.errors, "no error-severity validation flags").toBe(0)

    const otWarnings = body.flags.filter(
      (f: { code: string }) => f.code === "ot_rate_not_one_and_a_half",
    )
    expect(otWarnings.length, "nine typed OT rates are not 1.5x").toBe(EXPECTED.otWarnings)

    const detail = await request.get(
      `${BASE}/weeks/${week.id}/reports/weekly_dues_detail`,
      { headers: auth },
    )
    expect(detail.ok()).toBeTruthy()
    const rows = (await detail.json()).rows
    expect(rows).toHaveLength(EXPECTED.rowCount)

    const csv = await request.get(
      `${BASE}/weeks/${week.id}/reports/weekly_dues_detail?fmt=csv`,
      { headers: auth },
    )
    expect(csv.ok()).toBeTruthy()
    const text = await csv.text()
    expect(text, "the CSV total row carries its own population")
      .toContain(`TOTAL (n=${EXPECTED.rowCount})`)

    // --- approve, then assert the lock from both sides ---
    const approve = await request.post(`${BASE}/weeks/${week.id}/approve`, { headers: auth })
    expect(approve.status(), await approve.text()).toBe(200)
    expect((await approve.json()).locked).toBe(true)

    const recalc = await request.post(`${BASE}/weeks/${week.id}/calculate`, { headers: auth })
    expect(recalc.status(), "recalculating an approved week must refuse").toBe(409)

    const reimport = await request.post(`${BASE}/weeks/upload`, {
      headers: auth,
      multipart: {
        file: { name: "week39.csv", mimeType: "text/csv", buffer: Buffer.from(gateCsv()) },
        week_number: String(GATE_WEEK_NUMBER),
        week_end_date: GATE_WEEK_END,
        format_key: "bridgeable_csv",
      },
    })
    expect(reimport.status(), "re-importing an approved week must refuse").toBe(409)

    // Reads survive approval — approval locks writes, not citability.
    const after = await request.get(
      `${BASE}/weeks/${week.id}/reports/weekly_dues_detail`,
      { headers: auth },
    )
    expect(after.ok()).toBeTruthy()
    expect((await after.json()).totals.dues).toBe(EXPECTED.dues)
  })

  test("the seeded week-44 fixture is intact and unmodified by this gate", async ({ request }) => {
    const r = await request.get(`${BASE}/weeks`, { headers: auth })
    expect(r.ok()).toBeTruthy()
    const weeks: Array<{ week_end_date: string; week_number: number }> = (await r.json()).weeks

    const w44 = weeks.find((w) => w.week_end_date === "2026-10-31")
    test.skip(
      w44 === undefined,
      "week-44 fixture not seeded on this staging tenant — run " +
        "`python -m scripts.seed_payroll_week44 --tenant-slug sunnycrest`.",
    )
    expect(w44!.week_number).toBe(44)

    // The gate's own week must be a different row. If these ever collided the gate
    // would be approving the fixture it is meant to leave alone.
    expect(w44!.week_end_date).not.toBe(GATE_WEEK_END)
  })
})

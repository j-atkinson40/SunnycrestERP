/**
 * Vacation pay — Payroll 5c, FROM SIGN-IN, unmocked.
 *
 * ⚠️ **NOTHING HAD EVER COMPUTED A VACATION FIGURE.** Measured 2026-11-23: the
 * rulebook keys, the engine and the goldens all existed, and no code path in
 * `app/` or `scripts/` called any of them — no table, no writer, no surface.
 * So there is no "did the old path still work" here; the only question a walk
 * can answer is whether the new one works at all, through the real app against
 * the real server.
 *
 * What it walks:
 *   1. the note line — "Hunt's vacation Nov 16–20: 40 hours to pay"
 *   2. it opens the vacation pay Focus, scoped to that vacation
 *   3. the working: $33,062.74 over 1,512.36 h, truncated to 4dp → $22.5116,
 *      and 900.46 + 75.00 — James's golden, on screen
 *   4. approve → both lines land on the week, read back from the server
 *   5. the vacation pane, the Focus's other entrance, shows the pay
 *   6. read-only: a view-only payroll user reads the working and cannot approve
 *
 * ⚠️ **STEP 3 IS THE ONE THAT COULD NOT BE FAKED**, and it is the cent that
 * truncation moves: rounding the rate to 4dp gives 900.47 and so does leaving
 * it unrounded. Only truncation gives 900.46, which is Hunt's real line.
 *
 * ⚠️ **IT SEEDS AND UNDOES ITS OWN FIXTURE.** No API records a hire date or a
 * prior-year workbook figure for somebody who does not exist, so the walk
 * makes the person, and removes them.
 *
 * Run it with both servers up:
 *
 *   SECRET_KEY=… DATABASE_URL=…note5a_clean uvicorn app.main:app --port 8000
 *   npx vite --port 5199
 *   PW_BASE_URL=http://localhost:5199 SECRET_KEY=… DATABASE_URL=… \
 *     npx playwright test -c playwright.local.config.ts vacation-pay-walkthrough
 */
import { execFileSync } from "node:child_process"

import { expect, test, type Page } from "@playwright/test"

const EMAIL = process.env.PW_WALK_EMAIL ?? "susan.walkthrough@testco.example.com"
const PASSWORD = process.env.PW_WALK_PASSWORD ?? "WalkThrough123!"
const SLUG = process.env.PW_SLUG ?? "testco"
const SHOTS = "tests/local/shots"
const PY =
  process.env.PW_PY ?? "/Users/Jimmy1/Projects/SunnycrestERP-5a/backend/.venv/bin/python"
const BACKEND = process.env.PW_BACKEND ?? "/Users/Jimmy1/Projects/SunnycrestERP-setup/backend"

/** Hunt's figures, from the accountant's workbook Vac Calc tab (§11.13). */
const GROSS = "33062.74"
const PRIOR_HOURS = "1512.36"

test.describe.configure({ mode: "serial" })

function sql(snippet: string): string {
  return execFileSync(PY, ["-c", snippet], {
    cwd: BACKEND, encoding: "utf8", env: { ...process.env },
  }).trim()
}

const PRELUDE = [
  "from datetime import date, timedelta",
  "from decimal import Decimal as D",
  "import uuid",
  "from sqlalchemy import text",
  "from app.database import SessionLocal",
  "db = SessionLocal()",
  "C = 'staging-test-001'",
].join("\n")

function py(body: string): string {
  return `${PRELUDE}\ntry:\n${body.split("\n").map((l) => `    ${l}`).join("\n")}\nfinally:\n    db.close()`
}

async function asSusan(page: Page) {
  await page.goto(`/?slug=${SLUG}`)
  await page.getByLabel(/email/i).fill(EMAIL)
  await page.getByLabel(/password/i).fill(PASSWORD)
  await page.getByRole("button", { name: /sign in/i }).click()
  await page.waitForURL(/\/(home|note)/, { timeout: 30_000 })
}

async function shot(page: Page, name: string) {
  await page.screenshot({ path: `${SHOTS}/${name}.png`, fullPage: false })
}

/** ⚠️ Every request must stay on localhost — this walk WRITES. */
function pinToLocalhost(page: Page): string[] {
  const offsite: string[] = []
  page.on("request", (r) => {
    const h = new URL(r.url()).hostname
    if (h !== "localhost" && h !== "127.0.0.1") offsite.push(r.url())
  })
  return offsite
}

/** The fixture: a union member with a hire date, the workbook's prior-year
 *  figures, a 40-hour allowance, and a vacation whose week has come up. */
function seed(): string {
  return sql(py(
    "from app.models.payroll_report import (PayrollReportEmployee,\n"
    + "    PayrollPriorYearFigures, PayrollVacationEntitlement, PayrollVacation)\n"
    + "db.execute(text(\"DELETE FROM payroll_vacation_payments WHERE vacation_id IN \"\n"
    + "    \"(SELECT v.id FROM payroll_vacations v JOIN payroll_report_employees e \"\n"
    + "    \" ON e.id=v.employee_id WHERE e.payentry_file_number='WALK-VAC')\"))\n"
    + "db.execute(text(\"DELETE FROM payroll_vacations WHERE employee_id IN \"\n"
    + "    \"(SELECT id FROM payroll_report_employees WHERE payentry_file_number='WALK-VAC')\"))\n"
    + "for t in ('payroll_vacation_entitlements','payroll_prior_year_figures'):\n"
    + "    db.execute(text(f\"DELETE FROM {t} WHERE employee_id IN \"\n"
    + "        \"(SELECT id FROM payroll_report_employees WHERE payentry_file_number='WALK-VAC')\"))\n"
    + "db.execute(text(\"DELETE FROM payroll_report_employees WHERE payentry_file_number='WALK-VAC'\"))\n"
    + "eid = str(uuid.uuid4())\n"
    + "db.add(PayrollReportEmployee(id=eid, tenant_id=C,\n"
    + "    payentry_file_number='WALK-VAC', display_name='Hunt, Walkthrough',\n"
    + "    is_union_member=True, hire_date=date(2014, 1, 6)))\n"
    // ⚠️ FLUSHED BEFORE THE DEPENDENT ROWS. Without it the prior-year figures
    // insert against an employee id the database has not seen, and the FK
    // refuses — correctly.
    + "db.flush()\n"
    + `db.add(PayrollPriorYearFigures(tenant_id=C, employee_id=eid, year=2025,\n`
    + `    gross=D('${GROSS}'), hours=D('${PRIOR_HOURS}'), source='2025 Vac Calc tab'))\n`
    + "db.add(PayrollVacationEntitlement(tenant_id=C, employee_id=eid, year=2026,\n"
    + "    hours=D('40'), source='agreement, 2026'))\n"
    + "vid = str(uuid.uuid4())\n"
    + "# ⚠️ A REAL MONDAY-TO-FRIDAY WEEK, INSIDE THE NOTE'S 7-DAY WINDOW. My\n"
    + "# first fixture used today for both ends and the screenshot read\n"
    + "# 'Nov 23 - Nov 23', which is evidence of the fixture rather than of a\n"
    + "# vacation. The line appears when the WEEK comes up, not when the pick\n"
    + "# was made, so it starts within the window rather than today exactly.\n"
    + "mon = date.today() + timedelta(days=(7 - date.today().weekday()) % 7 or 7)\n"
    + "mon = mon if (mon - date.today()).days <= 7 else date.today()\n"
    + "db.add(PayrollVacation(id=vid, tenant_id=C, employee_id=eid,\n"
    + "    start_date=mon, end_date=mon + timedelta(days=4),\n"
    + "    hours=D('40'), status='scheduled', source='union pick'))\n"
    + "db.commit()\n"
    + "print(f'{eid} {vid}')",
  ))
}

function teardown(): string {
  return sql(py(
    "n = db.execute(text(\"DELETE FROM payroll_vacation_payments WHERE vacation_id IN \"\n"
    + "    \"(SELECT v.id FROM payroll_vacations v JOIN payroll_report_employees e \"\n"
    + "    \" ON e.id=v.employee_id WHERE e.payentry_file_number='WALK-VAC')\")).rowcount\n"
    + "m = db.execute(text(\"DELETE FROM payroll_vacations WHERE employee_id IN \"\n"
    + "    \"(SELECT id FROM payroll_report_employees WHERE payentry_file_number='WALK-VAC')\")).rowcount\n"
    + "for t in ('payroll_vacation_entitlements','payroll_prior_year_figures'):\n"
    + "    db.execute(text(f\"DELETE FROM {t} WHERE employee_id IN \"\n"
    + "        \"(SELECT id FROM payroll_report_employees WHERE payentry_file_number='WALK-VAC')\"))\n"
    + "k = db.execute(text(\"DELETE FROM payroll_report_employees WHERE payentry_file_number='WALK-VAC'\")).rowcount\n"
    + "db.commit()\n"
    + "print(f'{n} payments, {m} vacations, {k} people')",
  ))
}

let VACATION_ID = ""

test("1 · the note asks, and the line opens the Focus on that vacation", async ({
  page,
}) => {
  const offsite = pinToLocalhost(page)
  const ids = seed()
  VACATION_ID = ids.split(" ")[1]
  console.log(`[walk] seeded vacation ${VACATION_ID}`)

  await asSusan(page)

  // ⚠️ THE NOTE LINE IS ONE OF THE FOCUS'S TWO ENTRANCES. CLAUDE.md §1a: a
  // prompt fragment surfaces the decision AND carries the entrance, scoped.
  const line = page.getByTestId("prose-payroll_vacation_pay")
  await expect(line).toBeVisible({ timeout: 20_000 })
  await expect(line).toContainText(/Hunt/)
  await expect(line).toContainText(/40 hours to pay/)
  await shot(page, "v01-note-vacation-line")

  // ⚠️ The link names the ACT, not the surface.
  const open = page.getByTestId("prose-open-payroll_vacation_pay")
  await expect(open).toContainText(/Work out the pay/)
  await open.click()

  await expect(page.getByTestId("vacation-pay-core")).toBeVisible({ timeout: 20_000 })
  // ⚠️ SCOPED, not merely opened. The id in the URL is the vacation's.
  await expect(page).toHaveURL(new RegExp(`vacation_id=${VACATION_ID}`))
  expect(offsite, `requests left localhost:\n${offsite.join("\n")}`).toEqual([])
})


test("2 · the working shows WHERE the rate came from, and it is 900.46 + 75.00", async ({
  page,
}) => {
  // ⚠️ **THE STEP THAT COULD NOT BE FAKED.** Rounding the rate to 4dp gives
  // 900.47; so does leaving it unrounded. Only truncation gives 900.46.
  const offsite = pinToLocalhost(page)
  await asSusan(page)
  await page.goto(`/home?focus=vacation-pay&vacation_id=${VACATION_ID}`)
  await expect(page.getByTestId("vacation-pay-core")).toBeVisible({ timeout: 20_000 })

  const working = page.getByTestId("vacation-pay-working")
  await expect(working).toBeVisible({ timeout: 20_000 })
  // The derivation, not just the number.
  await expect(working).toContainText(`$${GROSS}`)
  await expect(working).toContainText("1512.36 hours")
  await expect(working).toContainText("truncated to 4 decimals")
  await expect(page.getByTestId("vacation-pay-rate")).toHaveText("$22.5116")
  // The two lines, separately.
  const parts = page.getByTestId("vacation-pay-parts")
  await expect(parts).toContainText("900.46")
  await expect(parts).toContainText("75.00")
  await shot(page, "v02-the-working")

  // Step 1 of the Focus: 1, 2 or 3 checks, and the split re-reads the server.
  await page.getByTestId("vacation-pay-checks-2").click()
  await expect(page.getByTestId("vacation-pay-parts").locator("tbody tr"))
    .toHaveCount(2, { timeout: 20_000 })
  await shot(page, "v03-split-over-two-checks")
  await page.getByTestId("vacation-pay-checks-1").click()
  await expect(page.getByTestId("vacation-pay-parts").locator("tbody tr"))
    .toHaveCount(1, { timeout: 20_000 })

  expect(offsite, `requests left localhost:\n${offsite.join("\n")}`).toEqual([])
})


test("3 · approving writes BOTH lines, read back from the server", async ({ page }) => {
  const offsite = pinToLocalhost(page)
  await asSusan(page)
  await page.goto(`/home?focus=vacation-pay&vacation_id=${VACATION_ID}`)
  await expect(page.getByTestId("vacation-pay-working")).toBeVisible({ timeout: 20_000 })

  await page.getByTestId("vacation-pay-approve").click()
  await expect(page.getByTestId("vacation-pay-approved")).toBeVisible({ timeout: 30_000 })
  await shot(page, "v04-approved")

  // ⚠️ READ THE SERVER, NOT THE SCREEN. The screen renders whatever it is
  // given, which is how a never-working upload shipped green for an arc.
  const stored = sql(py(
    "r = db.execute(text(\"SELECT vac_pay, vac_bonus, part_index, part_count, \"\n"
    + "    \"rate FROM payroll_vacation_payments WHERE vacation_id=:v\"),\n"
    + `    {'v': '${VACATION_ID}'}).fetchall()\n`
    + "print('; '.join(f'{x[0]}/{x[1]} part {x[2]} of {x[3]} at {x[4]}' for x in r))",
  ))
  console.log(`[walk] the server holds: ${stored}`)
  expect(stored).toBe("900.46/75.00 part 1 of 1 at 22.5116")

  const status = sql(py(
    `print(db.execute(text("SELECT status FROM payroll_vacations WHERE id=:v"),\n`
    + `    {'v': '${VACATION_ID}'}).scalar())`,
  ))
  expect(status).toBe("paid")
  expect(offsite, `requests left localhost:\n${offsite.join("\n")}`).toEqual([])
})


test("4 · the note line WITHDRAWS, because approving is its end transition", async ({
  page,
}) => {
  // ⚠️ A prompt declares how it ends and then actually ends. A line that
  // keeps asking after the thing is done is how a note stops being read.
  const offsite = pinToLocalhost(page)
  await asSusan(page)
  await expect(page.getByTestId("prose-region")).toBeAttached({ timeout: 20_000 })
  await expect(page.getByTestId("prose-payroll_vacation_pay")).toHaveCount(0)
  await shot(page, "v05-line-withdrawn")
  expect(offsite, `requests left localhost:\n${offsite.join("\n")}`).toEqual([])
})


test("5 · the walk leaves the fixture as it found it", async () => {
  const undone = teardown()
  console.log(`[walk] undone: ${undone}`)
  // ⚠️ NON-ZERO, so the teardown cannot pass by having run against nothing.
  expect(undone).toMatch(/^[1-9]\d* payments, [1-9]\d* vacations, [1-9]\d* people$/)
})

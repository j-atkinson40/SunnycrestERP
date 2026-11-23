/**
 * The employee-status row — FROM SIGN-IN, unmocked.
 *
 * ⚠️ **THIS IS THE FIRST TIME `payroll_status` HAS EVER BEEN WRITTEN FROM A
 * SCREEN.** `r234` added the columns; measured on production 2026-11-21,
 * **0 of 30** employees carried a value, because no endpoint and no surface
 * could set one. So there is no "did the existing path still work" to check
 * here — the only question a walk can answer is whether the new one works at
 * all, through the real app, against the real server.
 *
 * What it walks:
 *   1. sign in, open the weekly Focus, open a member pane
 *   2. the Status row reads "Not recorded" and says what that costs
 *   3. record "Left" with a past date and a reason — a real PUT
 *   4. the row re-reads from the server and shows the history
 *   5. the union form's line 1 stops counting checks, which is the payoff
 *   6. the same pane read-only: no editor, and the permission named
 *
 * ⚠️ **STEP 5 IS WHY THE FEATURE EXISTS AND IS THE ONLY STEP THAT COULD NOT
 * BE FAKED.** The R-115 counts line 1 from checks while no status exists
 * anywhere in the tenant and says so on the form. One recorded status flips
 * it to counting membership. Two Focuses, one write between them.
 *
 * ⚠️ **IT UNDOES ITS OWN WRITE, AND SAYS SO.** A status change is a record and
 * has no API that removes it — correctly. The teardown deletes the row and
 * nulls the two columns through the same database the server is using, so the
 * local fixture is left as it was found. Nothing here is reversible through
 * the UI, which is the point of the table.
 *
 * Run it with both servers up and the fixture seeded:
 *
 *   SECRET_KEY=… DATABASE_URL=…note5a_clean python scripts/seed_week44_walkthrough.py
 *   uvicorn app.main:app --port 8000
 *   npx vite --port 5199
 *   npx playwright test -c playwright.local.config.ts employee-status-walkthrough
 *
 * Screenshots land in `tests/local/shots/` and are committed — a walk whose
 * evidence is deleted is a claim with no auditable basis.
 */
import { execFileSync } from "node:child_process"

import { expect, test, type Page } from "@playwright/test"

const EMAIL = process.env.PW_WALK_EMAIL ?? "susan.walkthrough@testco.example.com"
const PASSWORD = process.env.PW_WALK_PASSWORD ?? "WalkThrough123!"
const SLUG = process.env.PW_SLUG ?? "testco"
const WEEK_ID = process.env.PW_WEEK_ID ?? ""
const SHOTS = "tests/local/shots"
const PY =
  process.env.PW_PY ?? "/Users/Jimmy1/Projects/SunnycrestERP-5a/backend/.venv/bin/python"
const BACKEND = process.env.PW_BACKEND ?? "/Users/Jimmy1/Projects/SunnycrestERP-setup/backend"

/** The date recorded by the walk. In the past, because the server refuses a
 *  future `since` — and a leaving date is a past fact by definition. */
const SINCE = "2026-06-25"
const REASON = "termination date from Payentry (walk-through)"

test.describe.configure({ mode: "serial" })

test.beforeAll(() => {
  expect(WEEK_ID, "PW_WEEK_ID must be the week id printed by the seed").not.toBe("")
})

function sql(snippet: string): string {
  return execFileSync(PY, ["-c", snippet], {
    cwd: BACKEND,
    encoding: "utf8",
    env: { ...process.env },
  }).trim()
}

const PRELUDE = [
  "from sqlalchemy import text",
  "from app.database import SessionLocal",
  "db = SessionLocal()",
  "C = 'staging-test-001'",
].join("\n")

function py(body: string): string {
  return `${PRELUDE}\ntry:\n${body
    .split("\n")
    .map((l) => `    ${l}`)
    .join("\n")}\nfinally:\n    db.close()`
}

/** Every status the tenant holds, so the walk can prove it started from none. */
function statusesInTenant(): string {
  return sql(
    py(
      "rows = db.execute(text(\"SELECT payentry_file_number, payroll_status, " +
        "payroll_status_since FROM payroll_report_employees WHERE tenant_id=:c " +
        "AND payroll_status IS NOT NULL ORDER BY 1\"), {'c': C}).fetchall()\n" +
        "print(len(rows), rows)",
    ),
  )
}

async function signIn(page: Page) {
  await page.goto(`/?slug=${SLUG}`)
  await page.getByLabel(/email/i).fill(EMAIL)
  await page.getByLabel(/password/i).fill(PASSWORD)
  await page.getByRole("button", { name: /sign in/i }).click()
  await page.waitForURL(/\/(home|note)/, { timeout: 30_000 })
}

/** ⚠️ **EVERY REQUEST MUST GO TO LOCALHOST.** CLAUDE.md §11 records an e2e
 *  suite that forwarded to production on a rewrite failure, held back only by
 *  a dead credential. This walk writes, so it checks rather than assumes. */
function pinToLocalhost(page: Page): string[] {
  const offsite: string[] = []
  page.on("request", (r) => {
    const h = new URL(r.url()).hostname
    if (h !== "localhost" && h !== "127.0.0.1") offsite.push(r.url())
  })
  return offsite
}

async function openMemberPane(page: Page) {
  await page.goto(`/home?focus=weekly-payroll&week_id=${WEEK_ID}`)
  await expect(page.getByTestId("week-table")).toBeVisible({ timeout: 30_000 })
  // The first member row the week has; the walk is about the row, not a person.
  const row = page.locator('[data-testid^="week-row-"]').first()
  await row.click()
  await expect(page.locator('[data-testid^="payroll-pane-member-"]')).toBeVisible({
    timeout: 20_000,
  })
}


test("1 · the row reads NOT RECORDED, and says what that costs", async ({ page }) => {
  const offsite = pinToLocalhost(page)

  // ⚠️ THE PRECONDITION IS MEASURED, NOT ASSUMED. If the tenant already held
  // a status the walk would be starting from the wrong world and step 5 would
  // prove nothing — and it would look exactly like a pass.
  const before = statusesInTenant()
  console.log(`[walk] statuses in testco before: ${before}`)
  expect(before.startsWith("0 "), `testco already holds statuses: ${before}`).toBe(true)

  await signIn(page)
  await openMemberPane(page)

  const row = page.getByTestId("employee-status-row")
  await expect(row).toBeVisible({ timeout: 20_000 })
  await expect(page.getByTestId("employee-status-value")).toHaveText("Not recorded")
  await expect(row).toContainText(/counts line 1 from who had a check that month/i)
  await expect(page.getByTestId("employee-status-change")).toHaveText("Record")
  // Nothing to show yet, and no toggle pretending there is.
  await expect(page.getByTestId("employee-status-history-toggle")).toHaveCount(0)

  // ⚠️ **THE PANE MUST STILL FIT, AND NO OTHER CHECK CAN SEE THIS.** The row
  // shipped with its button on a line of its own below a three-line
  // explanation; the member pane, which had always fit, overflowed its clip
  // and BOTH this button and the long-standing Timecard button went below the
  // fold — with no scrollbar, because the pane stack is `absolute inset-0
  // overflow-hidden` and clips the body's scrollbar away too. Every unit test
  // and every walk step passed, because Playwright and testing-library both
  // scroll an element into view before clicking it. Found by reading the
  // screenshot; pinned here by geometry so it cannot come back.
  //
  // ⚠️ **MEASURE AGAINST THE CLIPPING ANCESTOR, NOT THE PANE.** The first
  // version of this guard compared each button against the PANE's own box and
  // could not fail: `boundingBox()` reports the element's laid-out geometry,
  // which grows with its content, while the painted output is cut by the
  // stack's `absolute inset-0 overflow-hidden`. Break-tested with a 160px
  // spacer — the pane's reported bottom moved from 703 to 863 and the guard
  // stayed green, which is a check satisfied by the damage it detects.
  const clip = (await page
    .locator('[data-slot="payroll-pane-stack"]')
    .boundingBox())!
  // ⚠️ **THE PANE ITSELF MUST FIT THE CLIP — not every control inside it.**
  // Those are different requirements and only the first is achievable: the
  // pane's body is a scroll container, so content below the fold is fine
  // PROVIDED the pane's own box is inside the clip, because that is what
  // keeps its scrollbar painted. A pane taller than the clip is the bad case:
  // the body scrolls and the scrollbar is cut away with the content.
  const paneBox = (await page
    .locator('[data-testid^="payroll-pane-member-"]')
    .boundingBox())!
  console.log(
    `[walk] pane bottom ${Math.round(paneBox.y + paneBox.height)} vs the ` +
      `clip's bottom ${Math.round(clip.y + clip.height)}`,
  )
  expect(
    paneBox.y + paneBox.height,
    "the pane is painted outside its host's clip, so its body scrolls with " +
      "no visible scrollbar and nothing says there is more below",
  ).toBeLessThanOrEqual(Math.ceil(clip.y + clip.height))

  // And the row's own value and action are above the fold, which is the part
  // this feature is responsible for.
  for (const id of ["employee-status-value", "employee-status-change"]) {
    const box = (await page.getByTestId(id).boundingBox())!
    console.log(`[walk] ${id} bottom ${Math.round(box.y + box.height)}`)
    expect(
      box.y + box.height,
      `${id} is below the pane's visible region`,
    ).toBeLessThanOrEqual(Math.ceil(clip.y + clip.height))
  }

  await page.screenshot({ path: `${SHOTS}/s01-not-recorded.png`, fullPage: false })
  expect(offsite, `requests left localhost:\n${offsite.join("\n")}`).toEqual([])
})


test("2 · recording a status is a real PUT, and the row re-reads it", async ({ page }) => {
  const offsite = pinToLocalhost(page)
  const writes: string[] = []
  page.on("request", (r) => {
    if (r.method() === "PUT" && r.url().includes("/status")) {
      writes.push(`${r.method()} ${new URL(r.url()).pathname}`)
    }
  })

  await signIn(page)
  await openMemberPane(page)
  await page.getByTestId("employee-status-change").click()

  const editor = page.getByTestId("employee-status-editor")
  await expect(editor).toBeVisible()
  // ⚠️ THE PICKER REFUSES A FUTURE DATE. The line-1 rule only asks whether a
  // status began before the month, so a future date would drop the member
  // from months already filed.
  const max = await page.getByTestId("employee-status-since").getAttribute("max")
  console.log(`[walk] the since picker's max is ${max}`)
  expect(max).toMatch(/^\d{4}-\d{2}-\d{2}$/)

  // Nothing submittable until there is a date AND a reason.
  await expect(page.getByTestId("employee-status-save")).toBeDisabled()
  await page.getByTestId("employee-status-select").selectOption("left")
  await page.getByTestId("employee-status-since").fill(SINCE)
  await expect(page.getByTestId("employee-status-save")).toBeDisabled()
  await page.getByTestId("employee-status-reason").fill(REASON)
  await expect(page.getByTestId("employee-status-save")).toBeEnabled()
  await page.screenshot({ path: `${SHOTS}/s02-editor-filled.png`, fullPage: false })

  await page.getByTestId("employee-status-save").click()

  // ⚠️ WAIT FOR THE SERVER'S ANSWER ON SCREEN, not for the click to return.
  await expect(page.getByTestId("employee-status-value")).toHaveText(
    "Left · since Jun 25, 2026",
    { timeout: 20_000 },
  )
  await expect(page.getByTestId("employee-status-message")).toHaveCount(0)
  expect(writes, "no PUT reached the server").toEqual([
    expect.stringMatching(/^PUT \/api\/v1\/payroll-reports\/employees\/.+\/status$/),
  ])

  // The history is the point of the table: old → new, who, when, why.
  await page.getByTestId("employee-status-history-toggle").click()
  const history = page.getByTestId("employee-status-history")
  await expect(history).toContainText("Left since Jun 25, 2026")
  await expect(history).toContainText("first recorded")
  await expect(history).toContainText(REASON)
  await page.screenshot({ path: `${SHOTS}/s03-recorded-with-history.png`, fullPage: false })

  // ⚠️ READ THE SERVER BACK, NOT THE UI. The UI renders whatever it is given,
  // and that is exactly how a never-working upload shipped green for an arc.
  const after = statusesInTenant()
  console.log(`[walk] statuses in testco after: ${after}`)
  expect(after.startsWith("1 ")).toBe(true)
  expect(after).toContain("left")
  expect(after).toContain("2026, 6, 25")

  const audited = sql(
    py(
      "n = db.execute(text(\"SELECT count(*) FROM payroll_employee_status_changes \"\n" +
        "    \"WHERE tenant_id=:c AND reason=:r AND changed_by_user_id IS NOT NULL\"),\n" +
        `    {'c': C, 'r': ${JSON.stringify(REASON)}}).scalar()\n` +
        "print(n)",
    ),
  )
  console.log(`[walk] history rows carrying an author: ${audited}`)
  expect(audited).toBe("1")

  expect(offsite, `requests left localhost:\n${offsite.join("\n")}`).toEqual([])
})


test("2b · the timecard pane carries the row too — the non-union entrance", async ({
  page,
}) => {
  // ⚠️ **HALF THE SCOPE LIVES HERE AND THE REST OF THE WALK NEVER OPENS IT.**
  // The union member pane is the union entrance; the timecard pane is how a
  // non-union person is reached, and James asked for the row in both. A walk
  // that proved only the first would have read as proving the feature.
  const offsite = pinToLocalhost(page)
  await signIn(page)
  await openMemberPane(page)
  await page.getByTestId("pane-open-timecard").click()

  const pane = page.locator('[data-testid^="payroll-pane-timecard-"]')
  await expect(pane).toBeVisible({ timeout: 20_000 })
  // ⚠️ THE ROW IS AT THE TOP OF THIS PANE, NOT THE BOTTOM, because a person
  // with no hours is exactly whose status wants recording — a row that
  // appeared only alongside a populated timecard would be missing from every
  // instance of the situation it exists for.
  const row = pane.getByTestId("employee-status-row")
  await expect(row).toBeVisible()
  await expect(pane.getByTestId("employee-status-value")).toHaveText(
    "Left · since Jun 25, 2026",
  )

  const clip = (await page
    .locator('[data-slot="payroll-pane-stack"]')
    .boundingBox())!
  const paneBox = (await pane.boundingBox())!
  console.log(
    `[walk] timecard pane bottom ${Math.round(paneBox.y + paneBox.height)} vs ` +
      `the clip's bottom ${Math.round(clip.y + clip.height)}`,
  )
  expect(paneBox.y + paneBox.height).toBeLessThanOrEqual(
    Math.ceil(clip.y + clip.height),
  )

  await page.screenshot({ path: `${SHOTS}/s03b-timecard-pane.png`, fullPage: false })
  expect(offsite, `requests left localhost:\n${offsite.join("\n")}`).toEqual([])
})


test("3 · the union form stops counting line 1 from checks", async ({ page }) => {
  // ⚠️ **THE PAYOFF, AND THE ONLY STEP THAT COULD NOT BE FAKED.** Step 2's
  // write is the only thing between the two readings.
  const offsite = pinToLocalhost(page)
  await signIn(page)

  const period = sql(
    py(
      "from app.services.payroll.r115_schedule import current_form_period\n"
      + "from datetime import date\n"
      + "y, m = current_form_period(date.today())\n"
      + "print(f'{y}-{m:02d}')",
    ),
  )
  await page.goto(`/home?focus=union-form&period=${period}`)
  await expect(page.getByTestId("union-form-core")).toBeVisible({ timeout: 30_000 })
  await expect(page.getByTestId("union-form-lines")).toBeVisible()

  const core = page.getByTestId("union-form-core")
  const text = (await core.innerText()).toLowerCase()
  console.log(`[walk] the form's line-1 basis wording mentions "check": ${text.includes("check")}`)
  // The fallback sentence is gone, because a status now exists in the tenant.
  await expect(core).not.toContainText(/counted from who had a check/i)
  await core.screenshot({ path: `${SHOTS}/s04-union-form-basis.png` })

  const basis = sql(
    py(
      "from app.services.payroll import r115_form\n"
      + "from app.services.payroll.rules import DEFAULT_RULES\n"
      + "from app.services.payroll.r115_schedule import current_form_period\n"
      + "from datetime import date\n"
      + "y, m = current_form_period(date.today())\n"
      + "d = r115_form.build_lines(db, tenant_id=C, year=y, month=m, rules=DEFAULT_RULES)\n"
      + "print(d['unit']['basis'])",
    ),
  )
  console.log(`[walk] line 1's basis on the server: ${basis}`)
  expect(basis).toBe("payroll_status")

  expect(offsite, `requests left localhost:\n${offsite.join("\n")}`).toEqual([])
})


test("4 · read-only: no editor, and the permission named", async ({ page }) => {
  // ⚠️ A SECOND USER, NOT A FLAG. `readOnly` is the dispatcher's answer, keyed
  // on `payroll.approve`; a walk that set a prop would be testing the prop.
  const offsite = pinToLocalhost(page)
  const viewer = sql(
    py(
      "import uuid\n"
      + "from app.core.security import hash_password as H\n"
      + "from app.models.role import Role\n"
      + "from app.models.role_permission import RolePermission\n"
      + "from app.models.user import User\n"
      + "slug = 'walk-status-viewonly'\n"
      + "for (rid,) in db.execute(text(\"SELECT id FROM roles WHERE company_id=:c AND slug=:s\"), {'c': C, 's': slug}).fetchall():\n"
      + "    db.execute(text('DELETE FROM role_permissions WHERE role_id=:r'), {'r': rid})\n"
      + "    db.execute(text('DELETE FROM audit_logs WHERE user_id=:u'), {'u': slug})\n"
      + "    db.execute(text('DELETE FROM users WHERE id=:u'), {'u': slug})\n"
      + "    db.execute(text('DELETE FROM roles WHERE id=:r'), {'r': rid})\n"
      + "db.execute(text('DELETE FROM audit_logs WHERE user_id=:u'), {'u': slug})\n"
      + "db.execute(text('DELETE FROM users WHERE id=:u'), {'u': slug})\n"
      + "rid = str(uuid.uuid4())\n"
      + "db.add(Role(id=rid, company_id=C, name=slug, slug=slug, is_system=False, is_active=True))\n"
      + "db.flush()\n"
      + "db.add(RolePermission(id=str(uuid.uuid4()), role_id=rid, permission_key='payroll.view'))\n"
      + "db.add(User(id=slug, email='walk.viewonly@testco.example.com', hashed_password=H('WalkThrough123!'),\n"
      + "            first_name='View', last_name='Only', company_id=C, role_id=rid, is_active=True))\n"
      + "db.commit()\n"
      + "print('walk.viewonly@testco.example.com')",
    ),
  )
  console.log(`[walk] a view-only payroll user: ${viewer}`)

  await page.goto(`/?slug=${SLUG}`)
  await page.getByLabel(/email/i).fill(viewer)
  await page.getByLabel(/password/i).fill("WalkThrough123!")
  await page.getByRole("button", { name: /sign in/i }).click()
  await page.waitForURL(/\/(home|note)/, { timeout: 30_000 })

  await openMemberPane(page)
  const row = page.getByTestId("employee-status-row")
  await expect(row).toBeVisible({ timeout: 20_000 })
  // It READS — a look-only reviewer still sees the fact and its history.
  await expect(page.getByTestId("employee-status-value")).toHaveText(
    "Left · since Jun 25, 2026",
  )
  await expect(page.getByTestId("employee-status-history-toggle")).toBeVisible()
  // And it cannot change it, and says what would be needed.
  await expect(page.getByTestId("employee-status-change")).toHaveCount(0)
  await expect(page.getByTestId("employee-status-editor")).toHaveCount(0)
  await expect(row).toContainText("payroll.approve")
  await page.screenshot({ path: `${SHOTS}/s05-read-only.png`, fullPage: false })

  expect(offsite, `requests left localhost:\n${offsite.join("\n")}`).toEqual([])
})


test("5 · the walk leaves the fixture as it found it", async () => {
  // ⚠️ **THERE IS NO API FOR THIS, AND THERE SHOULD NOT BE.** A status change
  // is a record; removing one is a database operation a person does knowing
  // what they are removing. The walk's own write is the only thing undone.
  const left = sql(
    py(
      "n = db.execute(text('DELETE FROM payroll_employee_status_changes WHERE tenant_id=:c'), {'c': C}).rowcount\n"
      + "m = db.execute(text(\"UPDATE payroll_report_employees SET payroll_status=NULL, \"\n"
      + "    \"payroll_status_since=NULL WHERE tenant_id=:c AND payroll_status IS NOT NULL\"), {'c': C}).rowcount\n"
      + "for (rid,) in db.execute(text(\"SELECT id FROM roles WHERE company_id=:c AND slug='walk-status-viewonly'\"), {'c': C}).fetchall():\n"
      + "    db.execute(text('DELETE FROM role_permissions WHERE role_id=:r'), {'r': rid})\n"
      + "    db.execute(text(\"DELETE FROM audit_logs WHERE user_id='walk-status-viewonly'\"))\n"
      + "    db.execute(text(\"DELETE FROM users WHERE id='walk-status-viewonly'\"))\n"
      + "    db.execute(text('DELETE FROM roles WHERE id=:r'), {'r': rid})\n"
      + "db.commit()\n"
      + "print(f'{n} history rows, {m} employees')",
    ),
  )
  console.log(`[walk] undone: ${left}`)
  // ⚠️ NON-ZERO, so the teardown cannot pass by having run against nothing.
  expect(left).toMatch(/^[1-9]\d* history rows, [1-9]\d* employees$/)
  expect(statusesInTenant().startsWith("0 ")).toBe(true)
})

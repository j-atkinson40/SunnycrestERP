/**
 * Payroll 5b walk-through — the union form, FROM SIGN-IN, unmocked.
 *
 * ⚠️ **IT SIGNS IN AND IT TOUCHES NO MOCK.** Every figure on screen comes from
 * the register rows the walk-through seed wrote, through the real endpoints.
 * The PR C walk caught three defects the suite could not — an entry that
 * opened nothing, typing that did nothing, a placeholder naming the wrong
 * area — and all three were visible only to something driving the real app.
 *
 * ⚠️ **THE STALENESS STEP CHANGES THE DATA MID-WALK.** That is the point of
 * the copies record and cannot be shown any other way: a copy is taken, a
 * figure moves underneath it, and the form must say so. The change is made by
 * a short python script against the same database the server is using —
 * unmocked, and reversed in the same step.
 *
 * Run it with both servers up and the fixture seeded:
 *
 *   SECRET_KEY=… DATABASE_URL=…note5a_clean python scripts/seed_week44_walkthrough.py
 *   uvicorn app.main:app --port 8000
 *   VITE_API_URL=http://127.0.0.1:8000 npx vite --port 5199
 *   npx playwright test -c playwright.local.config.ts union-form-walkthrough
 *
 * ⚠️ Screenshots land in `tests/local/shots/` and are committed, because a
 * walk-through whose evidence is deleted is a claim with no auditable basis.
 */
import { execFileSync } from "node:child_process"

import { expect, test } from "@playwright/test"

const EMAIL = process.env.PW_WALK_EMAIL ?? "susan.walkthrough@testco.example.com"
const PASSWORD = process.env.PW_WALK_PASSWORD ?? "WalkThrough123!"
const SLUG = process.env.PW_SLUG ?? "testco"
const SHOTS = "tests/local/shots"
const PY =
  process.env.PW_PY ?? "/Users/Jimmy1/Projects/SunnycrestERP-5a/backend/.venv/bin/python"
const BACKEND = process.env.PW_BACKEND ?? "/Users/Jimmy1/Projects/SunnycrestERP-setup/backend"

test.describe.configure({ mode: "serial" })

/** Run a short python snippet against the same database the server uses.
 *
 *  ⚠️ **THE WALK CHANGES REAL DATA, SO IT SAYS SO LOUDLY.** This is how the
 *  staleness notice is shown at all — no API adds a register check — and the
 *  alternative was to mock the figures, which would have made the one step
 *  that matters prove nothing. */
function sql(snippet: string): string {
  return execFileSync(PY, ["-c", snippet], {
    cwd: BACKEND,
    encoding: "utf8",
    env: { ...process.env },
  }).trim()
}

const PRELUDE = [
  "from datetime import date",
  "from decimal import Decimal as D",
  "import uuid",
  "from sqlalchemy import text",
  "from app.database import SessionLocal",
  "from app.services.payroll.r115_schedule import current_form_period, check_dates_in",
  "db = SessionLocal()",
  "T = 'staging-test-001'",
  "Y, M = current_form_period(date.today())",
].join("\n")

/**
 * ⚠️ **THE WALK ESTABLISHES ITS OWN STARTING STATE, BECAUSE IT CHANGES THE
 * DATABASE.** Its second run failed on the "no copies yet" control — the
 * first run's printed copy was still there. A walk that only passes on a
 * freshly seeded database is a walk that silently stops being repeatable,
 * which is the shape that blanked the note during PR C: a suite leaving
 * state behind and the next reader paying for it.
 *
 * This clears only what the walk itself creates: the month's copies and its
 * form. The register rows the seed wrote are left alone, because they are
 * the fixture rather than the walk's litter.
 */
test.beforeAll(() => {
  const cleared = sql(
    `${PRELUDE}
db.execute(text("DELETE FROM outgoing_copies WHERE tenant_id=:t AND document_kind='r115'"), {"t": T})
db.execute(text("DELETE FROM payroll_union_forms_r115 WHERE tenant_id=:t"), {"t": T})
db.commit(); print('cleared')`,
  )
  if (cleared !== "cleared") throw new Error(`could not reset the walk: ${cleared}`)
})

/** Photograph the FORM, not the viewport.
 *
 * ⚠️ **THE PAGE SHOT WAS SHOWING THE WRONG THING.** The Focus is a dialog
 * with its own scroll, so `fullPage` captured a viewport in which the title,
 * the stage and the copies section had scrolled off the top — the evidence
 * for the steps about copies did not contain any copies. PR C lost three
 * steps to exactly this: an assertion passing while the artifact showed
 * something else. An element screenshot captures the form whole. */
async function shotForm(page: import("@playwright/test").Page, name: string) {
  await page.getByTestId("union-form-core").screenshot({ path: `${SHOTS}/${name}.png` })
}

async function signIn(page: import("@playwright/test").Page) {
  await page.goto(`/?slug=${SLUG}`)
  await page.getByLabel(/email/i).fill(EMAIL)
  await page.getByLabel(/password/i).fill(PASSWORD)
  await page.getByRole("button", { name: /sign in/i }).click()
  await page.waitForURL(/\/(home|note)/, { timeout: 30_000 })
}

/** Open the union form from the NOTE, which is one of its two entrances. */
async function openFromNote(page: import("@playwright/test").Page) {
  await signIn(page)
  const line = page.getByTestId("prose-payroll_union_form_due")
  await expect(line).toBeVisible({ timeout: 20_000 })
  await page.getByTestId("prose-open-payroll_union_form_due").click()
  // ⚠️ WAIT FOR THE FORM ITSELF, not for the URL. PR C's walk passed three
  // steps while photographing a page that had navigated and not rendered.
  await expect(page.getByTestId("union-form-core")).toBeVisible({ timeout: 20_000 })
}

test("1 · the note carries the union form line, and it opens the form", async ({ page }) => {
  await signIn(page)

  const line = page.getByTestId("prose-payroll_union_form_due")
  await expect(line).toBeVisible({ timeout: 20_000 })
  // The sentence names the month and says what is being asked for.
  await expect(line).toContainText(/union form/i)
  await page.screenshot({ path: `${SHOTS}/u01-note-union-line.png`, fullPage: true })

  // ⚠️ The link names the ACT, not the surface — PR #40's wording fix.
  const open = page.getByTestId("prose-open-payroll_union_form_due")
  await expect(open).not.toContainText(/^Open Union form$/)

  await open.click()
  await expect(page.getByTestId("union-form-core")).toBeVisible({ timeout: 20_000 })
  await expect(page.getByTestId("union-form-lines")).toBeVisible()
  await shotForm(page, "u02-form-opened")
})

test("2 · the form shows every numbered line, with 8 and 9 blank", async ({ page }) => {
  await openFromNote(page)

  const numbers = await page
    .locator("[data-testid^='line-']")
    .evaluateAll((els) => els.map((e) => e.getAttribute("data-line-number")))
  expect(numbers).toEqual(["1", "2", "3", "4", "5", "6", "7", "8", "9", ""])

  // ⚠️ Line 4 is the EARNINGS; the money is the un-numbered Total Remittance.
  // The two are different figures in this fixture, so a swap cannot pass.
  const earnings = await page.getByTestId("value-total_earnings").innerText()
  const remittance = await page.getByTestId("value-total_remittance").innerText()
  expect(earnings).not.toEqual(remittance)
  expect(earnings).toBe("13950.00")
  expect(remittance).toBe("214.25")

  // Blank, not 0.00.
  expect(await page.getByTestId("value-lump_sum").innerText()).toBe("")
  expect(await page.getByTestId("value-misc").innerText()).toBe("")
  expect(await page.getByTestId("value-initiation_fees").innerText()).toBe("0.00")

  await shotForm(page, "u03-lines-in-order")
})

test("3 · printing records a copy, and the copies line appears", async ({ page }) => {
  await openFromNote(page)

  // No copies yet — the control that makes step 3's assertion mean something.
  await expect(page.getByTestId("union-form-copies")).toHaveCount(0)

  // ⚠️ The print dialog would block the browser, so `window.print` is replaced
  // for the walk. The REQUEST that records the copy is untouched, which is the
  // behaviour under test — the dialog is the browser's, not ours.
  await page.evaluate(() => {
    window.print = () => {}
  })
  await page.getByTestId("union-form-print").click()

  const copies = page.getByTestId("union-form-copies")
  await expect(copies).toBeVisible({ timeout: 20_000 })
  await expect(copies).toContainText("Printed by Susan")
  // ⚠️ THE HONEST CLAUSE. A print is not a delivery.
  await expect(copies).toContainText("where it went after isn't known")
  await expect(copies).not.toContainText(/mailed|delivered/i)
  await shotForm(page, "u04-printed-copy")
})

test("4 · start the month, approve, then mark sent WITH A HOW", async ({ page }) => {
  await openFromNote(page)

  // ⚠️ **THE MONTH HAS TO BE STARTED FIRST, AND THE WALK DID NOT KNOW THAT.**
  // Its first version clicked Approve straight away and timed out — there is
  // no form to approve until somebody creates one from the register. The
  // screenshot showed the figures with a "Start this month's form" button
  // where Approve was expected, which is the walk doing its job: the order of
  // the real acts was wrong in my head and right on the screen.
  const start = page.getByTestId("union-form-build")
  await expect(start).toBeVisible({ timeout: 20_000 })
  await start.click()
  await expect(page.getByTestId("union-form-approve")).toBeVisible({ timeout: 20_000 })
  await shotForm(page, "u05a-form-started")

  await page.getByTestId("union-form-approve").click()
  await expect(page.getByTestId("union-form-stage")).toContainText("Approved", {
    timeout: 20_000,
  })
  await shotForm(page, "u05-approved")

  await page.getByTestId("union-form-mark-sent").click()
  // ⚠️ IT WILL NOT PROCEED WITHOUT THE HOW. "Sent" with no method is a claim
  // nobody can follow up, which is the whole value of recording it.
  await expect(page.getByTestId("union-form-mark-sent-confirm")).toBeDisabled()

  await page.getByTestId("union-form-how").fill("mailed with check 4521")
  await shotForm(page, "u06-asking-how")
  await page.getByTestId("union-form-mark-sent-confirm").click()

  await expect(page.getByTestId("union-form-stage")).toContainText("Sent", {
    timeout: 20_000,
  })
  const copies = page.getByTestId("union-form-copies")
  await expect(copies).toContainText("Marked sent by Susan")
  await expect(copies).toContainText("mailed with check 4521")
  // The earlier print is still listed — a form that does not say it is the
  // second copy this month invites a second filing.
  await expect(copies).toContainText("Printed by Susan")
  await shotForm(page, "u07-marked-sent")
})

test("5 · once sent, the note line withdraws itself", async ({ page }) => {
  /** ⚠️ **THE WALK EXPECTED THE LINE TO STILL BE THERE AND IT WAS NOT —
   *  WHICH IS THE PRODUCT BEING RIGHT.** The fragment's declared end
   *  transition is the form being SENT, not approved, so marking it sent in
   *  step 4 ends the prompt. Step 5's first version opened the form from the
   *  note and timed out looking for a line that had correctly gone.
   *
   *  Asserted rather than worked around: a prompt that keeps asking after
   *  the thing is done is the defect PR #38 existed to fix, and nothing else
   *  in this walk would notice if the end transition stopped firing. */
  await signIn(page)
  await expect(page.getByTestId("prose-payroll_union_form_due")).toHaveCount(0)
  await page.screenshot({ path: `${SHOTS}/u08-line-withdrawn.png`, fullPage: true })
})

test("6 · a figure moves, and the copy says it no longer matches", async ({ page }) => {
  // ⚠️ OPENED BY URL, because the note line has correctly gone (step 5). The
  // month is SENT, which is the state a reader is most likely to be looking
  // at when the data moves underneath them.
  await signIn(page)
  const period = sql(`${PRELUDE}\nprint(f"{Y}-{M:02d}")`)
  await page.goto(`/home?focus=union-form&period=${period}`)
  await expect(page.getByTestId("union-form-core")).toBeVisible({ timeout: 20_000 })

  // Nothing is stale before the change — without this the next assertion
  // could be satisfied by a notice that is always on.
  await expect(page.getByTestId("union-form-stale-banner")).toHaveCount(0)
  const before = await page.getByTestId("value-total_remittance").innerText()

  // ⚠️ A REAL ROW, IN THE REAL DATABASE. One extra dues check for a member
  // who was already paid, which moves the remittance and the earnings.
  const added = sql(
    `${PRELUDE}
cid = str(uuid.uuid4())
when = check_dates_in(Y, M)[-1]
db.execute(text("INSERT INTO payroll_checks (id,tenant_id,emp_id,person,check_number,check_date,source_page,created_at) VALUES (:i,:t,'9001','Coyne, Daniel','WALK-STALE',:d,0,now())"), {"i": cid, "t": T, "d": when})
db.execute(text("INSERT INTO payroll_check_lines (id,tenant_id,check_id,kind,code,hours,amount) VALUES (:i,:t,:c,'earning','Reg',40.00,900.00)"), {"i": str(uuid.uuid4()), "t": T, "c": cid})
db.execute(text("INSERT INTO payroll_check_lines (id,tenant_id,check_id,kind,code,amount) VALUES (:i,:t,:c,'deduction','Union',13.85)"), {"i": str(uuid.uuid4()), "t": T, "c": cid})
db.commit(); print(cid)`,
  )
  expect(added).toMatch(/^[0-9a-f-]{36}$/)

  try {
    await page.reload()
    await expect(page.getByTestId("union-form-core")).toBeVisible({ timeout: 20_000 })

    const after = await page.getByTestId("value-total_remittance").innerText()
    expect(after).not.toEqual(before)

    // ⚠️ THE REASON THE RECORD EXISTS. The copies that left no longer say
    // what the data says, and the form tells the reader so.
    await expect(page.getByTestId("union-form-stale-banner")).toBeVisible()
    await expect(page.getByTestId("union-form-copies")).toContainText(
      "Today's figures differ from this copy",
    )
    await shotForm(page, "u08-stale-copy")
  } finally {
    // Put the month back as it was found — the same discipline the payroll
    // switch teardown now follows.
    sql(
      `${PRELUDE}
db.execute(text("DELETE FROM payroll_check_lines WHERE check_id = :c"), {"c": "${added}"})
db.execute(text("DELETE FROM payroll_checks WHERE id = :c"), {"c": "${added}"})
db.commit(); print('reverted')`,
    )
  }
})

test("7 · Opas is the other entrance, and it opens the same month", async ({ page }) => {
  await signIn(page)

  // ⚠️ `opas-command-line`, read from the component rather than guessed. My
  // first version waited on `opas-pane`, which is a PREFIX of the per-pane
  // testids (`opas-pane-<id>`) and matches nothing on its own — a constructed
  // name, and the walk timed out on it for twenty seconds.
  await page.keyboard.press("Meta+k")
  await expect(page.getByTestId("opas-command-line")).toBeVisible({ timeout: 20_000 })
  // ⚠️ THE ENTRIES RENDER OUTSIDE THE COMMAND LINE. Scoping the assertion to
  // `opas-command-line` failed while the entry was plainly on screen — the
  // pills are siblings of the input, not children of it. Asserted on the
  // page, which is where a person reads it.
  const entry = page.getByText("Union form", { exact: false }).first()
  await expect(entry).toBeVisible({ timeout: 20_000 })
  await expect(page.getByText("The R-115 for the month being remitted")).toBeVisible()
  await page.screenshot({ path: `${SHOTS}/u09-opas-union-entry.png`, fullPage: true })

  await entry.click()
  await expect(page.getByTestId("union-form-core")).toBeVisible({ timeout: 20_000 })
  // ⚠️ SCOPED. The capability fills the period server-side; an unscoped target
  // is what rendered nothing in PR C's walk.
  await expect(page.getByTestId("union-form-lines")).toBeVisible()
  await expect(page).toHaveURL(/period=\d{4}-\d{2}/)
  await page.screenshot({ path: `${SHOTS}/u10-opened-from-opas.png`, fullPage: true })
})

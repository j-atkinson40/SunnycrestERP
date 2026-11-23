/**
 * The week-44 walkthrough, as Susan — Payroll 5a.
 *
 * sign in → the note → open the week from the note line AND from Opas (⌘K) →
 * the finding → 40 REG with a reason → approve → the deduction list → the
 * member pane → the timecard pane showing the correction labelled.
 *
 * ⚠️ **THIS WALK WAS RED FROM 2026-11-18 TO 2026-11-23 AND CHECKED NOTHING
 * PAST ITS THIRD ASSERTION.** `5dd34500` ("PR C: the shell Susan gets — no
 * sidebar") gave an area-limited user `LimitedShell`, which deliberately has
 * no sidebar. This walk still asserted `getByRole("link", {name: /^Today$/})`
 * and died there — before the note, before the Focus, before the correction,
 * before the approval. Five days in which the main walk for Susan's weekly
 * payroll was reporting a shell change as a payroll failure and verifying
 * nothing.
 *
 * ⚠️ **AND IT WAS REPORTED AS "PRE-EXISTING" ONCE BEFORE BEING FIXED**, which
 * is the thing to notice: "fails identically with and without my change" is
 * true, and is an answer to *did I break this*, not to *is this working*. A
 * walk is an instrument; §11's standing question — WHEN DID THIS LAST PASS? —
 * is owed to it the moment it goes red, and the answer here was a date and a
 * commit, not noise.
 *
 * ⚠️ **SIGN-IN IS NOW REAL, NOT AN INJECTED TOKEN.** The shell a user gets is
 * chosen from the `/auth/me` payload, so a walk that injects a token proves the
 * shell works for a session somebody else established. `seed_week44_walkthrough`
 * gives this user a published local-dev password for exactly this.
 *
 * ⚠️ Screenshots are taken DELIBERATELY at each step, not only on failure: the
 * point of this walk is that somebody looks at the screens. The Status row's
 * regression on 2026-11-23 — buttons pushed out of a pane while 92 tests
 * passed — was caught by reading one, and by nothing else.
 *
 * Run it with both servers up and the fixture seeded:
 *
 *   SECRET_KEY=… DATABASE_URL=…note5a_clean python scripts/seed_week44_walkthrough.py
 *   uvicorn app.main:app --port 8000
 *   npx vite --port 5199
 *   PW_WEEK_ID=… PW_BASE_URL=http://localhost:5199 \
 *     PW_HOURS_PDF=~/Downloads/Payentry_Employee_Hours_2026-10-25_to_10-31.pdf \
 *     npx playwright test -c playwright.local.config.ts payroll-week44-walkthrough
 *
 * ⚠️ `PW_BASE_URL` is needed because vite binds IPv6 `localhost` and the
 * config's default is `127.0.0.1`, which refuses the connection.
 */
import { execFileSync } from "node:child_process"

import { expect, test, type Page } from "@playwright/test"

const WEEK_ID = process.env.PW_WEEK_ID ?? ""
const SLUG = process.env.PW_SLUG ?? "testco"
const EMAIL = process.env.PW_WALK_EMAIL ?? "susan.walkthrough@testco.example.com"
const PASSWORD = process.env.PW_WALK_PASSWORD ?? "WalkThrough123!"
const SHOTS = "tests/local/shots"
const API = process.env.PW_API ?? "http://localhost:8000"
const PY =
  process.env.PW_PY ?? "/Users/Jimmy1/Projects/SunnycrestERP-5a/backend/.venv/bin/python"
const BACKEND =
  process.env.PW_BACKEND ?? "/Users/Jimmy1/Projects/SunnycrestERP-setup/backend"
/** ⚠️ **READ IN PLACE AND NEVER COPIED INTO THE REPOSITORY.** It is a real
 *  payroll export: real names, real rates. Points outside the tree, the way
 *  the register is handled. */
const HOURS_PDF = process.env.PW_HOURS_PDF ?? ""

test.describe.configure({ mode: "serial" })

test.beforeAll(() => {
  // Fail loudly rather than walking an unseeded app and screenshotting empty
  // states that look like a working quiet day.
  expect(WEEK_ID, "PW_WEEK_ID must be the week id printed by the seed").not.toBe("")
})

/**
 * Sign in through the form, as she would.
 *
 * ⚠️ **REPLACED THE INJECTED TOKEN ON 2026-11-23.** The old helper wrote
 * `access_token` into localStorage with a locally minted key. That proves the
 * app works for a session somebody else established — and the thing that broke
 * this walk was precisely which SHELL the session gets, which is decided from
 * the `/auth/me` payload. A token-injecting walk could not have caught it, and
 * did not.
 */
async function asSusan(page: Page) {
  // The tenant resolves from localStorage on localhost — `lib/tenant.ts`
  // persists `?slug=` and strips it, which is the documented dev bootstrap.
  await page.goto(`/?slug=${SLUG}`)
  await page.getByLabel(/email/i).fill(EMAIL)
  await page.getByLabel(/password/i).fill(PASSWORD)
  await page.getByRole("button", { name: /sign in/i }).click()
  await page.waitForURL(/\/(home|note)/, { timeout: 30_000 })
}

/**
 * Run a short python snippet against the same database the server is using.
 *
 * ⚠️ **THE WALK TOUCHES REAL DATA, SO IT SAYS SO LOUDLY AND PUTS IT BACK.**
 * The hours-upload step needs the roster to know the ids in the real export —
 * a precondition `import_hours` ENFORCES, not a workaround — and no API seeds
 * a roster. The alternative was to mock the upload, which would have made the
 * one step that matters prove nothing.
 */
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

/** The session's own token, read back from where the app put it, so the
 *  direct API reads below authenticate as the same user the browser is. */
async function tokenOf(page: Page): Promise<string> {
  const t = await page.evaluate(() => localStorage.getItem("access_token"))
  expect(t, "signed in but no access_token in localStorage").toBeTruthy()
  return t as string
}

async function shot(page: Page, name: string) {
  await page.screenshot({ path: `${SHOTS}/${name}.png`, fullPage: false })
}

test("week 44, start to finish, as the payroll user", async ({ page }) => {
  // ⚠️ **FAILED REQUESTS ARE RECORDED BY URL, NOT BY CONSOLE TEXT.** The
  // console says only "Failed to load resource", which cannot be told apart
  // from any other failure — and the 500 that wrote nothing announced itself
  // there and nowhere else.
  const failed: string[] = []
  page.on("response", (r) => {
    if (r.status() >= 400) failed.push(`${r.status()} ${new URL(r.url()).pathname}`)
  })

  // ⚠️ KNOWN AND EXPECTED, each with its reason. A payroll-limited user is
  // refused these by the AREA GUARD, correctly: both are composed surfaces
  // that do not yet filter by area, so the guard refuses rather than leaking.
  // Neither is Payroll 5a's, and neither breaks the Focus — the core reads the
  // week from the URL when no focus session can be created.
  //
  // Anything NOT on this list fails the walk. An allowlist of two named paths
  // still reports a third.
  // ⚠️ Paths READ FROM A RUN, not guessed. The first version of this list said
  // `/api/v1/focus/sessions`; the real path is `/api/v1/focus/{id}/open`, and
  // the walk correctly reported it as unexpected.
  const EXPECTED_403 = [
    /^\/api\/v1\/widgets\/composed-definitions$/,  // widget palette; not area-aware
    /^\/api\/v1\/focus\/[^/]+\/open$/,             // focus session; /focus is unbuilt
    // ⚠️ **THESE TWO ARE NEW ON 2026-11-23 AND ARE A FINDING, NOT NOISE.** They
    // appear because this walk now presses ⌘K; the old one never opened Opas,
    // so nothing had ever observed what her capture bar asks for. Both are
    // refused by the AREA GUARD — neither is in `COMPOSED_ROUTES`, and both
    // take only `get_current_user`, so the 403 is the guard and not the route.
    //
    // Measured consequences, stated rather than waved past:
    //   /capture/vocabulary   everything the bar may complete FOR THE TENANT.
    //                         It genuinely spans areas, so refusing it is
    //                         correct until it filters — and it means she gets
    //                         no completions at all.
    //   /capture/preferences  only the caller's OWN pill-pick modifier, which
    //                         its own docstring calls structurally impossible
    //                         to leak (no user parameter exists). Refusing it
    //                         silently falls her back to the default modifier.
    //
    // Allowlisted rather than fixed: `COMPOSED_ROUTES` says an entry there is a
    // promise, to be added only with the filtering it claims and a test that a
    // limited caller gets only their own areas back. That is a decision about
    // the guard, not a walk-through repair.
    /^\/api\/v1\/capture\/preferences$/,
    /^\/api\/v1\/capture\/vocabulary$/,
  ]

  await asSusan(page)

  // ── 0. the shell she actually gets ───────────────────────────────────────
  //
  // ⚠️ **THIS IS THE STEP THAT WENT STALE, AND IT IS WHY THE REST WENT DARK.**
  // It used to assert a sidebar with Today and Payroll. `5dd34500` removed the
  // sidebar for area-limited users ON PURPOSE — "a sidebar whose every item is
  // refused is worse than no sidebar" — and the walk went on asserting it for
  // five days.
  //
  // Asserted by the shell's own testid AND by the absence of the old chrome.
  // Either alone is weaker: the testid could be present while a sidebar renders
  // beside it, and "no sidebar" is true of a blank page.
  await expect(page.getByTestId("limited-shell")).toBeVisible({ timeout: 20_000 })
  await expect(page.getByTestId("limited-shell-who")).toContainText("Susan")
  await expect(
    page.locator("aside, nav").filter({ hasText: /Dashboard|Orders|Customers/ }),
  ).toHaveCount(0)
  // ⚠️ AND THE SUPERSEDED ASSERTION IS PINNED AS AN ABSENCE, so a future
  // session cannot "restore" it without this walk objecting.
  await expect(page.getByRole("link", { name: /^Today$/ })).toHaveCount(0)
  await expect(page).toHaveURL(/\/(home|note)$/)

  // ── 1. the note, which is her home ───────────────────────────────────────
  //
  // ⚠️ ATTACHED, not visible. An empty prose region has zero height and reads
  // as hidden — and empty is a LEGITIMATE state: the composition gate withholds
  // a non-prompt whose digest matches what the note last said, so the dues line
  // appears on the first view of the day and not on a reload. The walk asserts
  // the line itself rather than the region's box.
  await expect(page.getByTestId("prose-region")).toBeAttached({ timeout: 20_000 })
  await expect(
    page.getByTestId("prose-weekly_dues"),
    "the note has no dues line — re-run seed_week44_walkthrough.py; the backend "
      + "gate clears the payroll data switch on this database",
  ).toBeVisible()

  // ⚠️ **THE SHOT WAITS FOR THE NOTE, AND THIS IS THE SECOND TIME.** The
  // rewritten walk photographed the shell immediately after the chrome
  // assertions and captured "Loading…" — so the evidence for "she lands on her
  // note in the new shell" showed no note. The opas walk carries a comment
  // about exactly this defect, written a week earlier, and I reproduced it
  // anyway; it was caught by reading the picture, which is the only instrument
  // that can see a screenshot of the wrong moment. One shot now, taken once
  // there is something to photograph.
  await shot(page, "00-lands-on-home")

  // And the sphere is her entrance, quiet — no glow when there is nothing
  // urgent, which is canon.
  const sphere = page.getByTestId("opas-sphere")
  await expect(sphere).toBeVisible()
  await expect(sphere).toHaveAttribute("data-state", "quiet")

  // ── 2a. ENTRANCE ONE: the note's own line opens the week ─────────────────
  await page.getByTestId("prose-open-weekly_dues").click()
  // ⚠️ WAIT FOR THE FOCUS ITSELF, not for the URL. A walk in this suite passed
  // three steps while photographing a page that had navigated and not rendered.
  await expect(page.getByRole("heading", { name: /Week 44/ })).toBeVisible({
    timeout: 20_000,
  })
  await shot(page, "02a-week-from-the-note-line")

  // ── 2b. ENTRANCE TWO: ⌘K → Opas ─────────────────────────────────────────
  //
  // ⚠️ **⌘K IS OPAS HERE, NOT THE PLATFORM COMMAND BAR** — ruling 2 of
  // 2026-11-17. The platform bar would answer with orders, invoices and
  // contacts, none of which she can reach. Two entrances is the rule
  // (CLAUDE.md §1a); this walk exercises both rather than naming one.
  // ⚠️ `/home`, NOT `/note`. The note IS `/home` for this user — she lands
  // there and `landingRouteForAreas` has never run (it reads a provider the
  // redirect is mounted outside of). The first version of this step navigated
  // to `/note`, where the Opas host does not mount, and ⌘K did nothing — which
  // reads as "⌘K is broken" and was "this is not the page she is on".
  await page.goto("/home")
  // ⚠️ **A POSITIVE CONTROL BEFORE THE ABSENCE, AND IT IS WHY THIS STEP WORKS.**
  // The first version asserted `opas-command-line` absent and pressed ⌘K. The
  // absence was TRUE and MEANINGLESS — it is satisfied by a page that has not
  // hydrated — so it resolved instantly and the keypress landed before the ⌘K
  // listener was bound. It then failed for twenty seconds waiting for a command
  // line nothing had been told to open, which reads as "⌘K is broken".
  //
  // The sphere exists only once the Opas host has mounted, so waiting for it
  // makes the next line a claim about the app rather than about the clock.
  // §11: an instrument that cannot see returns what a true absence returns.
  await expect(page.getByTestId("opas-sphere")).toBeVisible({ timeout: 20_000 })
  await expect(page.getByTestId("opas-command-line")).toHaveCount(0)
  await page.keyboard.press("Meta+k")
  await expect(page.getByTestId("opas-command-line")).toBeVisible({ timeout: 20_000 })
  // ⚠️ WAIT FOR THE PILLS BEFORE THE SHOT, for the same reason as the note
  // above: the first version photographed the instant after ⌘K and captured
  // "Reading what you can do here…", which is evidence that Opas opened and
  // not evidence of what it offers her. The pills ARE the answer.
  await expect(page.getByTestId("opas-guided-pills")).toBeVisible({ timeout: 20_000 })
  await shot(page, "02b-cmdk-opens-opas")
  // ⚠️ SCOPED TO OPAS'S OWN LIST. "Upload hours" and this label also appear on
  // the note behind the veil — page-wide text matching took the opas walk red
  // when #40 reworded the week line.
  await page.getByTestId("opas-guided-pills").getByText("This week's payroll").click()
  await page.waitForURL(/focus=weekly-payroll/, { timeout: 20_000 })
  // ⚠️ THE SCOPE IS THE POINT. `/home?focus=weekly-payroll` with no scope
  // renders the note and nothing else; the capability carries the week being
  // worked, filled by the server.
  await expect(page).toHaveURL(/week_(id|end)=/)
  await shot(page, "02c-week-from-opas")

  // ── 2. the Focus, opened scoped to week 44 ───────────────────────────────
  await page.goto(`/home?focus=weekly-payroll&week_id=${WEEK_ID}`)
  await expect(page.getByTestId("weekly-payroll-core")
    .or(page.locator('[data-slot="weekly-payroll-core"]'))).toBeVisible({
      timeout: 20_000,
    })
  await expect(page.getByRole("heading", { name: /Week 44/ })).toBeVisible()
  await shot(page, "02-focus-opened")

  // ── 3. the finding, and the three numbered answers ───────────────────────
  const finding = page.getByTestId("finding-configured_member_missing_from_export")
  // ⚠️ **THIS WALK ANSWERS A FINDING, SO IT IS NOT REPEATABLE WITHOUT A RESEED,
  // AND IT SAYS SO RATHER THAN FAILING CRYPTICALLY.** An answered finding does
  // not come back — correctly; that is what answering means. A second run
  // against the same database therefore finds nothing to answer, and the bare
  // assertion read as "the finding never rendered", which is a different and
  // much more alarming claim. CLAUDE.md §11: a gate that mutates shared state
  // is not repeatable, and the honest form is to name the state it needs.
  await expect(
    finding,
    "the finding is not open — this walk ANSWERS it, so a second run needs a "
      + "fresh fixture: re-run scripts/seed_week44_walkthrough.py and pass the "
      + "week id it prints as PW_WEEK_ID",
  ).toBeVisible({ timeout: 20_000 })
  await expect(page.getByTestId("answer-1")).toHaveText(/Enter hours/)
  await shot(page, "03-finding-no-hours")

  // ── 4. enter 40 REG, with a reason ───────────────────────────────────────
  await page.getByTestId("answer-1").click()
  await expect(page.getByTestId("correction-form")).toBeVisible()
  await page.getByTestId("correction-date").fill("2026-10-28")
  await page.getByTestId("correction-paytype").selectOption("REG")
  await page.getByTestId("correction-hours").fill("40")
  await page.getByTestId("correction-reason").fill("worked all week, hours never reached Payentry")
  await shot(page, "04-correction-form")
  await page.getByTestId("correction-save").click()

  // ── 5. the correction must actually have landed ──────────────────────────
  //
  // ⚠️ **THIS ASSERTION IS THE WHOLE REASON THE WALK IS WORTH RUNNING.** The
  // first version asserted `corrections-count` OR `the-week` was visible —
  // and `the-week` is always visible, so the walk passed while the correction
  // POST returned 500 and NOTHING was written. Green, nine screenshots, no
  // correction and no decision in the database.
  //
  // So it now asserts the finding is GONE from the open list (the decision
  // landed) and the correction is listed (the hours landed). Both are server
  // state reflected back, not UI that renders regardless.
  await expect(finding).toBeHidden({ timeout: 20_000 })
  await expect(page.getByTestId("answered-findings")).toContainText(
    "configured_member_missing_from_export",
  )
  await shot(page, "05-after-correction")

  // ── 6. the week, and the checks before approving ─────────────────────────
  await expect(page.getByTestId("week-table")).toBeVisible()
  await expect(page.getByTestId("approve-section")).toBeVisible()
  await shot(page, "06-the-week-and-checks")

  // ── 7. approve ───────────────────────────────────────────────────────────
  await page.getByTestId("approve-week").click()
  await expect(page.getByTestId("deduction-list")).toBeVisible({ timeout: 20_000 })
  await shot(page, "07-approved-deduction-list")
  const rows = await page.getByTestId("deduction-list").locator("li").count()

  // ── 8. the timecard pane, with the correction labelled ───────────────────
  await page.getByTestId("week-row-9001").click()
  await expect(page.getByTestId("payroll-pane-member-" +
    (await page.getByTestId("week-row-9001").getAttribute("data-emp") ?? ""))
    .or(page.locator('[data-testid^="payroll-pane-member-"]'))).toBeVisible()
  await shot(page, "08-member-pane")

  await page.getByTestId("pane-open-timecard").click()
  await expect(page.locator('[data-testid^="payroll-pane-timecard-"]')).toBeVisible()
  await shot(page, "09-timecard-pane")

  // Reported, not asserted away: the walk's value is that somebody looks.
  const unexpected = failed.filter((f) => {
    const m = f.match(/^(\d{3}) (.+)$/)
    if (!m || m[1] !== "403") return true
    return !EXPECTED_403.some((re) => re.test(m[2]))
  })
  expect(
    unexpected,
    `the page made failed requests that are not the two known out-of-area 403s:\n${unexpected.join("\n")}`,
  ).toEqual([])

  console.log(`[walk] deduction rows: ${rows}`)
  console.log(`[walk] failed requests (all expected): ${failed.join(", ") || "none"}`)
})

/**
 * ⚠️ **A WALK-THROUGH NEVER MOCKS THE WRITE IT WALKS THROUGH.**
 *
 * ⚠️ **AND ON 2026-11-23 THIS ONE FOUND THAT THE UPLOAD HAD NEVER REACHED ITS
 * PARSER.** `POST /weeks/upload` chose a parser from a `format_key` form field
 * defaulting to `"payentry"` — the key of an old GUESSED CSV mapping carrying
 * `verified: false`. The Focus never sent the field, so every upload Susan
 * made took that default and was refused, **in every environment**. Payroll 3's
 * Employee Hours PDF reader sat behind `"payentry_employee_hours"`, a string
 * that appeared exactly once in the whole tree: at its own definition.
 *
 * The endpoint now routes on the BYTES. This step is the proof, and it is the
 * only instrument that could give it — Phase 3's suite tests the parser and
 * the rules, and would have stayed green through the entire period the product
 * was broken. That is not a hypothetical; it is what happened.
 *
 * It sends the real export through the Focus's own file input and then READS
 * THE SERVER BACK. Not the screen — the screen renders whatever it is given,
 * which is exactly how a never-working upload shipped green for an arc.
 *
 * ⚠️ **THE FILE IS READ IN PLACE AND IS NEVER COPIED INTO THE REPOSITORY.**
 * It is a real payroll export: real names, real rates. `PW_HOURS_PDF` points
 * at it outside the tree, the way the register is handled.
 */
test("the REAL Employee Hours PDF, through the Focus, reaches the Payroll 3 parser", async ({
  page,
}) => {
  test.skip(
    HOURS_PDF === "",
    "PW_HOURS_PDF must point at a real Payentry Employee Hours PDF, outside " +
      "the repo. Skipped rather than faked: a synthesised PDF would test my " +
      "idea of the format, which is precisely what the guessed CSV mapping " +
      "already was. Try " +
      "~/Downloads/Payentry_Employee_Hours_2026-10-25_to_10-31.pdf",
  )

  await asSusan(page)

  // ⚠️ **THE ROSTER IS A PRECONDITION THE IMPORTER ENFORCES.** `import_hours`
  // refuses a whole file whose employee ids are not in the register or the
  // roster — "correct hours against a person who does not exist" is what a
  // mis-read number looks like, and that guard is why the parser can be
  // trusted. The walk seeds the ids (NOT the names: nothing here writes a real
  // employee's name) and removes them again at the end.
  const seeded = sql(
    py(
      "import uuid, pathlib, pdfplumber\n"
      + "from app.models.payroll_report import PayrollReportEmployee\n"
      + "from app.services.payroll.hours_parser import parse_employee_hours\n"
      + `with pdfplumber.open(pathlib.Path(${JSON.stringify(HOURS_PDF)}).expanduser()) as f:\n`
      + "    ids = sorted(parse_employee_hours(f).emp_ids)\n"
      + "made = 0\n"
      + "for e in ids:\n"
      + "    if db.query(PayrollReportEmployee).filter(\n"
      + "            PayrollReportEmployee.tenant_id==C,\n"
      + "            PayrollReportEmployee.payentry_file_number==e).first():\n"
      + "        continue\n"
      + "    db.add(PayrollReportEmployee(id=str(uuid.uuid4()), tenant_id=C,\n"
      + "        payentry_file_number=e, display_name=f'Walk {e}',\n"
      + "        is_union_member=False))\n"
      + "    made += 1\n"
      + "db.execute(text(\"DELETE FROM payroll_hours_imports WHERE tenant_id=:c \"\n"
      + "    \"AND week_end_date='2026-10-31'\"), {'c': C})\n"
      + "db.commit()\n"
      + "print(f'{len(ids)} ids, {made} added')",
    ),
  )
  console.log(`[walk] roster seeded: ${seeded}`)

  // ⚠️ **AIM IT AT THE WEEK THE FILE IS ACTUALLY FOR.** The first version of
  // this step opened the week being worked (47) and uploaded a week-44 export.
  // The server refused — "the file covers the week ending 2026-10-31, not the
  // requested 2026-11-21" — which is the importer being RIGHT, and is worth
  // asserting rather than designing around. Both are checked below.
  const pending = await (await page.request.get(
    `${API}/api/v1/payroll-reports/weeks/current`,
    { headers: { Authorization: `Bearer ${await tokenOf(page)}`,
                 "X-Company-Slug": SLUG } },
  )).json()
  await page.goto(`/home?focus=weekly-payroll&week_end=${pending.week_end_date}`)
  await expect(page.getByTestId("upload-card")).toBeVisible({ timeout: 20_000 })
  await page.getByTestId("hours-file").setInputFiles(HOURS_PDF)
  await page.getByTestId("upload-hours").click()
  const wrongWeek = page.getByTestId("focus-error")
  await expect(wrongWeek).toBeVisible({ timeout: 60_000 })
  await expect(wrongWeek).toContainText("2026-10-31")
  await expect(wrongWeek).toContainText(pending.week_end_date)
  // The control for the assertion above: a refusal IS an error, and says so.
  await expect(wrongWeek).toHaveAttribute("data-ok", "no")
  console.log("[walk] a week-44 file into week " + pending.week_number +
    " is refused, and the sentence names both weeks")
  await shot(page, "09a-upload-into-the-wrong-week")

  // Now the week the file IS for. The seed already built week 44, so its row
  // is removed to get back to the state the upload card lives in — which is
  // why the seed must be re-run before another pass of this walk.
  console.log(`[walk] clearing week 44: ${sql(py(
    "n = db.execute(text(\"DELETE FROM payroll_weeks WHERE tenant_id=:c \"\n"
    + "    \"AND week_end_date='2026-10-31'\"), {'c': C}).rowcount\n"
    + "db.commit()\n"
    + "print(f'{n} week row(s)')"))}`)

  await page.goto("/home?focus=weekly-payroll&week_end=2026-10-31")
  await expect(page.getByTestId("upload-card")).toBeVisible({ timeout: 20_000 })
  await page.getByTestId("hours-file").setInputFiles(HOURS_PDF)
  await page.getByTestId("upload-hours").click()

  // ⚠️ **THE SENTENCE ON SCREEN IS PART OF THE FIX.** The PDF branch returned
  // no `summary`, so the card rendered "— people, — hours." on a week that had
  // loaded correctly. 25 is everyone the export LISTS (18 have hours, 7 do
  // not) — the figure James stated.
  const said = page.getByTestId("focus-error")
  await expect(said).toBeVisible({ timeout: 60_000 })
  await expect(said).toContainText("25 people")
  await expect(said).toContainText("708.61 hours")
  // ⚠️ **AND IT IS NOT RENDERED AS AN ERROR.** The upload reports through the
  // same slot as every failure, and that slot was styled `text-status-error`
  // — so the first successful Employee Hours upload said "Week 44 loaded: 25
  // people, 708.61 hours." IN RED. A success in error colour contradicts
  // itself and the reader believes the colour. Found by reading the
  // screenshot, which is the only thing that could see it.
  await expect(said).toHaveAttribute("data-ok", "yes")
  await shot(page, "10-real-hours-upload")

  // ⚠️ **READ BACK FROM THE SERVER, NOT FROM THE SCREEN.** The screen would
  // have said "loaded" on any 200 for the whole time this was broken.
  const stored = sql(
    py(
      "row = db.execute(text(\"SELECT count(DISTINCT h.emp_id), coalesce(sum(h.hours),0) \"\n"
      + "    \"FROM payroll_hours_lines h JOIN payroll_hours_imports i ON i.id=h.import_id \"\n"
      + "    \"WHERE i.tenant_id=:c AND i.week_end_date='2026-10-31'\"), {'c': C}).fetchone()\n"
      // ⚠️ **NORMALISED, BECAUSE `hours` IS `Numeric(10,4)` AND COMES BACK
      // "708.6100".** My first assertion compared it to the string "708.61"
      // and failed on formatting while the figure was exactly right — the same
      // trap recorded on 2026-11-17: compare DECIMALS for hours, strings for
      // money.
      + "print(f'{row[0]} with hours, {row[1].normalize()} hours')",
    ),
  )
  console.log(`[walk] the server holds: ${stored}`)
  expect(stored).toBe("18 with hours, 708.61 hours")

  // ⚠️ **THE WEEK NOW EXISTS, WHICH A REFUSED UPLOAD CANNOT PRODUCE.** It
  // opens on week 44 at status `imported`.
  //
  // ⚠️ **AND IT DOES NOT SHOW A WEEK TABLE, WHICH IS CORRECT HERE AND WAS MY
  // FIRST ASSERTION.** Dues need a pay rate, and the roster rows this walk
  // seeds are ids with no rates — so Opas flags "no effective pay rate on or
  // before the week end date" for each and no line is calculated. That is the
  // engine being right about a synthetic roster, not the import failing, and
  // asserting a table here would have been a claim about the fixture dressed
  // as a claim about the product.
  await page.goto("/home?focus=weekly-payroll&week_end=2026-10-31")
  await expect(
    page.getByRole("heading", { name: /Week 44/ }),
  ).toBeVisible({ timeout: 20_000 })
  await expect(page.getByTestId("findings")).toContainText(/pay rate/i)
  await shot(page, "11-week-loaded-from-the-real-export")

  const weekRow = sql(
    py(
      "r = db.execute(text(\"SELECT status FROM payroll_weeks WHERE tenant_id=:c \"\n"
      + "    \"AND week_end_date='2026-10-31'\"), {'c': C}).fetchone()\n"
      + "print(r[0] if r else 'NO ROW')",
    ),
  )
  console.log(`[walk] week 44 on the server: ${weekRow}`)
  expect(weekRow).toBe("imported")

  // ⚠️ UNDONE, so the walk is repeatable and leaves the fixture as found.
  const undone = sql(
    py(
      "n = db.execute(text(\"DELETE FROM payroll_hours_imports WHERE tenant_id=:c \"\n"
      + "    \"AND week_end_date='2026-10-31'\"), {'c': C}).rowcount\n"
      + "m = db.execute(text(\"DELETE FROM payroll_report_employees WHERE tenant_id=:c \"\n"
      + "    \"AND display_name LIKE 'Walk %'\"), {'c': C}).rowcount\n"
      + "db.commit()\n"
      + "print(f'{n} imports, {m} roster rows')",
    ),
  )
  console.log(`[walk] undone: ${undone}`)
})

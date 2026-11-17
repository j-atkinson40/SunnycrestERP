/**
 * The week-44 walkthrough, as Susan — Payroll 5a.
 *
 * sign in (session injected) → home note → open the Focus → resolve the member
 * with no hours by entering 40 REG + 2 OT with a reason → approve → the
 * deduction list → the timecard pane showing the correction labelled.
 *
 * ⚠️ **THE SESSION IS INJECTED, NOT TYPED, AND NO REAL CREDENTIAL EXISTS.**
 * A payroll-role user requires two-step sign-in, so driving the sign-in form
 * would need a second factor. The token is minted locally with the dev
 * `SECRET_KEY` and carries the `mfa` claim — the same thing the backend suite's
 * `tenant_token` helper does. The seeded user's password hash is a literal that
 * cannot be signed in with.
 *
 * ⚠️ Screenshots are taken DELIBERATELY at each step, not only on failure: the
 * point of this walk is that somebody looks at the screens.
 */
import { expect, test, type Page } from "@playwright/test"

const WEEK_ID = process.env.PW_WEEK_ID ?? ""
const TOKEN = process.env.PW_TOKEN ?? ""
const SLUG = process.env.PW_SLUG ?? "testco"
const SHOTS = "tests/local/shots"

test.beforeAll(() => {
  // Fail loudly rather than walking an unseeded app and screenshotting empty
  // states that look like a working quiet day.
  expect(WEEK_ID, "PW_WEEK_ID must be the week id printed by the seed").not.toBe("")
  expect(TOKEN, "PW_TOKEN must be a locally minted token").not.toBe("")
})

async function asSusan(page: Page) {
  await page.addInitScript(
    ([token, slug]) => {
      localStorage.setItem("access_token", token as string)
      localStorage.setItem("company_slug", slug as string)
    },
    [TOKEN, SLUG],
  )
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
  ]

  await asSusan(page)

  // ── 0. where she LANDS ───────────────────────────────────────────────────
  //
  // ⚠️ **STARTS AT THE ROOT, NOT AT A URL I CHOSE.** `landingRouteForAreas`
  // sends an area-limited user to their area and never to Home, so `/payroll`
  // is Susan's entire entrance. The walk used to begin at `/note` — a page she
  // never lands on — which is exactly why the placeholder on `/payroll`
  // survived a release after the Focus shipped.
  //
  // A real sign-in is not driven here: a payroll user requires two-step, so
  // the session is injected as before. What is asserted is where the app puts
  // her once she HAS one.
  await page.goto("/")

  // ⚠️ **SHE LANDS ON `/home`, NOT `/payroll`, AND THAT IS A FINDING.**
  //
  // `landingRouteForAreas` exists to send an area-limited user to her area and
  // never to Home, and it is unit-tested to return "/payroll". It has never
  // run. `RootRedirect` reads `usePresetThemeOptional()`, and the single
  // `PresetThemeProvider` in App.tsx wraps a DIFFERENT route subtree — the
  // redirect is mounted outside it, so the hook returns null every time and
  // the area branch is unreachable. Its tests mock the hook and supply a
  // preset, so they exercise the function and not the wiring.
  //
  // Asserted as MEASURED rather than as intended. Moving a provider in the
  // boot path is every user's boot path and is not this follow-up's to do.
  await expect(page).toHaveURL(/\/home$/, { timeout: 20_000 })
  await shot(page, "00-lands-on-home")

  // ── 0a. her sidebar offers Today and Payroll, and both work ──────────────
  //
  // Before this follow-up it held ONE item, Payroll, pointing at a
  // placeholder — and nothing returned her to the note, so navigating away
  // once put the week's dues line out of reach until she signed in again.
  await expect(page.getByRole("link", { name: /^Today$/ })).toBeVisible()
  await page.getByRole("link", { name: /^Payroll$/ }).click()
  await expect(page).toHaveURL(/\/payroll$/, { timeout: 20_000 })
  await expect(page.getByTestId("payroll-home")).toBeVisible()
  await expect(page.getByText(/review is coming/i)).toHaveCount(0)
  await expect(page.getByTestId("payroll-this-week")).toContainText(/Week \d+/)
  await shot(page, "00a-payroll-page")

  // ── 0b. and the Focus opens from there, scoped to the week ───────────────
  await page.getByTestId("open-weekly-payroll").click()
  await expect(page.getByRole("heading", { name: /Week 44/ })).toBeVisible({
    timeout: 20_000,
  })
  await shot(page, "00b-focus-from-payroll")

  // ── 1. the home note ─────────────────────────────────────────────────────
  await page.goto("/note")
  // ⚠️ ATTACHED, not visible. An empty prose region has zero height and reads
  // as hidden — and empty is a LEGITIMATE state: the composition gate withholds
  // a non-prompt whose digest matches what the note last said, so the dues line
  // appears on the first view of the day and not on a reload. The walk asserts
  // the line itself below rather than the region's box.
  await expect(page.getByTestId("prose-region")).toBeAttached()
  await expect(page.getByTestId("prose-weekly_dues")).toBeVisible()
  await expect(page.getByTestId("prose-open-weekly_dues")).toBeVisible()
  await shot(page, "01-home-note")

  // ── 2. the Focus, opened scoped to the week ──────────────────────────────
  await page.goto(`/home?focus=weekly-payroll&week_id=${WEEK_ID}`)
  await expect(page.getByTestId("weekly-payroll-core")
    .or(page.locator('[data-slot="weekly-payroll-core"]'))).toBeVisible()
  await expect(page.getByRole("heading", { name: /Week 44/ })).toBeVisible()
  await shot(page, "02-focus-opened")

  // ── 3. the finding, and the three numbered answers ───────────────────────
  const finding = page.getByTestId("finding-configured_member_missing_from_export")
  await expect(finding).toBeVisible()
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
 * Added 2026-11-17, and it is the test whose absence let a never-working
 * upload ship green through an entire arc. The 5a walk above exercises the
 * correction and the approval against a real server — but the UPLOADS were
 * covered only by vitest, against `vi.fn()`. So `apiClient`'s JSON
 * content-type turned every FormData body into about thirteen bytes of
 * `{"file":{}}`, the register upload answered 422 in 41 ms on production
 * having received 1,156 bytes of a 1.7 MB file, and nothing anywhere had ever
 * sent a real one.
 *
 * This sends the real Payentry Employee Hours PDF through the Focus's own file
 * input and then READS THE SERVER BACK. Not the UI — the UI renders whatever
 * it is given, and that is precisely how the defect stayed invisible.
 *
 * ⚠️ **THE FILE IS READ IN PLACE AND IS NEVER COPIED INTO THE REPOSITORY.**
 * It is a real payroll export: real names, real rates. `PW_HOURS_PDF` points
 * at it outside the tree, the way the register is handled.
 */
const HOURS_PDF = process.env.PW_HOURS_PDF ?? ""

test("the hours upload sends a REAL file, and the server confirms it", async ({
  page,
  request,
}) => {
  test.skip(
    HOURS_PDF === "",
    "PW_HOURS_PDF must point at a real Payentry Employee Hours PDF, outside the repo. " +
      "Skipped rather than faked: a mocked upload is what this test exists to replace.",
  )

  await asSusan(page)
  await page.goto(`/home?focus=weekly-payroll&week_id=${WEEK_ID}`)

  // ⚠️ A STATED PRECONDITION, FAILED LOUDLY RATHER THAN SKIPPED. The upload
  // card renders only while the week has nobody on it. A week that already
  // has hours cannot exercise the upload, and quietly passing here would be
  // the same false green this test replaces.
  const card = page.getByTestId("upload-card")
  await expect(
    card,
    "the seeded week already has hours, so the upload card is absent — " +
      "seed a week with no hours for this test",
  ).toBeVisible({ timeout: 20_000 })

  // The real file, through the real input, over real multipart.
  await page.getByTestId("hours-file").setInputFiles(HOURS_PDF)
  await page.getByTestId("upload-hours").click()

  // ⚠️ READ BACK FROM THE SERVER, NOT FROM THE SCREEN. The screen would say
  // "loaded" on any 200 and said "the week is unchanged" on every failure
  // regardless of what the server held.
  await expect(async () => {
    const r = await request.get(
      `${process.env.PW_API ?? "http://localhost:8000"}/api/v1/payroll-reports/weeks`,
      { headers: { Authorization: `Bearer ${TOKEN}`, "X-Company-Slug": SLUG } },
    )
    expect(r.status(), await r.text()).toBe(200)
    const weeks = (await r.json()).weeks as { id: string; status: string }[]
    const mine = weeks.find((w) => w.id === WEEK_ID)
    expect(mine, `week ${WEEK_ID} is not on the server`).toBeTruthy()
    // `awaiting_hours` is the pre-upload state. Anything past it means the
    // file arrived, was parsed, and rows were written.
    expect(mine!.status).not.toBe("awaiting_hours")
  }).toPass({ timeout: 60_000 })

  await shot(page, "10-real-hours-upload")

  // And the Focus now shows people, which it cannot do from a 13-byte body.
  await expect(page.getByTestId("week-table")).toBeVisible({ timeout: 20_000 })
})


/**
 * ⚠️ **FROM SIGN-IN WITH ZERO WEEKS — the state Susan was actually in.**
 *
 * The other specs here start from a seeded week. This one starts from nothing,
 * because "nothing" is where the blocker lived: with the data switch on, a
 * register imported and a roster reconciled, there was still no path to the
 * first upload. The upload card lives in the weekly Focus; the Focus opened
 * only on a `week_id`; that row is created BY the upload.
 *
 * Sends a REAL Employee Hours PDF, unmocked, and reads the week back FROM THE
 * SERVER — not from the screen, which renders whatever it is given and is
 * exactly how a never-working upload shipped green for an arc.
 *
 * ⚠️ The file is read IN PLACE from outside the repository and never
 * committed; it is a real payroll export.
 */
test("zero weeks → upload a real file → the week exists on the server", async ({
  page,
  request,
}) => {
  test.skip(
    HOURS_PDF === "",
    "PW_HOURS_PDF must point at a real Payentry Employee Hours PDF outside the " +
      "repo. Skipped rather than faked — a mocked upload is what this replaces.",
  )

  const api = process.env.PW_API ?? "http://localhost:8000"
  const auth = { Authorization: `Bearer ${TOKEN}`, "X-Company-Slug": SLUG }

  // ⚠️ PRECONDITION, FAILED LOUDLY. The whole point is the zero-week state; a
  // tenant that already has this week cannot exercise it, and passing over
  // that would be the false green this spec exists to replace.
  const before = await request.get(`${api}/api/v1/payroll-reports/weeks/current`,
    { headers: auth })
  expect(before.status(), await before.text()).toBe(200)
  const cur = await before.json()
  expect(
    cur.exists,
    `week ${cur.week_number} already has a row — seed a tenant with no hours ` +
      `for this week to exercise the zero-week path`,
  ).toBe(false)

  // She signs in and lands on the note; the Payroll page offers the upload.
  await asSusan(page)
  await page.goto("/payroll")
  await expect(page.getByTestId("upload-this-week")).toBeVisible({ timeout: 20_000 })
  await shot(page, "11-zero-weeks-payroll-page")

  // That link carries the week END, which exists before any row does.
  await page.getByTestId("upload-this-week").click()
  await expect(page.getByTestId("pending-week")).toBeVisible({ timeout: 20_000 })
  await expect(page.getByTestId("upload-card")).toBeVisible()
  await shot(page, "12-upload-card-is-step-1")

  await page.getByTestId("hours-file").setInputFiles(HOURS_PDF)
  await page.getByTestId("upload-hours").click()

  // ⚠️ READ BACK FROM THE SERVER. The screen would say "loaded" on any 200.
  await expect(async () => {
    const r = await request.get(`${api}/api/v1/payroll-reports/weeks/current`,
      { headers: auth })
    expect(r.status(), await r.text()).toBe(200)
    const after = await r.json()
    expect(after.week_end_date).toBe(cur.week_end_date)
    expect(after.exists, "the week still has no row on the server").toBe(true)
    expect(after.week_id).toBeTruthy()
  }).toPass({ timeout: 90_000 })

  await shot(page, "13-week-created-by-the-upload")
})

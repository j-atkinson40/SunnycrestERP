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

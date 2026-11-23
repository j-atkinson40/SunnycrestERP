/**
 * PR C walk-through — the shell an area-limited user gets, FROM SIGN-IN.
 *
 * ⚠️ **IT SIGNS IN. IT DOES NOT INJECT A TOKEN.** The shell a user gets is
 * chosen from the `/auth/me` payload, so a walk that establishes its own
 * session proves the chrome works for a session somebody else made. Susan's
 * local account carries a published dev password — see
 * `backend/scripts/seed_week44_walkthrough.py`, which refuses to run against
 * production.
 *
 * Run it with both servers up and the fixture seeded:
 *
 *   SECRET_KEY=… DATABASE_URL=…note5a_clean python scripts/seed_week44_walkthrough.py
 *   uvicorn app.main:app --port 8000
 *   VITE_API_URL=http://127.0.0.1:8000 npx vite --port 5199
 *   npx playwright test -c playwright.local.config.ts opas-shell-walkthrough
 *
 * ⚠️ Screenshots land in `tests/local/shots/` and are committed, because a
 * walk-through whose evidence is deleted is a claim with no auditable basis.
 */
import { expect, test } from "@playwright/test"

const EMAIL = process.env.PW_WALK_EMAIL ?? "susan.walkthrough@testco.example.com"
const PASSWORD = process.env.PW_WALK_PASSWORD ?? "WalkThrough123!"
const SLUG = process.env.PW_SLUG ?? "testco"
const SHOTS = "tests/local/shots"

test.describe.configure({ mode: "serial" })

/** Sign in through the form, exactly as she would. */
async function signIn(page: import("@playwright/test").Page) {
  // The tenant is resolved from localStorage on localhost — `lib/tenant.ts`
  // persists `?slug=` and strips it, which is the documented dev bootstrap.
  await page.goto(`/?slug=${SLUG}`)
  await page.getByLabel(/email/i).fill(EMAIL)
  await page.getByLabel(/password/i).fill(PASSWORD)
  await page.screenshot({ path: `${SHOTS}/c00-sign-in.png`, fullPage: true })
  await page.getByRole("button", { name: /sign in/i }).click()
  await page.waitForURL(/\/(home|note)/, { timeout: 30_000 })
}

test("1 · she lands on the note, in the new shell, with no sidebar", async ({ page }) => {
  await signIn(page)

  // ⚠️ THE NEW SHELL IS ASSERTED BY ITS OWN TESTID **AND** BY THE ABSENCE OF
  // THE OLD CHROME. Either alone is weaker: the testid could be present while a
  // sidebar renders beside it, and "no sidebar" is true of a blank page.
  await expect(page.getByTestId("limited-shell")).toBeVisible()
  await expect(page.getByTestId("limited-shell-who")).toContainText("Susan")
  await expect(page.locator("aside, nav").filter({ hasText: /Dashboard|Orders|Customers/ }))
    .toHaveCount(0)

  /* ⚠️ WAIT FOR THE NOTE BEFORE THE SHOT. The first version screenshotted
     immediately and captured "Loading…", so the evidence for "she lands on the
     note" showed no note. A screenshot is the artifact this walk produces; one
     taken before the thing arrives is a picture of the wrong moment. */
  await expect(page.getByRole("heading", { name: "Today" })).toBeVisible()

  /* ⚠️ THE NOTE'S CONTENT IS A PRECONDITION, AND IT WENT MISSING UNDER ME.
     `backend/tests/test_payroll_data_switch.py` REMOVES `payroll_data_enabled`
     from the tenant's settings and does not put it back (4 of 4 runs), so
     running the backend gate against the same local database silently turns
     payroll off — and this walk then photographs an empty note while every
     assertion about the SHELL still passes. Asserted loudly rather than
     tolerated: an empty note here means re-run the seed, not that the shell
     is broken. */
  await expect(
    page.getByText(/has no hours yet|dues come to/).first(),
    "the note is empty — re-run seed_week44_walkthrough.py; the backend gate "
      + "clears the payroll data switch on this database",
  ).toBeVisible()

  // And the sphere is her entrance, quiet — no glow.
  const sphere = page.getByTestId("opas-sphere")
  await expect(sphere).toBeVisible()
  await expect(sphere).toHaveAttribute("data-state", "quiet")
  await page.screenshot({ path: `${SHOTS}/c01-note-no-sidebar.png`, fullPage: true })
})

test("2 · the sphere sits on the right edge and snaps to the left when dragged", async ({ page }) => {
  await signIn(page)
  const sphere = page.getByTestId("opas-sphere")
  const before = await sphere.boundingBox()
  expect(before, "the sphere has a box").not.toBeNull()
  const vw = page.viewportSize()!.width
  // It starts on the RIGHT: its centre is past the midline.
  expect(before!.x + before!.width / 2).toBeGreaterThan(vw / 2)

  // Drag it across the midline and release; it should settle against the left
  // gutter (16px) rather than staying where it was dropped.
  await page.mouse.move(before!.x + 28, before!.y + 28)
  await page.mouse.down()
  await page.mouse.move(120, 300, { steps: 12 })
  await page.screenshot({ path: `${SHOTS}/c02-sphere-dragging.png` })
  await page.mouse.up()
  await page.waitForTimeout(700) // the settle transition is 360ms

  const after = await sphere.boundingBox()
  expect(after!.x + after!.width / 2).toBeLessThan(vw / 2)
  expect(Math.round(after!.x)).toBe(16)
  await page.screenshot({ path: `${SHOTS}/c03-sphere-snapped-left.png`, fullPage: true })
})

test("3 · Opas offers payroll and nothing else", async ({ page }) => {
  await signIn(page)
  await page.getByTestId("opas-sphere").click()

  // ⚠️ **SCOPED TO OPAS'S OWN LIST, NOT THE PAGE** — fixed 2026-11-23. These
  // were page-wide `getByText`, and "Upload hours" began matching TWICE when
  // #40 reworded the note's week line to name the act rather than the surface:
  // one hit is Opas's pill, the other is `prose-open-payroll_week_open` sitting
  // behind the veil. Strict mode refused, correctly, and this walk went red —
  // red on a copy change in a different surface, which is the same staleness
  // that took the 5a walk down.
  //
  // Scoping also makes the assertion say what it means: these are the entries
  // OPAS offers, and a label that happens to appear elsewhere on the note is
  // not evidence either way.
  // ⚠️ `opas-guided-pills`, NOT `opas-guided-pane`. The pane is the question
  // and the hint; the PILLS are the entries, and they are a sibling rather
  // than a child — measured from the DOM, not assumed from the names.
  const opas = page.getByTestId("opas-guided-pills")
  await expect(opas).toBeVisible()
  await expect(opas.getByText("This week's payroll")).toBeVisible()
  await expect(opas.getByText("Upload hours")).toBeVisible()
  await expect(opas.getByText("Dues reports")).toBeVisible()

  // ⚠️ AND NOT THE ORDERS ENTRANCE. "New order" is the hardcoded pill every
  // other Opas shows; for her it is another area's offering.
  await expect(opas.getByText("New order")).toHaveCount(0)
  await page.screenshot({ path: `${SHOTS}/c04-opas-payroll-only.png`, fullPage: true })
})

test("4 · ⌘K opens Opas, because there is no platform command bar here", async ({ page }) => {
  await signIn(page)
  await expect(page.getByTestId("opas-command-line")).toHaveCount(0)
  await page.keyboard.press("Meta+k")
  await expect(page.getByTestId("opas-command-line")).toBeVisible()
  await page.screenshot({ path: `${SHOTS}/c05-cmdk-opens-opas.png`, fullPage: true })

  // It toggles — a key that opens but cannot close is pressed twice.
  await page.keyboard.press("Meta+k")
  await expect(page.getByTestId("opas-command-line")).toHaveCount(0)
})

test("5 · typing a request opens the surface it names", async ({ page }) => {
  await signIn(page)
  await page.getByTestId("opas-sphere").click()
  /* ⚠️ WAITS FOR THE LIST ON PURPOSE, AND THE FIRST VERSION DID NOT — which is
     how step 5a below was found. Typing before the read lands is a real thing
     she will do (⌘K then type), and it used to do NOTHING. */
  await expect(page.getByText("Dues reports")).toBeVisible()
  await page.getByTestId("opas-input").fill("dues report")
  await page.screenshot({ path: `${SHOTS}/c06-typed-request.png`, fullPage: true })
  await page.getByTestId("opas-input").press("Enter")

  // "dues report" must reach the REPORTS page and not the week, whose phrases
  // include "dues" — the discriminating case from the shared table.
  await page.waitForURL(/\/payroll\b/, { timeout: 15_000 })
  /* ⚠️ A URL MATCH IS EVIDENCE OF NAVIGATION, NOT OF A WORKING PAGE, and the
     first version stopped at the URL. Its screenshot showed the NOTE under a
     /payroll address — the route had changed and the page had not yet
     rendered, so the artifact evidenced the wrong thing. Assert the payroll
     page's OWN content before the shot. */
  await expect(page.getByRole("heading", { name: /payroll/i })).toBeVisible()
  await expect(page.getByTestId("limited-shell")).toBeVisible()
  await page.screenshot({ path: `${SHOTS}/c07-opened-dues-reports.png`, fullPage: true })
})

test("6 · and the week itself still opens, from Opas", async ({ page }) => {
  await signIn(page)

  /* ⚠️ **THE WEEK NUMBER IS READ FROM THE SERVER, NOT TYPED** — fixed
     2026-11-23. This step asserted "Week 46" as a literal, so it went red the
     moment the calendar moved past it: the week being worked is now 47, and
     will be 48 next Monday. A walk that expires on a date is a walk that will
     be red more often than the product is broken, and a walk that is usually
     red is a channel nobody reads.

     "Week 46" looked like a fact about the app and was a fact about the week
     it was written in — CLAUDE.md §11's expired premise, in a test literal. */
  const token = await page.evaluate(() => localStorage.getItem("access_token"))
  const current = await (await page.request.get(
    `${process.env.PW_API ?? "http://localhost:8000"}/api/v1/payroll-reports/weeks/current`,
    { headers: { Authorization: `Bearer ${token}`, "X-Company-Slug": SLUG } },
  )).json()
  const wk = current.week_number as number
  expect(
    current.exists,
    `week ${wk} already has a row, so Opas opens the week core rather than the ` +
      "upload card and this step's shape no longer applies",
  ).toBe(false)

  await page.getByTestId("opas-sphere").click()
  await page.getByTestId("opas-guided-pills").getByText("This week's payroll").click()
  /* ⚠️ ASSERTS THE FOCUS RENDERED, NOT JUST THAT THE URL CHANGED. The first
     version waited on the URL and screenshotted; the Focus had not opened at
     all — `/home?focus=weekly-payroll` with no scope renders the note and
     nothing else. That is the defect this step now guards: the capability
     carries the week being worked, filled by the server. */
  await page.waitForURL(/focus=weekly-payroll/, { timeout: 15_000 })
  await expect(page).toHaveURL(/week_end=\d{4}-\d{2}-\d{2}/)
  /* ⚠️ THE PENDING WEEK RENDERS THE UPLOAD CARD, NOT THE WEEK CORE. My first
     assertion waited for `weekly-payroll-core` and failed — correctly, and not
     because the product was wrong: the week being worked has no row yet, so
     PR B's step-1 branch renders "No hours for week N yet" with the file
     input. Asserting the SCOPE is what this step is about, so it asserts the
     week it opened on. */
  await expect(page.getByText(`Week ${wk}`).first()).toBeVisible({ timeout: 15_000 })
  await expect(
    page.getByRole("heading", { name: new RegExp(`No hours for week ${wk} yet`) }),
  ).toBeVisible()
  await page.screenshot({ path: `${SHOTS}/c08-week-from-opas.png`, fullPage: true })
})

test("5a · ⚠️ typing before the list arrives says so, instead of nothing", async ({ page }) => {
  /* THE DEFECT THIS WALK FOUND. ⌘K then type immediately submitted against an
     unread capability list, matched nothing, and returned — no navigation and
     no message, on her only entrance. The read is delayed here so the window is
     reproducible rather than a timing accident. */
  await page.route("**/api/v1/opas/capabilities", async (route) => {
    await new Promise((r) => setTimeout(r, 4000))
    await route.continue()
  })
  await signIn(page)
  await page.keyboard.press("Meta+k")
  await page.getByTestId("opas-input").fill("dues report")
  await page.getByTestId("opas-input").press("Enter")
  await expect(page.getByText(/Still reading what you can do here/)).toBeVisible()
  await page.screenshot({ path: `${SHOTS}/c09-unread-list-answers.png`, fullPage: true })
  // And it did not navigate on a guess.
  expect(new URL(page.url()).pathname).toBe("/home")
})

test("7 · the command line does not invite her to type about orders", async ({ page }) => {
  /* ⚠️ FOUND IN THIS WALK'S OWN SCREENSHOT. c04 showed three payroll entries
     above a command line reading "orders · the catalog" — an instruction she
     cannot follow. No assertion had looked at the placeholder. */
  await signIn(page)
  await page.getByTestId("opas-sphere").click()
  await expect(page.getByText("Dues reports")).toBeVisible()
  const ph = await page.getByTestId("opas-input").getAttribute("placeholder")
  expect(ph).not.toContain("orders")
  expect(ph).not.toContain("catalog")
  await page.screenshot({ path: `${SHOTS}/c10-placeholder-is-hers.png`, fullPage: true })
})

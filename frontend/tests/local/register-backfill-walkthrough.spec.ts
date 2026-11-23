/**
 * The register backfill, on card 2 of `/payroll/setup`.
 *
 * sign in → the setup page → upload a register whose checks are ALL already
 * loaded → read the reply → it says how many rates were written.
 *
 * ⚠️ **THIS PAGE HAD NO WALK, AND THAT IS WHERE THE DEFECT LIVED.** #53 made
 * the server return `rates_written` — with a comment on the route explaining
 * that it is reported *"because a backfill upload inserts ZERO checks"* — and
 * no surface in the application read it. Four walks depended on
 * `lib/payroll/focus-api.ts`; not one depended on a byte of
 * `pages/payroll/payroll-setup.tsx`, so card 2's reply was covered only by
 * jsdom against a response this repository wrote itself. A client type and a
 * render derived from reading the route agree with the route whether or not
 * either is right — CLAUDE.md §11, fixtures modelled on the implementation.
 * The only thing that closes that gap is a real request.
 *
 * ⚠️ **THE UPLOAD ASSERTED HERE INSERTS NOTHING, ON PURPOSE.** Every check in
 * the file is already stored, so `0 checks` and `5 already loaded and skipped`
 * are the correct, expected readings — and the rate count is the ONLY number
 * on the page that distinguishes a successful backfill from an upload that did
 * nothing at all. That is the whole reason James asked to be told it.
 *
 * ⚠️ **THE REGISTER IS SYNTHETIC AND THE REASON IS A STANDING CONSTRAINT.**
 * Real exports stay out of the repository and out of test tenants. The
 * question this walk answers — does the client read the field the server
 * writes — does not depend on whose hours are in the file, and
 * `tests/fixtures/payroll/register_fixture` reproduces the real page geometry
 * with invented people so the parser's actual mechanism still runs.
 *
 * ⚠️ Screenshots are taken deliberately, not only on failure. The reason this
 * walk exists is that somebody looks at the sentence card 2 prints.
 *
 * Run it with both servers up, after both seeds:
 *
 *   SECRET_KEY=… DATABASE_URL=…note5a_clean python scripts/seed_week44_walkthrough.py
 *   SECRET_KEY=… DATABASE_URL=…note5a_clean \
 *     python scripts/seed_register_backfill_walkthrough.py
 *   uvicorn app.main:app --port 8000
 *   npx vite --port 5199
 *   PW_BASE_URL=http://localhost:5199 \
 *     PW_REGISTER_PDF=/var/folders/…/cc-synthetic-register.pdf \
 *     npx playwright test -c playwright.local.config.ts register-backfill-walkthrough
 */
import { expect, test, type Page } from "@playwright/test"

/** ⚠️ **ITS OWN TENANT.** The first version of this walk ran against
 *  `testco` and its five roster rows took that tenant's payroll roster from
 *  4 people to 9 — which moved the week-44 walk's
 *  `configured_member_missing_from_export` finding and turned it red. The
 *  seed owns this company outright. */
const SLUG = process.env.PW_SLUG ?? "backfillco"
/**
 * ⚠️ **THE ADMIN, NOT SUSAN, AND THAT IS THE PAGE'S OWN RULING.**
 * `/payroll/setup` is behind `<ProtectedRoute adminOnly />` with a comment
 * saying why: *"this is administering the tenant's payroll data, which is the
 * admin role's own job."* Walking it as the area-limited payroll user returns
 * a 403 page — correctly. James does card 2 himself; this walk is him.
 *
 * ⚠️ Worth knowing and NOT changed here: the register-upload ENDPOINT was
 * deliberately widened to `payroll.upload` on 2026-11-13 so Susan could
 * import the register, and the PAGE that performs it is still admin-only. The
 * endpoint is reachable by a permission the only page calling it will not
 * admit. That is a permissions decision, not a defect to fix inside a walk.
 *
 * The credential is CLAUDE.md §7's published local-dev admin, in the same
 * category as the walkthrough user's.
 */
const EMAIL = process.env.PW_WALK_EMAIL ?? "admin@backfillco.example.com"
const PASSWORD = process.env.PW_WALK_PASSWORD ?? "BackfillAdmin123!"
const SHOTS = "tests/local/shots"
/** Written by the seed, OUTSIDE the tree. Synthetic, but handled like the
 *  real one anyway: passed in by path, never committed. */
const REGISTER_PDF = process.env.PW_REGISTER_PDF ?? ""

/**
 * ⚠️ **HAND-DERIVED FROM THE FIXTURE, NOT READ BACK FROM THE WRITER.** Three
 * of the fixture's five people carry an hourly `Reg` rate (E01 @ 25.0000,
 * E02 @ 20.0000, E03 @ 18.0000); E04 and E05 are `Sal` and correctly get
 * none. All five checks are dated 11/13/2025, so there is one effective date
 * and the answer is three rows. An expectation read back from `write_rates`
 * would agree with any rule at all, including a wrong one.
 */
const EXPECT_RATES = 3
/** All five fixture checks are already stored, so all five come back duplicate. */
const EXPECT_DUPLICATES = 5

test.describe.configure({ mode: "serial" })

test.beforeAll(() => {
  expect(
    REGISTER_PDF,
    "PW_REGISTER_PDF must be the path printed by seed_register_backfill_walkthrough.py",
  ).not.toBe("")
})

async function asAdmin(page: Page) {
  await page.goto(`/?slug=${SLUG}`)
  await page.getByLabel(/email/i).fill(EMAIL)
  await page.getByLabel(/password/i).fill(PASSWORD)
  await page.getByRole("button", { name: /sign in/i }).click()
  await page.waitForURL(/\/(home|note)/, { timeout: 30_000 })
}

async function shot(page: Page, name: string) {
  await page.screenshot({ path: `${SHOTS}/${name}.png`, fullPage: false })
}

test.describe("the register backfill says how many rates it wrote", () => {
  test("card 2 reports the rate count on an upload that inserts nothing", async ({
    page,
  }) => {
    await asAdmin(page)
    await shot(page, "backfill-01-signed-in")

    // ⚠️ Navigated by URL. The setup page has no nav item of its own; its
    // entrances are Opas and the link from card 1's own flow.
    await page.goto("/payroll/setup")
    const card = page.getByTestId("register-file")
    await expect(card).toBeVisible({ timeout: 30_000 })
    await shot(page, "backfill-02-setup-card2")

    await card.setInputFiles(REGISTER_PDF)
    await page.getByTestId("register-upload").click()
    await shot(page, "backfill-03-confirm")
    await page.getByTestId("register-upload-yes").click()

    const result = page.getByTestId("register-result")
    await expect(result).toBeVisible({ timeout: 60_000 })
    await shot(page, "backfill-04-reply")

    // ── the number this walk exists for ─────────────────────────────────────
    const rates = page.getByTestId("register-rates")
    await expect(rates).toBeVisible()
    await expect(rates).toContainText(`${EXPECT_RATES} rates written`)

    // ── and the readings that would otherwise say "nothing happened" ────────
    // Both are CORRECT here. Asserted together with the rate line because the
    // point is that the rate count is what makes this page legible: without
    // it, every number on the screen is zero or a duplicate.
    await expect(result).toContainText("0 checks")
    await expect(page.getByTestId("register-duplicates")).toContainText(
      `${EXPECT_DUPLICATES} already loaded and skipped`,
    )

    // ⚠️ **THE ALL-CLEAR IS CORRECTLY ABSENT, and the first version of this
    // walk asserted it was present.** Fixture check C4 carries `Sal` AND a
    // `Union` deduction on purpose — the anomaly James asked to be reported
    // rather than resolved in code — so this register can never produce a
    // clean import. Asserting the real finding instead, because an assertion
    // written from what I expected to see rather than from what the fixture
    // contains is the same defect in a test that it would be in the page.
    await expect(page.getByTestId("register-anomalies")).toContainText(
      /salary and union dues/i,
    )
    await expect(page.getByTestId("register-clean")).toHaveCount(0)
  })

  test("a second upload says 'no new rates' rather than going silent", async ({
    page,
  }) => {
    // Immediately after the first. The rates now exist, so this upload writes
    // none — and a line that rendered only when non-zero would VANISH here,
    // which is indistinguishable from the pre-#53 page that could not report
    // rates at all.
    await asAdmin(page)
    await page.goto("/payroll/setup")
    const card = page.getByTestId("register-file")
    await expect(card).toBeVisible({ timeout: 30_000 })

    await card.setInputFiles(REGISTER_PDF)
    await page.getByTestId("register-upload").click()
    await page.getByTestId("register-upload-yes").click()

    const result = page.getByTestId("register-result")
    await expect(result).toBeVisible({ timeout: 60_000 })
    await shot(page, "backfill-05-second-upload")

    await expect(page.getByTestId("register-rates")).toContainText("No new rates")
  })
})

/**
 * S-5 Park — the DM fan-out + one escalation E2E (the arc's closing
 * witness).
 *
 * THE WITNESS: summon three tablets from the command bar (reply-DM +
 * add-note + start-quote), arrange a working set, act in each concurrently
 * — then escalate the quote ("Build this out →"), watch PARK SUSPEND
 * behind the quote Focus, close the Focus, watch PARK RESUME with the
 * other two tablets intact (suspend-and-return). Finally a deliberate exit
 * → the grace-window relaunch pill → relaunch restores the session.
 *
 * The Figma screenshot — draggable windows summoned from a command bar —
 * made real and honest as park. Desktop-only.
 *
 * Pattern mirrors command-bar-s3b-edit-canvas.spec.ts.
 */
import { test, expect, Page } from "@playwright/test"

const STAGING_BACKEND =
  process.env.BACKEND_URL || "https://sunnycresterp-staging.up.railway.app"
const PROD_API = "https://api.getbridgeable.com"
const TENANT_SLUG = "testco"
const CREDS = { email: "admin@testco.com", password: "TestAdmin123!" }

async function setupPage(page: Page) {
  await page.route(`${PROD_API}/**`, async (route) => {
    const url = route.request().url().replace(PROD_API, STAGING_BACKEND)
    try {
      await route.fulfill({ response: await route.fetch({ url }) })
    } catch {
      await route.continue()
    }
  })
  await page.goto("/", { waitUntil: "commit" })
  await page.evaluate((slug) => {
    localStorage.setItem("company_slug", slug)
  }, TENANT_SLUG)
}

async function login(page: Page) {
  await setupPage(page)
  await page.goto("/login")
  await page.waitForLoadState("load")
  const identifier = page.locator("#identifier")
  await identifier.waitFor({ state: "visible", timeout: 10_000 })
  await identifier.fill(CREDS.email)
  await page.waitForTimeout(300)
  const password = page.locator("#password")
  await password.waitFor({ state: "visible", timeout: 5_000 })
  await password.fill(CREDS.password)
  await page.getByRole("button", { name: /sign\s*in/i }).click()
  await page.waitForURL((url) => !url.pathname.includes("/login"), {
    timeout: 20_000,
  })
}

async function openCommandBar(page: Page) {
  const input = page
    .locator(
      'input[placeholder*="search" i], input[placeholder*="ask" i], input[aria-label*="command" i]',
    )
    .first()
  for (const combo of ["Meta+k", "Control+k", "Meta+k"]) {
    await page.keyboard.press(combo)
    try {
      await input.waitFor({ state: "visible", timeout: 6_000 })
      return input
    } catch {
      /* try next */
    }
  }
  await input.waitFor({ state: "visible", timeout: 6_000 })
  return input
}

/** (b) — summon a tablet on an ALREADY-OPEN palette (no Cmd+K reopen, which
 *  would toggle the bar closed). The palette stays open + clears after each
 *  summon so the next intent can be typed — the chaining property. */
async function chainSummon(
  page: Page,
  input: ReturnType<Page["locator"]>,
  query: string,
  tileName: RegExp,
) {
  await input.fill(query)
  const tile = page.getByText(tileName).first()
  await tile.waitFor({ state: "visible", timeout: 8_000 })
  await tile.click()
  // (b) palette-stays-open: the input is still present + cleared.
  await expect(input).toBeVisible()
  await expect(input).toHaveValue("")
}

test.describe("@tenant:sunnycrest Command Bar S-5 park", () => {
  test.skip(
    ({ viewport }) => (viewport?.width ?? 0) < 1024,
    "the free-form working set is a desktop-viewport concern",
  )

  test("DM fan-out: three tablets, escalate → suspend → resume, relaunch", async ({
    page,
  }) => {
    await login(page)
    await page.goto("/dashboard", { waitUntil: "load" })

    // (b) THE PEER-LAYER PROPERTY: open the bar ONCE, then chain three
    // summons while it STAYS OPEN — assemble the working set in one burst.
    const input = await openCommandBar(page)
    await chainSummon(page, input, "reply", /reply in park/i)
    await chainSummon(page, input, "note", /add a note in park/i)
    await chainSummon(page, input, "quote in park", /start a quote in park/i)
    // Bar still open + reachable after three summons; dismiss it (Esc).
    await expect(input).toBeVisible()
    await page.keyboard.press("Escape")

    const canvas = page.locator('[data-slot="park-canvas"]')
    await canvas.waitFor({ state: "visible", timeout: 8_000 })
    // Three concurrent light+escalatable acts, each live at once.
    await expect(page.getByTestId("park-reply-text")).toBeVisible()
    await expect(page.getByTestId("park-note-text")).toBeVisible()
    await expect(page.getByTestId("park-quote-escalate")).toBeVisible()

    // Act in the light tablets concurrently.
    await page.getByTestId("park-reply-text").fill("Thanks — sending that over.")
    await page.getByTestId("park-note-text").fill("Wants updated price list next visit.")

    await page.screenshot({
      path: "tests/e2e/screenshots/s5-park-fanout-witness.png",
      fullPage: false,
    })

    // THE CROSSING — escalate the quote. Park SUSPENDS behind the Focus.
    await page.getByTestId("park-quote-escalate").click()
    const focus = page.locator('[data-slot="quote-focus"]')
    await focus.waitFor({ state: "visible", timeout: 8_000 })
    // Park is suspended — the canvas is not mounted while the Focus is up.
    await expect(canvas).toBeHidden({ timeout: 8_000 })

    // Close the Focus → park RESUMES with the two other tablets intact.
    await page.keyboard.press("Escape")
    await expect(focus).toBeHidden({ timeout: 8_000 })
    await expect(page.getByTestId("park-reply-text")).toBeVisible({
      timeout: 8_000,
    })
    await expect(page.getByTestId("park-reply-text")).toHaveValue(
      "Thanks — sending that over.",
    )

    await page.screenshot({
      path: "tests/e2e/screenshots/s5-park-resume-witness.png",
      fullPage: false,
    })

    // Deliberate exit → grace-window relaunch pill → relaunch restores it.
    await page.getByTestId("park-exit").click()
    const pill = page.getByTestId("park-relaunch")
    await pill.waitFor({ state: "visible", timeout: 8_000 })
    await pill.click()
    await expect(page.getByTestId("park-reply-text")).toBeVisible({
      timeout: 8_000,
    })
  })
})

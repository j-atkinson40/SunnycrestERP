/**
 * Command Bar S-3a (§4.5) — the Act→Decide crossing E2E.
 *
 * THE WITNESS THAT MATTERS: type a quote → the S-2 surfaces appear in
 * the command bar → click "Build this out →" → the COMMAND BAR CLOSES
 * (§5.15 mutual-exclusivity) and a full-screen quote Focus opens, showing
 * the SAME $4,215 preview + price-list, now re-hosted as the Focus's
 * core + pin. Act surface closes, Decide surface opens, same content —
 * that crossing is S-3a's whole deliverable.
 *
 * Desktop-only (surfaces + the crossing are a desktop-viewport concern;
 * the Focus's own 3-tier cascade handles mobile separately).
 *
 * Pattern mirrors command-bar-s2-contextual-surfaces.spec.ts.
 */
import { test, expect, Page } from "@playwright/test"

const STAGING_BACKEND =
  process.env.BACKEND_URL || "https://sunnycresterp-staging.up.railway.app"
const PROD_API = "https://api.getbridgeable.com"
const TENANT_SLUG = "testco"
const CREDS = { email: "admin@testco.com", password: "TestAdmin123!" }
const QUOTE_TEXT = "quote 3 Monticello for Hopkins"

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
      // try the next combo
    }
  }
  await input.waitFor({ state: "visible", timeout: 6_000 })
  return input
}

test.describe("@tenant:sunnycrest Command Bar S-3a Focus escalation", () => {
  test.skip(
    ({ viewport }) => (viewport?.width ?? 0) < 1024,
    "the crossing is a desktop-viewport concern",
  )

  test("Build this out → closes the bar and opens the quote Focus with the re-hosted preview", async ({
    page,
  }) => {
    await login(page)
    await page.goto("/dashboard", { waitUntil: "load" })

    // Drive the S-2 chain: Cmd+K → Compose → type a quote → surfaces.
    const paletteInput = await openCommandBar(page)
    await paletteInput.fill("quote")
    const composeRow = page.getByText("Bridgeable Compose").first()
    await composeRow.waitFor({ state: "visible", timeout: 8_000 })
    await composeRow.click()
    const overlay = page.getByPlaceholder(
      /Continental for Hopkins|describe in your own words/i,
    )
    await overlay.waitFor({ state: "visible", timeout: 8_000 })
    await overlay.fill(QUOTE_TEXT)

    // The escalation affordance appears on the committed quote intent.
    const buildOut = page.getByRole("button", { name: /build this out/i })
    await buildOut.waitFor({ state: "visible", timeout: 20_000 })

    // Precondition: the command bar IS open right now.
    await expect(paletteInput).toBeVisible()

    // THE CROSSING.
    await buildOut.click()

    // §5.15 — the command bar CLOSES (its input unmounts with it).
    await expect(paletteInput).toBeHidden({ timeout: 8_000 })

    // The quote Focus is open, re-hosting the S-2 preview as its core.
    const focus = page.locator('[data-slot="quote-focus"]')
    await focus.waitFor({ state: "visible", timeout: 8_000 })
    const rehosted = focus.getByTestId("quote-preview-surface")
    await rehosted.waitFor({ state: "visible", timeout: 20_000 })
    // Same order-resolver price as in the bar (Monticello ×3 @ $1,405).
    await expect(focus).toContainText("$4,215.00", { timeout: 20_000 })
    // The price-list pin re-hosted alongside.
    await expect(
      focus.getByTestId("price-list-reference-surface"),
    ).toBeVisible({ timeout: 20_000 })

    await page.screenshot({
      path: "tests/e2e/screenshots/s3a-crossing-witness.png",
      fullPage: false,
    })

    // Backdrop dismiss returns to the underlying page (Focus closes).
    await page.keyboard.press("Escape")
    await expect(focus).toBeHidden({ timeout: 8_000 })
  })
})

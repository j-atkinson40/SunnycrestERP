/**
 * Command Bar S-3b (§4.5) — the EDITABLE quote core E2E.
 *
 * S-3a witnessed the crossing into a DISPLAY core; S-3b witnesses the
 * EDITABLE core it was replaced with. THE WITNESS THAT MATTERS: escalate a
 * quote → the Focus opens the edit canvas seeded with the extracted line →
 * edit the quantity and the SUBTOTAL MOVES → add a second line through the
 * portaled combobox (THE pointer-events proof — a dropdown clicked in the
 * production Focus tier, the AncillaryPoolPin-class landmine) → remove a
 * line → RELOAD and the draft SURVIVES (persistence option b). The
 * NO-QUOTE-DATA-BEFORE-SAVE invariant is proven rigorously by the backend
 * (test_focus_draft_persistence); here the UI corollary is that Save is
 * present-but-deferred and the draft is durable without it.
 *
 * Desktop-only (the crossing + edit canvas are a desktop-viewport
 * concern; the Focus's own 3-tier cascade handles mobile separately).
 *
 * Pattern mirrors command-bar-s3a-focus-escalation.spec.ts.
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

/** Escalate a typed quote into the Focus edit canvas. Reused across the
 *  crossing + the reload-survival tests. */
async function escalateToEditCanvas(page: Page) {
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
  const buildOut = page.getByRole("button", { name: /build this out/i })
  await buildOut.waitFor({ state: "visible", timeout: 20_000 })
  await buildOut.click()
  await expect(paletteInput).toBeHidden({ timeout: 8_000 })
  const canvas = page.getByTestId("quote-edit-canvas")
  await canvas.waitFor({ state: "visible", timeout: 12_000 })
  return canvas
}

test.describe("@tenant:sunnycrest Command Bar S-3b edit canvas", () => {
  test.skip(
    ({ viewport }) => (viewport?.width ?? 0) < 1024,
    "the edit canvas is a desktop-viewport concern",
  )

  test("edit canvas opens seeded, a qty edit moves the subtotal, and add/remove work", async ({
    page,
  }) => {
    await login(page)
    await page.goto("/dashboard", { waitUntil: "load" })

    const canvas = await escalateToEditCanvas(page)

    // Seeded from the extraction: one editable line (Monticello ×3),
    // subtotal at the order-resolver price ($1,405 × 3 = $4,215.00).
    await expect(canvas.getByTestId("quote-line-row")).toHaveCount(1)
    await expect(canvas.getByTestId("quote-line-qty")).toHaveValue("3")
    await expect(canvas.getByTestId("quote-subtotal")).toHaveText(
      "$4,215.00",
      { timeout: 20_000 },
    )

    // THE TOTAL MOVES — change qty 3 → 5 ($1,405 × 5 = $7,025.00).
    const qty = canvas.getByTestId("quote-line-qty")
    await qty.fill("5")
    await expect(canvas.getByTestId("quote-subtotal")).toHaveText(
      "$7,025.00",
      { timeout: 20_000 },
    )

    // THE POINTER-EVENTS PROOF — the portaled add-line combobox is
    // clickable in the production Focus tier (would be dead if the tier
    // contract were violated). Open it + add a second line.
    await canvas.getByTestId("quote-add-line").click()
    const popover = page.getByTestId("quote-add-line-popover")
    await popover.waitFor({ state: "visible", timeout: 8_000 })
    const addInput = page.getByTestId("quote-add-line-input")
    await addInput.fill("Continental")
    await addInput.press("Enter")
    await expect(canvas.getByTestId("quote-line-row")).toHaveCount(2, {
      timeout: 8_000,
    })

    await page.screenshot({
      path: "tests/e2e/screenshots/s3b-edit-canvas-witness.png",
      fullPage: false,
    })

    // REMOVE the second line — back to one.
    await canvas.getByTestId("quote-line-remove").last().click()
    await expect(canvas.getByTestId("quote-line-row")).toHaveCount(1, {
      timeout: 8_000,
    })

    // Save is the one chrome primary — present but DEFERRED (no quote
    // materializes; the invariant is backend-proven).
    await expect(canvas.getByTestId("quote-save")).toBeDisabled()
  })

  test("the edited draft SURVIVES a reload (persistence option b)", async ({
    page,
  }) => {
    await login(page)
    await page.goto("/dashboard", { waitUntil: "load" })

    const canvas = await escalateToEditCanvas(page)
    // Edit qty 3 → 4 so the surviving state is distinguishable from a
    // fresh seed ($1,405 × 4 = $5,620.00).
    await canvas.getByTestId("quote-line-qty").fill("4")
    await expect(canvas.getByTestId("quote-subtotal")).toHaveText(
      "$5,620.00",
      { timeout: 20_000 },
    )
    // Let the 300ms debounced draft persist land.
    await page.waitForTimeout(1_200)

    // RELOAD — the URL carries only ?focus=quote-building; params drop.
    // The draft must hydrate from focus_sessions.draft_state.
    await page.reload({ waitUntil: "load" })

    const reloaded = page.getByTestId("quote-edit-canvas")
    await reloaded.waitFor({ state: "visible", timeout: 15_000 })
    // The edited quantity + repriced subtotal survived — proving the
    // draft is durable WITHOUT a quote ever materializing.
    await expect(reloaded.getByTestId("quote-line-qty")).toHaveValue("4")
    await expect(reloaded.getByTestId("quote-subtotal")).toHaveText(
      "$5,620.00",
      { timeout: 20_000 },
    )

    await page.screenshot({
      path: "tests/e2e/screenshots/s3b-reload-survives-witness.png",
      fullPage: false,
    })
  })
})

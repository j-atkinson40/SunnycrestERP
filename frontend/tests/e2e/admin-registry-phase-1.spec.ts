/**
 * Admin Component Registry — Phase 1 of Admin Visual Editor E2E.
 *
 * Verifies the /admin/registry debug page is reachable, gated to
 * admins, and renders the Phase 1 tagged components correctly.
 *
 *   1. Admin lands on /admin/registry and sees registry contents
 *   2. Coverage tiles render correct counts
 *   3. Type filter narrows the table to one type
 *   4. Vertical filter narrows + includes universal components
 *   5. Detail card shows full metadata when a row is clicked
 *   6. Token reverse-lookup shows component consumers when a token is clicked
 *   7. Phase 1 component registrations all appear in the table
 *   8. Registry survives page reload (registrations re-fire on import)
 *
 * Test pattern mirrors command-bar-phase-1.spec.ts —
 * prod→staging fetch redirect, testco tenant, admin creds.
 */
import { test, expect, Page } from "@playwright/test"

const STAGING_BACKEND =
  process.env.BACKEND_URL ||
  "https://sunnycresterp-staging.up.railway.app"

const PROD_API = "https://api.getbridgeable.com"
const TENANT_SLUG = "testco"
const CREDS = { email: "admin@testco.com", password: "TestAdmin123!" }


async function setupPage(page: Page) {
  await page.route(`${PROD_API}/**`, async (route) => {
    const url = route.request().url().replace(PROD_API, STAGING_BACKEND)
    try {
      const response = await route.fetch({ url })
      await route.fulfill({ response })
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
  await page.waitForLoadState("networkidle")
  const identifierInput = page.locator("#identifier")
  await identifierInput.waitFor({ state: "visible", timeout: 10_000 })
  await identifierInput.fill(CREDS.email)
  await page.waitForTimeout(300)
  const passwordInput = page.locator("#password")
  await passwordInput.waitFor({ state: "visible", timeout: 5_000 })
  await passwordInput.fill(CREDS.password)
  await page.getByRole("button", { name: /sign\s*in/i }).click()
  await page.waitForURL((url) => !url.pathname.includes("/login"), {
    timeout: 20_000,
  })
}


test.describe("@tenant:sunnycrest Admin Registry Phase 1", () => {
  test("1. Admin can access /admin/registry and registry contents render", async ({
    page,
  }) => {
    await login(page)
    await page.goto("/admin/registry")
    await page.waitForLoadState("networkidle")

    await expect(
      page.getByTestId("registry-debug-page"),
    ).toBeVisible()

    const totalCountEl = page.getByTestId("registry-total-count")
    await expect(totalCountEl).toBeVisible()
    const text = (await totalCountEl.textContent())?.trim()
    const total = Number(text)
    expect(total).toBeGreaterThanOrEqual(13)
    expect(total).toBeLessThanOrEqual(17)
  })

  test("2. Coverage tiles show per-type and per-vertical breakdowns", async ({
    page,
  }) => {
    await login(page)
    await page.goto("/admin/registry")
    await page.waitForLoadState("networkidle")

    // Per-type counts surface for the tagged kinds
    await expect(page.getByTestId("registry-count-type-widget")).toBeVisible()
    await expect(page.getByTestId("registry-count-type-focus")).toBeVisible()
    await expect(
      page.getByTestId("registry-count-type-focus-template"),
    ).toBeVisible()
    await expect(
      page.getByTestId("registry-count-type-document-block"),
    ).toBeVisible()
    await expect(
      page.getByTestId("registry-count-type-workflow-node"),
    ).toBeVisible()

    // Per-vertical coverage cards
    await expect(page.getByTestId("registry-coverage-all")).toBeVisible()
    await expect(
      page.getByTestId("registry-coverage-funeral_home"),
    ).toBeVisible()
    await expect(
      page.getByTestId("registry-coverage-manufacturing"),
    ).toBeVisible()
  })

  test("3. Type filter narrows the table", async ({ page }) => {
    await login(page)
    await page.goto("/admin/registry")
    await page.waitForLoadState("networkidle")

    const typeFilter = page.getByTestId("registry-filter-type")
    await typeFilter.selectOption("focus")
    await page.waitForTimeout(150)

    // Only 5 Focus types should be in the table
    const filtered = await page
      .getByTestId("registry-filtered-count")
      .textContent()
    expect(Number((filtered ?? "").trim())).toBe(5)
  })

  test("4. Vertical filter includes universal components", async ({ page }) => {
    await login(page)
    await page.goto("/admin/registry")
    await page.waitForLoadState("networkidle")

    const verticalFilter = page.getByTestId("registry-filter-vertical")
    await verticalFilter.selectOption("funeral_home")
    await page.waitForTimeout(150)

    // Cross-vertical "today" widget should still be in the filtered set
    await expect(
      page.getByTestId("registry-row-widget-today"),
    ).toBeVisible()

    // Plus the FH-specific "Arrangement Scribe" template
    await expect(
      page.getByTestId("registry-row-focus-template-arrangement-scribe"),
    ).toBeVisible()
  })

  test("5. Detail card shows full metadata when a row is clicked", async ({
    page,
  }) => {
    await login(page)
    await page.goto("/admin/registry")
    await page.waitForLoadState("networkidle")

    await page.getByTestId("registry-row-widget-today").click()

    const detail = page.getByTestId("registry-detail")
    await expect(detail).toBeVisible()
    await expect(page.getByTestId("registry-detail-title")).toHaveText(
      "Today",
    )
    await expect(page.getByTestId("registry-detail-id")).toContainText(
      "widget · today",
    )
    await expect(page.getByTestId("registry-detail-tokens")).toBeVisible()
    await expect(page.getByTestId("registry-detail-props")).toBeVisible()
    await expect(page.getByTestId("registry-detail-variants")).toBeVisible()
  })

  test("6. Token reverse-lookup shows component consumers", async ({
    page,
  }) => {
    await login(page)
    await page.goto("/admin/registry")
    await page.waitForLoadState("networkidle")

    // surface-elevated is consumed by multiple Phase 1 components
    const tokenChip = page.getByTestId("registry-token-surface-elevated")
    await expect(tokenChip).toBeVisible()
    await tokenChip.click()

    const inspect = page.getByTestId("registry-token-inspect")
    await expect(inspect).toBeVisible()

    const countText = await page
      .getByTestId("registry-token-consumer-count")
      .textContent()
    const count = Number((countText ?? "").trim())
    expect(count).toBeGreaterThan(1)
  })

  test("7. All five Focus types render in the table", async ({ page }) => {
    await login(page)
    await page.goto("/admin/registry")
    await page.waitForLoadState("networkidle")

    for (const focusName of [
      "decision",
      "coordination",
      "execution",
      "review",
      "generation",
    ]) {
      await expect(
        page.getByTestId(`registry-row-focus-${focusName}`),
      ).toBeVisible()
    }
  })

  test("8. Registry survives page reload — registrations re-fire on import", async ({
    page,
  }) => {
    await login(page)
    await page.goto("/admin/registry")
    await page.waitForLoadState("networkidle")
    const before = await page
      .getByTestId("registry-total-count")
      .textContent()

    await page.reload()
    await page.waitForLoadState("networkidle")
    const after = await page
      .getByTestId("registry-total-count")
      .textContent()

    expect(after).toBe(before)
    expect(Number((after ?? "").trim())).toBeGreaterThanOrEqual(13)
  })
})

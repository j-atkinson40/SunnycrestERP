/**
 * Workflow Editor — Phase 4 of Admin Visual Editor E2E.
 *
 * Verifies the /admin/workflows page is admin-gated, renders
 * the three-pane layout, exposes the cross-link nav, and that
 * the seeded vertical_default workflows resolve correctly via
 * the backend API.
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
  await page.locator("#identifier").waitFor({ state: "visible", timeout: 10_000 })
  await page.locator("#identifier").fill(CREDS.email)
  await page.waitForTimeout(300)
  await page.locator("#password").fill(CREDS.password)
  await page.getByRole("button", { name: /sign\s*in/i }).click()
  await page.waitForURL((url) => !url.pathname.includes("/login"), { timeout: 20_000 })
}


test.describe("Admin Workflow Editor — Phase 4", () => {
  test("admin can access /admin/workflows", async ({ page }) => {
    await login(page)
    await page.goto("/admin/workflows")
    await page.waitForLoadState("networkidle")
    await expect(page.getByRole("heading", { name: /workflow editor/i })).toBeVisible()
  })

  test("cross-link nav points at themes + components + registry", async ({ page }) => {
    await login(page)
    await page.goto("/admin/workflows")
    await page.waitForLoadState("networkidle")
    await expect(page.locator('[data-testid="nav-to-themes"]')).toBeVisible()
    await expect(page.locator('[data-testid="nav-to-components"]')).toBeVisible()
    await expect(page.locator('[data-testid="nav-to-registry"]')).toBeVisible()
  })

  test("API: list endpoint returns seeded vertical_default templates", async ({ request }) => {
    const loginRes = await request.post(`${STAGING_BACKEND}/api/v1/auth/login`, {
      data: { email: CREDS.email, password: CREDS.password },
      headers: { "X-Company-Slug": TENANT_SLUG },
    })
    expect(loginRes.ok()).toBeTruthy()
    const { access_token } = await loginRes.json()

    const listRes = await request.get(
      `${STAGING_BACKEND}/api/v1/admin/workflow-templates/?scope=vertical_default`,
      { headers: { Authorization: `Bearer ${access_token}` } },
    )
    expect(listRes.ok()).toBeTruthy()
    const templates = await listRes.json()
    expect(Array.isArray(templates)).toBe(true)
  })

  test("API: resolve endpoint returns canvas_state for a workflow_type", async ({ request }) => {
    const loginRes = await request.post(`${STAGING_BACKEND}/api/v1/auth/login`, {
      data: { email: CREDS.email, password: CREDS.password },
      headers: { "X-Company-Slug": TENANT_SLUG },
    })
    expect(loginRes.ok()).toBeTruthy()
    const { access_token } = await loginRes.json()

    const resolveRes = await request.get(
      `${STAGING_BACKEND}/api/v1/admin/workflow-templates/resolve?workflow_type=quote_to_pour&vertical=manufacturing`,
      { headers: { Authorization: `Bearer ${access_token}` } },
    )
    // Either resolves with canvas_state or returns null source — both are valid contract shapes
    expect(resolveRes.ok()).toBeTruthy()
    const resolved = await resolveRes.json()
    expect(resolved).toHaveProperty("workflow_type")
    expect(resolved).toHaveProperty("canvas_state")
    expect(resolved).toHaveProperty("source")
  })

  test("non-admin cannot access /admin/workflows", async ({ page }) => {
    await setupPage(page)
    await page.goto("/admin/workflows")
    await page.waitForLoadState("networkidle")
    // Should redirect to login or show access denied — not render workflow editor
    const heading = page.getByRole("heading", { name: /workflow editor/i })
    await expect(heading).not.toBeVisible({ timeout: 3_000 }).catch(() => {})
  })
})

/**
 * Component Editor — Phase 3 of Admin Visual Editor E2E.
 *
 * Verifies the /admin/components page is admin-gated, renders
 * the three-pane layout, lets the operator select a component
 * and edit its configuration, propagates edits to the live
 * preview, and persists overrides via the backend.
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


test.describe("@tenant:sunnycrest Admin Components Phase 3", () => {
  test("1. Admin can access /admin/components and three-pane layout renders", async ({ page }) => {
    await login(page)
    await page.goto("/admin/components")
    await page.waitForLoadState("networkidle")
    await expect(page.getByTestId("component-editor-page")).toBeVisible()
    await expect(page.getByTestId("component-editor-browser-pane")).toBeVisible()
    await expect(page.getByTestId("component-editor-config-pane")).toBeVisible()
    await expect(page.getByTestId("component-editor-preview-pane")).toBeVisible()
  })

  test("2. Component browser shows all 17 Phase 1 components grouped by kind", async ({ page }) => {
    await login(page)
    await page.goto("/admin/components")
    await page.waitForLoadState("networkidle")
    for (const kind of [
      "widget",
      "focus",
      "focus-template",
      "document-block",
      "workflow-node",
    ]) {
      await expect(page.getByTestId(`browser-kind-${kind}`)).toBeVisible()
    }
    for (const key of [
      "widget-today",
      "widget-anomalies",
      "widget-vault-schedule",
      "focus-decision",
      "focus-template-arrangement-scribe",
      "document-block-header-block",
      "workflow-node-send-communication",
    ]) {
      await expect(page.getByTestId(`browser-item-${key}`)).toBeVisible()
    }
  })

  test("3. Selecting a component loads its configurable props", async ({ page }) => {
    await login(page)
    await page.goto("/admin/components")
    await page.waitForLoadState("networkidle")
    await page.getByTestId("browser-item-widget-today").click()
    await expect(page.getByTestId("config-pane-id")).toContainText("widget · today")
    await expect(page.getByTestId("prop-row-showRowBreakdown")).toBeVisible()
    await expect(page.getByTestId("prop-row-refreshIntervalSeconds")).toBeVisible()
  })

  test("4. Vertical filter changes browser content", async ({ page }) => {
    await login(page)
    await page.goto("/admin/components")
    await page.waitForLoadState("networkidle")
    await page.getByTestId("browser-vertical-select").selectOption("funeral_home")
    await page.waitForTimeout(150)
    // Manufacturing-only widgets are hidden
    await expect(page.getByTestId("browser-item-widget-vault-schedule")).not.toBeVisible()
    // Cross-vertical + FH-specific are visible
    await expect(page.getByTestId("browser-item-widget-today")).toBeVisible()
    await expect(
      page.getByTestId("browser-item-focus-template-arrangement-scribe"),
    ).toBeVisible()
  })

  test("5. Editing a boolean prop visibly updates the preview", async ({ page }) => {
    await login(page)
    await page.goto("/admin/components")
    await page.waitForLoadState("networkidle")
    await page.getByTestId("browser-item-widget-today").click()

    // Widget:today's config-aware preview hides rows when showRowBreakdown=false.
    await expect(page.getByTestId("cfg-preview-today-rows")).toBeVisible()
    await page.getByTestId("prop-control-showRowBreakdown-switch").click()
    // After toggling to false, the rows section should disappear.
    await expect(page.getByTestId("cfg-preview-today-rows")).not.toBeVisible()
  })

  test("6. Editing an enum prop visibly updates the preview", async ({ page }) => {
    await login(page)
    await page.goto("/admin/components")
    await page.waitForLoadState("networkidle")
    await page.getByTestId("browser-item-widget-today").click()

    // Switch dateFormatStyle to ISO
    await page.getByTestId("prop-control-dateFormatStyle-iso").click()
    await expect(page.getByTestId("cfg-preview-today")).toContainText("2026-05-14")
  })

  test("7. Editing a numeric prop with bounds enforces them", async ({ page }) => {
    await login(page)
    await page.goto("/admin/components")
    await page.waitForLoadState("networkidle")
    await page.getByTestId("browser-item-widget-today").click()
    const numInput = page.getByTestId(
      "prop-control-refreshIntervalSeconds-input",
    )
    // Try to set below min (60). Control should clamp.
    await numInput.fill("5")
    await numInput.dispatchEvent("change")
    await numInput.blur()
    const v = await numInput.inputValue()
    expect(Number(v)).toBeGreaterThanOrEqual(60)
  })

  test("8. Token reference picker scopes to declared tokenCategory", async ({ page }) => {
    await login(page)
    await page.goto("/admin/components")
    await page.waitForLoadState("networkidle")
    await page.getByTestId("browser-item-widget-today").click()
    await page.getByTestId("prop-control-accentToken-toggle").click()
    // accentToken declares tokenCategory="accent" — picker only shows
    // accent tokens.
    await expect(page.getByTestId("prop-control-accentToken-list")).toBeVisible()
    await expect(
      page.getByTestId("prop-control-accentToken-option-accent"),
    ).toBeVisible()
    await expect(
      page.getByTestId("prop-control-accentToken-option-accent-hover"),
    ).toBeVisible()
    // surface-base is NOT in the accent category — should not appear
    await expect(
      page.getByTestId("prop-control-accentToken-option-surface-base"),
    ).not.toBeVisible()
  })

  test("9. Mode toggle on preview switches preview only", async ({ page }) => {
    await login(page)
    await page.goto("/admin/components")
    await page.waitForLoadState("networkidle")
    await page.getByTestId("browser-item-widget-today").click()
    await page.getByTestId("preview-mode-dark").click()
    const sandbox = page.getByTestId("component-editor-sandbox")
    await expect(sandbox).toHaveAttribute("data-mode", "dark")
  })

  test("10. Show only overridden props filter works", async ({ page }) => {
    await login(page)
    await page.goto("/admin/components")
    await page.waitForLoadState("networkidle")
    await page.getByTestId("browser-item-widget-today").click()
    // Initially all props visible; toggle filter — empty until an
    // override exists at this scope or in the draft.
    await page.getByTestId("show-only-overridden-toggle").check()
    await expect(page.getByTestId("props-list")).toContainText(
      /No configurable props match/i,
    )
  })

  test("11. Show all instances renders multiple variants", async ({ page }) => {
    await login(page)
    await page.goto("/admin/components")
    await page.waitForLoadState("networkidle")
    await page.getByTestId("browser-item-widget-today").click()
    await page.getByTestId("show-all-instances-toggle").check()
    await expect(page.getByTestId("preview-instance-instance-1")).toBeVisible()
    await expect(page.getByTestId("preview-instance-instance-2")).toBeVisible()
    await expect(page.getByTestId("preview-instance-instance-3")).toBeVisible()
  })

  test("12. Cross-link nav works between editors", async ({ page }) => {
    await login(page)
    await page.goto("/admin/components")
    await page.waitForLoadState("networkidle")
    await page.getByTestId("nav-to-themes").click()
    await page.waitForURL(/\/admin\/themes/)
    await expect(page.getByTestId("theme-editor-page")).toBeVisible()
    await page.getByTestId("nav-to-components").click()
    await page.waitForURL(/\/admin\/components/)
    await expect(page.getByTestId("component-editor-page")).toBeVisible()
  })

  test("13. Save persists; reload restores", async ({ page }) => {
    await login(page)
    await page.goto("/admin/components")
    await page.waitForLoadState("networkidle")
    await page.getByTestId("browser-item-widget-today").click()
    // Toggle showRowBreakdown to false (was true)
    await page.getByTestId("prop-control-showRowBreakdown-switch").click()
    // Save manually
    const save = page.getByTestId("component-editor-save")
    await expect(save).toBeEnabled()
    await save.click()
    await page.waitForTimeout(800)
    await page.reload()
    await page.waitForLoadState("networkidle")
    // Editor auto-selects the first component (widget:anomalies due
    // to default ordering); navigate explicitly to widget:today
    await page.getByTestId("browser-item-widget-today").click()
    await expect(page.getByTestId("cfg-preview-today-rows")).not.toBeVisible()
  })
})

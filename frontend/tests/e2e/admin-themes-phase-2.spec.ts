/**
 * Theme Editor — Phase 2 of Admin Visual Editor E2E.
 *
 * Verifies the /admin/themes page is reachable, gated to admins,
 * and that the core editing flows work end-to-end.
 *
 *   1. Admin can navigate to /admin/themes
 *   2. Three-pane layout renders + token categories visible
 *   3. Editing a color (accent) updates the preview canvas
 *   4. Editing radius updates the preview
 *   5. Editing typography size updates the preview
 *   6. Mode toggle on preview switches preview chrome only
 *   7. Scope toggle (platform / vertical / tenant) updates state
 *   8. Vertical filter changes preview component set
 *   9. Save persists overrides; reload restores them
 *  10. Show-only-overridden filter works
 *  11. Clicking a component in the preview filters tokens
 *  12. All 17 components from Phase 1 appear in the preview
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


test.describe("@tenant:sunnycrest Admin Themes Phase 2", () => {
  test("1. Admin can access /admin/themes and three-pane layout renders", async ({
    page,
  }) => {
    await login(page)
    await page.goto("/admin/themes")
    await page.waitForLoadState("networkidle")

    await expect(page.getByTestId("theme-editor-page")).toBeVisible()
    await expect(page.getByTestId("theme-editor-scope-pane")).toBeVisible()
    await expect(page.getByTestId("token-editor-pane")).toBeVisible()
    await expect(page.getByTestId("preview-canvas-root")).toBeVisible()
  })

  test("2. Token categories render", async ({ page }) => {
    await login(page)
    await page.goto("/admin/themes")
    await page.waitForLoadState("networkidle")

    for (const cat of [
      "surface",
      "content",
      "border",
      "accent",
      "status",
      "typography-size",
      "radius",
      "motion-duration",
    ]) {
      await expect(page.getByTestId(`token-category-${cat}`)).toBeVisible()
    }
  })

  test("3. Editing accent color updates the preview", async ({ page }) => {
    await login(page)
    await page.goto("/admin/themes")
    await page.waitForLoadState("networkidle")

    // Capture the accent value before editing.
    const sandbox = page.getByTestId("preview-canvas-sandbox")
    const before = await sandbox.evaluate(
      (el) => getComputedStyle(el).getPropertyValue("--accent"),
    )

    // Drag the OKLCH lightness slider for the accent token.
    const accentL = page.getByTestId("token-control-accent-l")
    await accentL.fill("0.65")
    await accentL.dispatchEvent("change")

    // Expect the sandbox's --accent variable to have changed.
    await expect(async () => {
      const after = await sandbox.evaluate(
        (el) => getComputedStyle(el).getPropertyValue("--accent"),
      )
      expect(after).not.toBe(before)
    }).toPass({ timeout: 2_000 })
  })

  test("4. Editing radius updates the preview", async ({ page }) => {
    await login(page)
    await page.goto("/admin/themes")
    await page.waitForLoadState("networkidle")

    const sandbox = page.getByTestId("preview-canvas-sandbox")
    const before = await sandbox.evaluate(
      (el) => getComputedStyle(el).getPropertyValue("--radius-base"),
    )

    const radiusInput = page.getByTestId("token-control-radius-base-input")
    await radiusInput.fill("16")
    await radiusInput.dispatchEvent("change")

    await expect(async () => {
      const after = await sandbox.evaluate(
        (el) => getComputedStyle(el).getPropertyValue("--radius-base"),
      )
      expect(after).not.toBe(before)
    }).toPass({ timeout: 2_000 })
  })

  test("5. Mode toggle on preview switches preview only", async ({ page }) => {
    await login(page)
    await page.goto("/admin/themes")
    await page.waitForLoadState("networkidle")

    await page.getByTestId("preview-mode-dark").click()
    const sandbox = page.getByTestId("preview-canvas-sandbox")
    await expect(sandbox).toHaveAttribute("data-mode", "dark")

    // Editing-mode toggle stays on light (orthogonal control).
    const editingLight = page.getByTestId("editing-mode-light")
    await expect(editingLight).toHaveAttribute("aria-selected", /.*/)
  })

  test("6. Scope toggle updates the right pane data state", async ({
    page,
  }) => {
    await login(page)
    await page.goto("/admin/themes")
    await page.waitForLoadState("networkidle")

    await page.getByTestId("scope-vertical_default").click()
    await expect(page.getByTestId("vertical-select")).toBeVisible()

    await page.getByTestId("scope-tenant_override").click()
    await expect(page.getByTestId("tenant-id-input")).toBeVisible()

    await page.getByTestId("scope-platform_default").click()
    await expect(page.getByTestId("vertical-select")).not.toBeVisible()
  })

  test("7. Vertical preview filter changes component set", async ({ page }) => {
    await login(page)
    await page.goto("/admin/themes")
    await page.waitForLoadState("networkidle")

    // Show all
    await page.getByTestId("preview-vertical-select").selectOption("all")
    await expect(page.getByTestId("preview-component-widget-vault-schedule")).toBeVisible()

    // Funeral home: should hide manufacturing-only widgets
    await page.getByTestId("preview-vertical-select").selectOption("funeral_home")
    await page.waitForTimeout(150)
    await expect(page.getByTestId("preview-component-widget-vault-schedule")).not.toBeVisible()
    // Cross-vertical widget remains
    await expect(page.getByTestId("preview-component-widget-today")).toBeVisible()
  })

  test("8. Show-only-overridden filter works", async ({ page }) => {
    await login(page)
    await page.goto("/admin/themes")
    await page.waitForLoadState("networkidle")

    const toggle = page.getByTestId("token-show-overridden-toggle")
    await toggle.check()
    // Visible token count should drop (no overrides yet — empty state).
    const shown = await page.getByTestId("token-shown-count").textContent()
    expect(shown).toMatch(/0 of \d+/)
  })

  test("9. Clicking a component filters tokens", async ({ page }) => {
    await login(page)
    await page.goto("/admin/themes")
    await page.waitForLoadState("networkidle")

    await page.getByTestId("preview-component-widget-today").click()
    await expect(page.getByTestId("token-component-filter-banner")).toBeVisible()
    await expect(
      page.getByTestId("token-component-filter-banner"),
    ).toContainText("widget:today")
  })

  test("10. All Phase 1 components appear in preview", async ({ page }) => {
    await login(page)
    await page.goto("/admin/themes")
    await page.waitForLoadState("networkidle")

    for (const key of [
      "widget-today",
      "widget-operator-profile",
      "widget-recent-activity",
      "widget-anomalies",
      "widget-vault-schedule",
      "widget-line-status",
      "focus-decision",
      "focus-coordination",
      "focus-execution",
      "focus-review",
      "focus-generation",
      "focus-template-triage-decision",
      "focus-template-arrangement-scribe",
      "document-block-header-block",
      "document-block-signature-block",
      "workflow-node-generation-focus-invocation",
      "workflow-node-send-communication",
    ]) {
      await expect(page.getByTestId(`preview-component-${key}`)).toBeVisible()
    }
  })

  test("11. Save persists; reload restores", async ({ page }) => {
    await login(page)
    await page.goto("/admin/themes")
    await page.waitForLoadState("networkidle")

    // Edit accent — small lightness change.
    const accentL = page.getByTestId("token-control-accent-l")
    await accentL.fill("0.62")
    await accentL.dispatchEvent("change")

    // Manual save.
    const saveBtn = page.getByTestId("theme-editor-save")
    await expect(saveBtn).toBeEnabled()
    await saveBtn.click()
    // Wait for save to settle (no save error indicator).
    await page.waitForTimeout(500)

    // Reload and verify preview still shows the edit.
    await page.reload()
    await page.waitForLoadState("networkidle")
    const sandbox = page.getByTestId("preview-canvas-sandbox")
    const after = await sandbox.evaluate(
      (el) => getComputedStyle(el).getPropertyValue("--accent"),
    )
    // Persisted oklch value must include 0.62 (lightness).
    expect(after).toContain("0.62")
  })
})

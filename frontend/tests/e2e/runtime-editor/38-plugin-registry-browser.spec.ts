/**
 * Gate 38 — Plugin Registry browser (R-8.y.d).
 *
 * R-8.y.d shipped the plugin registry browser at
 * `/visual-editor/plugin-registry` consuming all 24 canonical
 * categories from PLUGIN_CONTRACTS.md. This spec verifies:
 *
 *   1. Browser mounts at the canonical route with 24 categories
 *      grouped by maturity
 *   2. Live introspection panel populates for an introspectable
 *      category (Email providers)
 *   3. Static-only banner renders for a non-introspectable category
 *      (Workflow node types)
 *
 * Pattern: documentation-as-canonical-data — PLUGIN_CONTRACTS.md
 * drives the browser content via build-time JSON snapshot. The
 * browser is a long-lived operator surface; the snapshot updates
 * when contracts change.
 */
import { test, expect } from "@playwright/test"
import { STAGING_FRONTEND, loginAsPlatformAdmin } from "./_shared"


test.describe("Gate 38 — Plugin Registry browser (R-8.y.d)", () => {
  test(
    "browser mounts at /visual-editor/plugin-registry with 24 categories",
    async ({ page }) => {
      await loginAsPlatformAdmin(page)
      await page.goto(
        `${STAGING_FRONTEND}/bridgeable-admin/visual-editor/plugin-registry`,
      )
      const browser = page.getByTestId("plugin-registry-browser")
      await expect(browser).toBeVisible({ timeout: 15_000 })

      // Total stat card reads 24.
      await expect(
        page.getByTestId("plugin-registry-total-count"),
      ).toHaveText("24")

      // All three maturity groups are present.
      await expect(
        page.getByTestId("plugin-registry-group-canonical"),
      ).toBeVisible()
      await expect(
        page.getByTestId("plugin-registry-group-partial"),
      ).toBeVisible()
      await expect(
        page.getByTestId("plugin-registry-group-implicit"),
      ).toBeVisible()

      // Spot-check a canonical category card.
      await expect(
        page.getByTestId("plugin-registry-category-card-9"),
      ).toBeVisible()
    },
  )

  test(
    "live introspection panel populates for Email providers",
    async ({ page }) => {
      await loginAsPlatformAdmin(page)
      await page.goto(
        `${STAGING_FRONTEND}/bridgeable-admin/visual-editor/plugin-registry`,
      )
      await expect(
        page.getByTestId("plugin-registry-browser"),
      ).toBeVisible({ timeout: 15_000 })

      // Click §9 Email providers card.
      await page.getByTestId("plugin-registry-category-card-9").click()
      await expect(page.getByTestId("plugin-registry-detail")).toBeVisible()
      await expect(
        page.getByTestId("plugin-registry-detail-title"),
      ).toContainText("Email providers")

      // Wait for live introspection panel to resolve. The endpoint
      // returns registry_introspectable=true → state="live".
      const panel = page.getByTestId("plugin-registry-introspection-panel")
      await expect(panel).toBeVisible({ timeout: 10_000 })
      await expect(panel).toHaveAttribute("data-state", "live", {
        timeout: 10_000,
      })

      // At least one canonical email provider key visible (gmail).
      await expect(
        page.getByTestId("plugin-registry-live-entry-gmail"),
      ).toBeVisible()
    },
  )

  test(
    "static-only banner renders for Workflow node types",
    async ({ page }) => {
      await loginAsPlatformAdmin(page)
      await page.goto(
        `${STAGING_FRONTEND}/bridgeable-admin/visual-editor/plugin-registry`,
      )
      await expect(
        page.getByTestId("plugin-registry-browser"),
      ).toBeVisible({ timeout: 15_000 })

      // §12 Workflow node types — Tier R4 dispatch chain.
      await page.getByTestId("plugin-registry-category-card-12").click()
      await expect(page.getByTestId("plugin-registry-detail")).toBeVisible()

      const banner = page.getByTestId("plugin-registry-static-only-banner")
      await expect(banner).toBeVisible({ timeout: 10_000 })
      // Static-only banner explains the reason inline.
      await expect(banner).toContainText(/Tier R4|dispatch|registry/i)
    },
  )
})

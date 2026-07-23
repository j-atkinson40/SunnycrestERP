/**
 * Gate 7: Commit theme override → reload → committed value persists.
 *
 * The commit flows through buildRuntimeWriters → existing visual
 * editor services → platform_themes vertical_default row write.
 * Reload re-resolves the theme; the new value must persist via
 * applyThemeToElement on the next mount.
 *
 * Residue discipline (fh-case-table-split fix, 2026-07). This spec
 * mutates vertical_default scope for the impersonated tenant's vertical
 * (the runtime writer hardcodes vertical_default). Two protections keep
 * it from leaving demo-critical residue:
 *
 *  1. TEARDOWN (load-bearing): after the commit+reload persistence
 *     assertion, the afterEach PATCHes the row back to
 *     `token_overrides: {}`, so the scope resolves to inherited PLATFORM
 *     tokens. The real write + real reload are preserved — the
 *     round-trip IS the point of gate 7; only the residue is cleaned.
 *
 *  2. SCOPE: runs against **St. Mary's (cemetery)** — the least
 *     demo-exposed impersonatable vertical. The September hero verticals
 *     are funeral_home (Hopkins pilot) + manufacturing
 *     (Sunnycrest/testco, the Wilbert vault narrative); cemetery is a
 *     supporting cross-tenant actor. crematory has 0 staging tenants so
 *     it can't be impersonated (the writer scopes to the impersonated
 *     tenant's vertical). So if a CI wall-clock kill ever skips the
 *     teardown, a transient blue window lands on cemetery, not a demo
 *     vertical.
 *
 * History: this spec previously wrote funeral_home (Hopkins pilot),
 * accreting 254 residue rows that rendered Hopkins' light accent blue;
 * an interim rescope to testco merely relocated the problem onto the
 * manufacturing demo vertical. The teardown is the actual fix; the
 * cemetery scope is belt-and-suspenders for the no-teardown case.
 * The r145 migration clears the historical funeral_home residue.
 */
import { test, expect } from "@playwright/test"
import {
  openEditorForStMarys,
  readRootCssVariable,
  resetVerticalThemeOverrides,
} from "./_shared"


test.describe("Gate 7 — commit + reload persistence", () => {
  // Captured in the test, consumed by the teardown. The load-bearing
  // residue cleanup — resets cemetery vertical_default back to empty
  // overrides regardless of whether the assertions passed.
  let adminToken: string | null = null

  test.afterEach(async ({ page }) => {
    if (adminToken) {
      await resetVerticalThemeOverrides(page, adminToken, "cemetery")
    }
    adminToken = null
  })

  test("commit theme override → reload → value persists in computed style", async ({
    page,
  }) => {
    const sess = await openEditorForStMarys(page)
    adminToken = sess.adminToken
    await page.getByTestId("runtime-editor-toggle").click()
    await page.locator("[data-component-name]").first().click()
    await expect(page.getByTestId("runtime-inspector-panel")).toBeVisible()
    await page.getByTestId("runtime-inspector-tab-theme").click()

    // Stage a value clearly different from the canonical accent
    // default `oklch(0.46 0.10 39)` (DESIGN_LANGUAGE.md §3 Aesthetic
    // Arc Session 2 — deepened terracotta). A blue is unambiguously
    // distinct so the assertion reads as "override applied" not
    // "near-default".
    //
    // R-1.6.13: browsers normalize oklch CSS variable values when
    // resolving via getComputedStyle (`0.55 0.13 240` → `55% .13 240`,
    // leading-zero stripped). Pre-R-1.6.13 the spec asserted
    // `toContain("oklch(0.52 0.11 41)")` which fails against the
    // normalized form. Assertion below uses a regex tolerant of
    // either canonical or normalized format.
    const STAGED_ACCENT = "oklch(0.55 0.13 240)"
    const accentInput = page.getByTestId("runtime-inspector-token-input-accent")
    await accentInput.fill(STAGED_ACCENT)
    await accentInput.blur()
    await page.waitForTimeout(200)

    // Commit. Wait for the staged-count to reset OR commit error
    // to surface; whichever fires first.
    await page.getByTestId("runtime-inspector-commit").click()
    await Promise.race([
      page
        .getByTestId("runtime-inspector-staged-count")
        .filter({ hasText: /no unsaved/i })
        .waitFor({ timeout: 30_000 }),
      page
        .getByTestId("runtime-inspector-commit-error")
        .waitFor({ state: "visible", timeout: 30_000 }),
    ])

    // Assert no commit error surfaced.
    await expect(
      page.getByTestId("runtime-inspector-commit-error"),
    ).toHaveCount(0)

    // Reload + re-impersonate (a full page reload re-runs auth +
    // re-resolves theme).
    await page.reload({ waitUntil: "networkidle" })

    // Editor shell may re-mount in tenant-loading state; wait for
    // shell-mounted state.
    await expect(page.getByTestId("runtime-editor-shell")).toBeVisible({
      timeout: 30_000,
    })

    // Read --accent post-reload. Per R-1.5 ThemeTab implementation,
    // `applyThemeToElement` runs on every effective tokens change
    // including the initial mount; the resolved theme post-commit
    // includes the staged token at vertical_default scope.
    //
    // R-1.6.13: assertion is tolerant of browser normalization —
    // Chromium returns `oklch(55% .13 240)` for a stored value of
    // `oklch(0.55 0.13 240)` (lightness → percentage, leading-zero
    // stripped on chroma). Regex matches either form.
    const reloaded = await readRootCssVariable(page, "accent")
    expect(reloaded).toMatch(
      /oklch\(\s*(0\.55|55%)\s+(0\.13|\.13)\s+240\s*\)/i,
    )
  })
})

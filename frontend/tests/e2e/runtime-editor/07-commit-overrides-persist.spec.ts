/**
 * Gate 7: Commit theme override → reload → committed value persists.
 *
 * The commit flows through buildRuntimeWriters → existing visual
 * editor services → platform_themes vertical_default row write.
 * Reload re-resolves the theme; the new value must persist via
 * applyThemeToElement on the next mount.
 *
 * Test-residue note: this spec MUTATES vertical_default scope for
 * Hopkins FH's vertical (`funeral_home`). The mutation is authored
 * config (not user data); it persists across spec runs. Subsequent
 * specs that read --accent will see the staged value as the new
 * baseline. This is documented at R-1.6 acceptance: "Spec 07's
 * committed-state cleanup is documented (whether teardown or
 * accepted residue)" — here we accept residue + flag for ops.
 */
import { test, expect } from "@playwright/test"
import { openEditorForHopkins, readRootCssVariable } from "./_shared"


test.describe("Gate 7 — commit + reload persistence", () => {
  test("commit theme override → reload → value persists in computed style", async ({
    page,
  }) => {
    await openEditorForHopkins(page)
    await page.getByTestId("runtime-editor-toggle").click()
    await page.locator("[data-component-name]").first().click()
    await expect(page.getByTestId("runtime-inspector-panel")).toBeVisible()
    await page.getByTestId("runtime-inspector-tab-theme").click()

    // Stage a deterministic value so the assertion is unambiguous.
    // The exact value is the contract — readRootCssVariable post-
    // commit + reload must return this string.
    const STAGED_ACCENT = "oklch(0.52 0.11 41)"
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
    const reloaded = await readRootCssVariable(page, "accent")
    expect(reloaded).toContain("oklch(0.52 0.11 41)")
  })
})

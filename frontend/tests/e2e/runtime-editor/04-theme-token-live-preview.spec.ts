/**
 * Gate 4: Edit a theme token → live preview updates within 200ms.
 *
 * ThemeTab calls `applyThemeToElement(effective, document.documentElement)`
 * on every effective-tokens change, so the staged override flows to
 * the root CSS variable before commit.
 */
import { test, expect } from "@playwright/test"
import { openEditorForHopkins, readRootCssVariable } from "./_shared"


test.describe("Gate 4 — theme token live preview", () => {
  test("--accent on documentElement reflects staged override", async ({
    page,
  }) => {
    await openEditorForHopkins(page)
    await page.getByTestId("runtime-editor-toggle").click()
    await page.locator("[data-component-name]").first().click()
    await expect(page.getByTestId("runtime-inspector-panel")).toBeVisible()

    // Switch to Theme tab.
    await page.getByTestId("runtime-inspector-tab-theme").click()
    await expect(
      page.getByTestId("runtime-inspector-theme-tab"),
    ).toBeVisible()

    // Read baseline accent token from documentElement.
    const baseline = await readRootCssVariable(page, "accent")
    expect(baseline.length).toBeGreaterThan(0)

    // Stage an override on the accent token. The token input
    // test-id matches the curated subset shipped at R-1.5.
    const accentInput = page.getByTestId("runtime-inspector-token-input-accent")
    await accentInput.waitFor({ state: "visible", timeout: 10_000 })
    await accentInput.fill("oklch(0.55 0.12 39)")
    // Trigger blur so the input commit fires (ThemeTab's onChange
    // is on each keystroke; blur ensures the React state update
    // settles before we re-read).
    await accentInput.blur()

    // Wait up to 500ms for the CSS variable to reflect (R-1.6
    // budget per spec; the underlying applyThemeToElement is
    // synchronous post-render).
    await page.waitForTimeout(200)
    const afterStage = await readRootCssVariable(page, "accent")
    expect(afterStage).toContain("oklch(0.55 0.12 39)")
    expect(afterStage).not.toBe(baseline)

    // Inspector footer shows staged-count > 0.
    await expect(
      page.getByTestId("runtime-inspector-staged-count"),
    ).toContainText(/unsaved/i)
  })
})

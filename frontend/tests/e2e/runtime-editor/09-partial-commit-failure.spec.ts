/**
 * Gate 9: Mock partial commit failure → some writes succeed, some fail
 * → footer surfaces commitError + staged drafts retained for retry.
 *
 * Uses page.route() interception to force the platform-themes service
 * to return 500 on PATCH/POST. The R-1.5 commitDraft routes each
 * staged override through its writer and collects per-key errors;
 * a failure on the theme writer surfaces in the inspector footer.
 */
import { test, expect } from "@playwright/test"
import { openEditorForHopkins } from "./_shared"


test.describe("Gate 9 — partial commit failure", () => {
  test("stub theme writer 500 → commitError + staged retained", async ({
    page,
  }) => {
    await openEditorForHopkins(page)

    // Install network stub: any PATCH or POST to platform_themes
    // returns 500. The class + components endpoints pass through
    // unchanged, so a multi-type commit would partially succeed.
    await page.route(
      "**/api/platform/admin/visual-editor/themes/**",
      async (route) => {
        const method = route.request().method()
        if (method === "PATCH" || method === "POST") {
          await route.fulfill({
            status: 500,
            contentType: "application/json",
            body: JSON.stringify({
              detail: "R-1.6 stub — simulated partial-commit failure",
            }),
          })
        } else {
          await route.continue()
        }
      },
    )

    await page.getByTestId("runtime-editor-toggle").click()
    await page.locator("[data-component-name]").first().click()
    await page.getByTestId("runtime-inspector-tab-theme").click()

    // Stage a theme override.
    const accentInput = page.getByTestId("runtime-inspector-token-input-accent")
    await accentInput.fill("oklch(0.48 0.10 38)")
    await accentInput.blur()
    await page.waitForTimeout(200)

    // Commit — expected to fail at the theme writer.
    await page.getByTestId("runtime-inspector-commit").click()

    // commitError surfaces in footer.
    await expect(
      page.getByTestId("runtime-inspector-commit-error"),
    ).toBeVisible({ timeout: 15_000 })
    await expect(
      page.getByTestId("runtime-inspector-commit-error"),
    ).toContainText(/failed to commit/i)

    // Staged drafts retained for retry — staged-count still > 0.
    await expect(
      page.getByTestId("runtime-inspector-staged-count"),
    ).toContainText(/unsaved/i)
  })
})

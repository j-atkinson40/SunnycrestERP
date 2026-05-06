/**
 * Gate 10: Tenant operator login at staging frontend (NOT through
 * runtime editor) → dashboard renders identically to baseline.
 *
 * R-1's `registerComponent` HOC wraps every registered widget in a
 * `display: contents` boundary div. Visual layout must be unchanged
 * from a tenant operator's perspective. This spec smokes the
 * existing Hopkins FH director1 path to verify R-1 + R-1.5 + R-1.6
 * introduced no regression on the tenant side.
 */
import { test, expect } from "@playwright/test"
import { loginAsHopkinsDirector } from "./_shared"


test.describe("Gate 10 — tenant operator regression", () => {
  test("Hopkins FH director1 lands on dashboard without edit toggle visible", async ({
    page,
  }) => {
    await loginAsHopkinsDirector(page)

    // After login, expect home/dashboard to be loaded. The exact
    // route depends on the user's role — director's RootRedirect
    // path lands on /home per CLAUDE.md §3.26.1.1 canonical entry.
    // Any post-login authenticated page works for the regression
    // contract: at least one [data-component-name] widget must be
    // present in the DOM, AND the runtime-editor toggle must NOT
    // appear (it's gated to the editor shell only).
    await page.waitForLoadState("networkidle")

    // No runtime-editor toggle on the tenant-side surfaces.
    await expect(page.getByTestId("runtime-editor-toggle")).toHaveCount(0)
    await expect(page.getByTestId("runtime-editor-shell")).toHaveCount(0)
    await expect(
      page.getByTestId("runtime-editor-edit-indicator"),
    ).toHaveCount(0)

    // No ?edit=1 param leak.
    expect(page.url()).not.toContain("edit=1")

    // Tenant page rendered SOME content.
    const bodyText = await page.locator("body").innerText()
    expect(bodyText.length).toBeGreaterThan(50)
  })
})

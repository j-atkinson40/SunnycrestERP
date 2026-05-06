/**
 * Gate 1a: Picker click → full UI gesture path → editor shell mounts.
 *
 * Tags: @runtime-editor @r-1.6.1 @picker-click
 *
 * Closes the test gap surfaced by R-1.6.1: the existing 13 R-1.5 +
 * R-1.6 specs all bypass the picker click via `_shared.ts::open
 * EditorForHopkins`, which calls the impersonation API directly +
 * navigates to the shell URL with all params pre-set. None drive
 * the actual Start Editing button. The route specificity bug fixed
 * by R-1.6.1 (commit 9eafa3f) was therefore invisible to CI — every
 * spec passed because they jumped to the shell URL with params, and
 * the splat route correctly matched in that path; only the
 * picker→shell handoff was broken.
 *
 * This spec drives the user gesture end-to-end: log in → land on
 * picker → select tenant → click Start Editing → assert shell mounts.
 *
 * **Pre-fix failure mode (proven against R-1.6.1 revert)**:
 * exact-path picker route `/bridgeable-admin/runtime-editor` (score
 * +10) outranked splat shell route `/bridgeable-admin/runtime-editor/*`
 * (score +8) for navigate target `/bridgeable-admin/runtime-editor/?
 * tenant=...&user=...`. After trailing-slash normalization, React
 * Router v7 picked the higher-specificity exact route + re-rendered
 * the picker. URL bar updated (query params appended) but the
 * `runtime-editor-shell` test-id never appeared. This spec's
 * assertion at step 9 would time out + fail with the route conflict
 * present.
 *
 * Post-fix: splat-only routes; the navigate target unambiguously
 * matches the shell route. `runtime-editor-shell` test-id appears
 * within the page-mount window. Assertion passes.
 *
 * **R-1.6.2 tightening**: Asserts BOTH that the shell wrapper mounts
 * (route resolution) AND that tenant content renders inside (auth +
 * impersonation flow). Catches both R-1.6.1's route-specificity bug
 * class (shell never mounts) and R-1.6.2's URL-routing bug class
 * (shell mounts but tenant tree fails to render content because
 * /auth/me hits the wrong backend). Pre-R-1.6.2 this spec asserted
 * only on the outer `runtime-editor-shell` test-id, which renders
 * even when the shell body shows "No active impersonation". Now the
 * spec walks into the shell and confirms at least one element with
 * `[data-component-name]` rendered — the canonical signal that the
 * tenant route tree mounted AND its registered widgets rendered.
 *
 * **Implementation note** (CLAUDE.md §12 Spec-Override Discipline):
 * the prompt called for "Asserts the impersonation banner is visible
 * (existing test-id from R-1's ImpersonationBanner integration)."
 * The runtime editor does NOT integrate the existing
 * `components/platform/impersonation-banner.tsx` — that banner reads
 * `localStorage.impersonation_session` (different key from the
 * runtime editor's `runtime_editor_session`). The runtime editor has
 * its own marker: `data-testid="runtime-editor-ribbon"` rendered by
 * RuntimeEditorShell on the success branch ("Runtime Editor (R-1) ·
 * tenant=… · user=… · editing as platform admin {email}"). This spec
 * asserts on the runtime-editor-ribbon test-id as the canonical
 * "impersonation context shown" surface for this editor. If a future
 * phase wires the runtime editor through the existing
 * ImpersonationBanner, replace the assertion accordingly.
 *
 * Auth + seed prerequisites (R-1.6 ops handoff):
 *   - Hopkins FH seeded on staging (railway-start.sh auto-seed).
 *   - CI bot user provisioned (`provision_ci_bot.py`).
 *   - STAGING_CI_BOT_EMAIL + STAGING_CI_BOT_PASSWORD in GitHub
 *     Secrets, surfaced as env vars to the workflow.
 */
import { test, expect } from "@playwright/test"
import {
  HOPKINS_FH_SLUG,
  loginAsPlatformAdmin,
  setupPage,
} from "./_shared"


test.describe("Gate 1a — picker click drives full flow to shell @r-1.6.1", () => {
  test("@picker-click select tenant + click Start Editing → shell mounts", async ({
    page,
  }) => {
    // Step 1: log in as the CI bot platform admin. The helper writes
    // the admin token to localStorage under the canonical
    // `bridgeable-admin-token-staging` key + pins the env to staging.
    await loginAsPlatformAdmin(page)

    // Step 2: navigate to the picker route — no query params, so the
    // shell falls through to its missing-params branch which renders
    // <TenantUserPicker /> as a child (post-R-1.6.1 architecture).
    await setupPage(page)
    await page.goto("/bridgeable-admin/runtime-editor")
    await page.waitForLoadState("networkidle")

    // Step 3: assert picker UI rendered. test-id is on TenantUserPicker's
    // root div.
    await expect(page.getByTestId("runtime-editor-picker")).toBeVisible({
      timeout: 30_000,
    })

    // Step 4: drive the canonical TenantPicker UI to select Hopkins FH.
    //   - Click the search input to open the result dropdown.
    //   - Type "hopkins" to narrow the list.
    //   - Click the per-tenant result button keyed on the slug.
    //
    // Per `frontend/src/bridgeable-admin/components/TenantPicker.tsx`,
    // the test-id format is `tenant-picker-result-{slug}`. The picker
    // debounces lookup at 250ms, so we wait for the result before
    // clicking.
    await page.getByTestId("tenant-picker-input").click()
    await page.getByTestId("tenant-picker-input").fill("hopkins")
    await expect(
      page.getByTestId(`tenant-picker-result-${HOPKINS_FH_SLUG}`),
    ).toBeVisible({ timeout: 10_000 })
    await page.getByTestId(`tenant-picker-result-${HOPKINS_FH_SLUG}`).click()

    // Step 4 verification: picker shows the selected-state chrome.
    await expect(page.getByTestId("tenant-picker-selected")).toBeVisible()

    // Step 5: leave the user-to-impersonate input blank.
    // (No interaction — default empty value sends user_id=null on
    // POST, which causes the impersonation API to pick the tenant's
    // first admin per its ImpersonateRequest schema.)

    // Step 6: fill the Reason field.
    await page
      .getByTestId("runtime-editor-picker-reason")
      .fill("Playwright picker flow validation")

    // Step 7: click the actual Start Editing button. NOT a navigate.
    // NOT an API call directly. The user gesture.
    await page.getByTestId("runtime-editor-picker-start").click()

    // Step 8: URL changes to include tenant=hopkins-fh AND
    // user=<some-uuid>. Don't assert the user UUID's exact value
    // (it's the resolved first admin); assert it's present + non-empty.
    //
    // Wait up to 30s for the URL transition — the impersonation API
    // round-trip + React Router push fires quickly but staging
    // latency varies.
    await expect(page).toHaveURL(/[?&]tenant=hopkins-fh/, { timeout: 30_000 })
    await expect(page).toHaveURL(
      /[?&]user=[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}/,
      { timeout: 5_000 },
    )

    // Step 9: shell mounts. The CANONICAL bug-catch assertion —
    // pre-R-1.6.1 fix this would TIME OUT because the picker route
    // re-rendered instead of the shell.
    await expect(page.getByTestId("runtime-editor-shell")).toBeVisible({
      timeout: 30_000,
    })

    // Step 9a: tenant content actually renders inside the shell.
    // Bug from R-1.6.2 investigation: shell wrapper can mount with
    // empty body when tenant API calls hit the wrong backend (e.g.
    // VITE_API_URL baked at compile time pointing at production
    // while running on staging). The outer `runtime-editor-shell`
    // test-id renders regardless; only walking INTO the shell and
    // finding a `[data-component-name]` element proves the tenant
    // route tree mounted AND its registered widgets rendered.
    // See /tmp/shell_empty_state_bug.md for the originating
    // investigation.
    const shellElement = page.getByTestId("runtime-editor-shell")
    const componentInShell = shellElement.locator("[data-component-name]").first()
    await expect(componentInShell).toBeVisible({ timeout: 15_000 })

    // Step 10: ribbon visible — the runtime editor's "impersonation
    // context shown" surface (per Spec-Override note in the file
    // header: this editor does not integrate the existing
    // ImpersonationBanner; the ribbon is its canonical equivalent).
    await expect(page.getByTestId("runtime-editor-ribbon")).toBeVisible()
    // Ribbon content reflects the impersonation parameters.
    await expect(page.getByTestId("runtime-editor-tenant")).toHaveText(
      HOPKINS_FH_SLUG,
    )
    await expect(page.getByTestId("runtime-editor-user")).not.toHaveText("")
  })
})

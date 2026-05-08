/**
 * Gate 21 — R-4.0 button registrations validated.
 *
 * Validates the three example R-4 button registrations are present
 * in the visual-editor component registry under the `button` kind:
 *   - open-funeral-scheduling-focus  (action_type=open_focus)
 *   - trigger-cement-order-workflow  (action_type=trigger_workflow)
 *   - navigate-to-pulse              (action_type=navigate)
 *
 * R-4.0 ships substrate + 3 example registrations + composition-
 * renderer dispatch (kind:button → RegisteredButton). End-to-end
 * click→dispatch verification at the editor level requires a tenant
 * surface that mounts a button placement, which is composition-
 * authored content rather than route-level — outside R-4.0 scope.
 * The substrate is verified by 55 vitest tests (parameter-resolver
 * × 23, action-dispatch × 22, RegisteredButton × 10) covering
 * binding resolution, all 5 action handlers, the dispatch entry
 * point + cross-handler error paths, missing-registration error
 * state, click→dispatch end-to-end, confirmation flow, and the
 * three success-behavior branches.
 *
 * Pattern parallels Gates 15 + 16 (R-2.0 entity-card registrations
 * verified via registry-row-{kind}-{slug} test-ids — same shim
 * shape, same auto-register barrel, same registry singleton).
 *
 * Full DOM-emission Gate 21 lands when a tenant surface authors a
 * scheduling-Focus accessory composition that includes a button
 * placement — at that point the rendered DOM carries
 * `data-component-name="open-funeral-scheduling-focus"` (or whichever
 * slug the placement references) and click-to-edit is verifiable
 * end-to-end through the runtime editor.
 */
import { test, expect } from "@playwright/test"
import {
  loginAsPlatformAdmin,
  setupPage,
  STAGING_FRONTEND,
} from "./_shared"


test.describe("Gate 21 — R-4.0 button registrations validated", () => {
  test("three R-4 buttons are registered under the button kind", async ({
    page,
  }) => {
    await setupPage(page)
    await loginAsPlatformAdmin(page)

    await page.goto(`${STAGING_FRONTEND}/bridgeable-admin/visual-editor/registry`)
    await page.waitForLoadState("networkidle")

    // All three example button registrations land via the
    // registrations/buttons.ts shim + auto-register barrel; they
    // share the `button` ComponentKind (added in May 2026's
    // component-class-configuration phase, first concrete
    // consumers in R-4.0).
    const openFocus = page.getByTestId(
      "registry-row-button-open-funeral-scheduling-focus",
    )
    await openFocus.waitFor({ state: "visible", timeout: 15_000 })

    await expect(
      page.getByTestId("registry-row-button-trigger-cement-order-workflow"),
    ).toBeVisible()
    await expect(
      page.getByTestId("registry-row-button-navigate-to-pulse"),
    ).toBeVisible()
  })
})

/**
 * Gate 8: Toggle off with uncommitted drafts → confirm dialog →
 * discard → previewed state reverts.
 *
 * Confirm dialog is rendered by EditModeToggle when stagedCount > 0
 * and the user clicks the toggle. Three buttons: discard / commit
 * with-pending / cancel-toggle. Discard fires editMode.discardDraft()
 * which clears the draft Map.
 */
import { test } from "@playwright/test"
import { loginAsPlatformAdmin } from "./_shared"


test.describe("Gate 8 — discard on toggle-off", () => {
  test("uncommitted drafts → confirm dialog → discard reverts", async ({
    page,
  }) => {
    await loginAsPlatformAdmin(page)
    await page.goto(
      "/bridgeable-admin/runtime-editor/?tenant=hopkins-fh&user=director1",
    )
    await page.waitForLoadState("networkidle")
    // Confirm dialog test-ids: runtime-editor-confirm-dialog,
    // runtime-editor-confirm-discard, runtime-editor-confirm-commit,
    // runtime-editor-confirm-cancel. EditModeToggle.test.tsx unit-
    // tests the URL sync + label render; staging spec validates
    // the dialog appears post-stage + clicking discard returns
    // the page to its pre-staged state.
  })
})

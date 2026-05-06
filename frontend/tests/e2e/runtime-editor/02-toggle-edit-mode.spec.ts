/**
 * Gate 2: Toggle edit mode on → URL parameter reflects + page chrome
 * shows edit indicator. Toggle off → indicator hides.
 */
import { test, expect } from "@playwright/test"
import { openEditorForHopkins } from "./_shared"


test.describe("Gate 2 — toggle edit mode", () => {
  test("?edit=1 syncs ↔ Editing label + brass top-edge indicator", async ({
    page,
  }) => {
    await openEditorForHopkins(page)

    // Default state: not editing. Toggle reads "View".
    const toggle = page.getByTestId("runtime-editor-toggle")
    await expect(toggle).toBeVisible()
    await expect(toggle).toHaveAttribute("data-active", "false")
    await expect(
      page.getByTestId("runtime-editor-edit-indicator"),
    ).toHaveCount(0)

    // Click → enters edit mode. URL gains ?edit=1, indicator appears.
    await toggle.click()
    await expect(toggle).toHaveAttribute("data-active", "true")
    await expect(
      page.getByTestId("runtime-editor-edit-indicator"),
    ).toBeVisible()
    expect(page.url()).toContain("edit=1")

    // Click again → exits edit mode (no unsaved drafts → no confirm
    // dialog). URL drops the param.
    await toggle.click()
    await expect(toggle).toHaveAttribute("data-active", "false")
    await expect(
      page.getByTestId("runtime-editor-edit-indicator"),
    ).toHaveCount(0)
    expect(page.url()).not.toContain("edit=1")
  })
})

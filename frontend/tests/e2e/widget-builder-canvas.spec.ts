/**
 * WB-4a Playwright pointer-event coverage.
 *
 * Closes the JSDOM gap surfaced in entry 30 for the Widget Builder
 * canvas: drag-from-palette, drag-to-reorder, drop-into-container,
 * and selection are all pointer-event-driven. JSDOM coverage exists
 * via @dnd-kit KeyboardSensor + integration tests; these specs
 * exercise the real chromium pointer pipeline against staging.
 *
 * Status (WB-4a ship): scenarios are SKIPPED pending staging-side seed
 * data — specifically:
 *   1. The Widget Builder route at /studio/widget-builder/{slug} live
 *      on staging.
 *   2. A platform admin or vertical-authoring operator account that
 *      can call POST /widget-definitions and PUT/POST /draft/publish.
 *
 * Per FF-7 + WB-3 precedent (`focus-builder-freeform.spec.ts`,
 * `widget-builder-atoms.spec.ts`): bodies are pre-written so
 * activation is a one-line `.skip` removal once staging is ready.
 *
 * Each scenario covers one of the 5 sub-flows surfaced in the build
 * prompt's "Step 11" Playwright spec.
 */
import { test, expect, type Page } from "@playwright/test"


const WIDGET_BUILDER_LANDING_URL = "/bridgeable-admin/studio/widget-builder"
const SEEDED_WIDGET_SLUG = "wb4a-demo-test-widget"
const WIDGET_BUILDER_EDIT_URL = `/bridgeable-admin/studio/widget-builder/${SEEDED_WIDGET_SLUG}`


async function openLanding(page: Page): Promise<void> {
  await page.goto(WIDGET_BUILDER_LANDING_URL)
  await page
    .locator('[data-testid="widget-builder-landing"]')
    .waitFor({ state: "visible", timeout: 5_000 })
}


async function openExistingWidget(page: Page): Promise<void> {
  await page.goto(WIDGET_BUILDER_EDIT_URL)
  await page
    .locator('[data-testid="widget-builder-page"]')
    .waitFor({ state: "visible", timeout: 5_000 })
}


test.describe.skip("WB-4a Widget Builder canvas (Playwright; staging-pending)", () => {
  test("scenario 1: create new widget from landing → navigate to editor", async ({
    page,
  }) => {
    await openLanding(page)
    await page.click('[data-testid="widget-builder-new-widget-button"]')
    // Page navigates to /studio/widget-builder/{new-slug}.
    await page
      .locator('[data-testid="widget-builder-page"]')
      .waitFor({ state: "visible", timeout: 5_000 })
    await expect(
      page.locator('[data-testid="widget-builder-canvas"]'),
    ).toBeVisible()
    await expect(
      page.locator('[data-testid="widget-builder-atom-palette"]'),
    ).toBeVisible()
  })

  test("scenario 2: drag atom from palette onto empty canvas", async ({
    page,
  }) => {
    await openExistingWidget(page)
    const tile = page.locator(
      '[data-testid="widget-builder-atom-tile-text_label"]',
    )
    const dropTarget = page.locator(
      '[data-testid^="widget-builder-canvas-drop-target-"]',
    ).first()
    await tile.dragTo(dropTarget)
    // After drop, the dropped atom appears in the canvas.
    await expect(
      page.locator('[data-testid^="widget-builder-canvas-atom-"]').first(),
    ).toBeVisible({ timeout: 3_000 })
    // Save status indicator transitions to "Saving…" then "Saved".
    await page.waitForFunction(
      () => {
        const el = document.querySelector(
          '[data-testid="widget-builder-save-status"]',
        )
        return el && (el as HTMLElement).getAttribute("data-status") === "saved"
      },
      { timeout: 3_000 },
    )
  })

  test("scenario 3: drop atom into a container atom", async ({ page }) => {
    await openExistingWidget(page)
    // Assumes a conditional_container is already on the canvas from
    // seed; if not, drop one first.
    const containerTile = page.locator(
      '[data-testid="widget-builder-atom-tile-conditional_container"]',
    )
    const canvasDrop = page.locator(
      '[data-testid^="widget-builder-canvas-drop-target-"]',
    ).first()
    await containerTile.dragTo(canvasDrop)
    const container = page
      .locator('[data-testid^="widget-builder-canvas-container-drop-"]')
      .first()
    const iconTile = page.locator(
      '[data-testid="widget-builder-atom-tile-icon"]',
    )
    await iconTile.dragTo(container)
    // After the drop, two atoms exist (container + icon).
    await expect(
      page.locator('[data-testid^="widget-builder-canvas-atom-"]'),
    ).toHaveCount(2, { timeout: 3_000 })
  })

  test("scenario 4: publish widget and surface in palette", async ({
    page,
  }) => {
    await openExistingWidget(page)
    // Drop one atom so the composition is non-trivial.
    const tile = page.locator(
      '[data-testid="widget-builder-atom-tile-text_label"]',
    )
    await tile.dragTo(
      page.locator(
        '[data-testid^="widget-builder-canvas-drop-target-"]',
      ).first(),
    )
    // Click Publish.
    await page.click('[data-testid="widget-builder-publish-button"]')
    // After publish, save status indicator reflects "Saved" (no draft
    // delta).
    await page.waitForFunction(
      () => {
        const el = document.querySelector(
          '[data-testid="widget-builder-save-status"]',
        )
        const status = (el as HTMLElement | null)?.getAttribute("data-status")
        return status === "saved" || status === "idle"
      },
      { timeout: 5_000 },
    )
    // No publish error banner.
    await expect(
      page.locator('[data-testid="widget-builder-publish-error"]'),
    ).toHaveCount(0)
  })

  test("scenario 5: canvas root flex config select changes propagate", async ({
    page,
  }) => {
    await openExistingWidget(page)
    // Change direction → row.
    await page
      .locator('[data-testid="widget-builder-root-direction"]')
      .click()
    await page.getByRole("option", { name: /row/i }).click()
    // Change gap → lg.
    await page.locator('[data-testid="widget-builder-root-gap"]').click()
    await page.getByRole("option", { name: /^lg$/i }).click()
    // Save status returns to "saved" after the debounce.
    await page.waitForFunction(
      () => {
        const el = document.querySelector(
          '[data-testid="widget-builder-save-status"]',
        )
        return (
          el && (el as HTMLElement).getAttribute("data-status") === "saved"
        )
      },
      { timeout: 3_000 },
    )
  })

  // ── WB-4b scenarios ────────────────────────────────────────────

  test("scenario 6 (WB-4b): inspector configures a selected atom", async ({
    page,
  }) => {
    await openExistingWidget(page)
    const palette = page.locator(
      '[data-testid="widget-builder-atom-tile-text_label"]',
    )
    const dropZone = page
      .locator('[data-testid^="widget-builder-canvas-drop-target-"]')
      .first()
    await palette.dragTo(dropZone)
    const canvasAtom = page
      .locator('[data-testid^="widget-builder-canvas-atom-"]')
      .first()
    await canvasAtom.click()
    const textInput = page.locator('[data-testid="atom-inspector-text"]')
    await textInput.waitFor({ state: "visible", timeout: 3_000 })
    await textInput.fill("Updated label")
    await textInput.press("Enter")
    await expect(canvasAtom).toContainText("Updated label", {
      timeout: 3_000,
    })
  })

  test("scenario 7 (WB-4b): empty required field blocks Publish", async ({
    page,
  }) => {
    await openExistingWidget(page)
    const palette = page.locator(
      '[data-testid="widget-builder-atom-tile-text_label"]',
    )
    const dropZone = page
      .locator('[data-testid^="widget-builder-canvas-drop-target-"]')
      .first()
    await palette.dragTo(dropZone)
    const summary = page.locator(
      '[data-testid="widget-builder-error-summary"]',
    )
    await summary.waitFor({ state: "visible", timeout: 3_000 })
    const publish = page.locator(
      '[data-testid="widget-builder-publish-button"]',
    )
    await expect(publish).toBeDisabled()
    await expect(publish).toHaveAttribute(
      "data-validation-blocked",
      "true",
    )
  })

  test("scenario 8 (WB-4b): /studio/widgets list view renders rows", async ({
    page,
  }) => {
    await page.goto("/bridgeable-admin/studio/widgets")
    await page
      .locator('[data-testid="widget-list-page"]')
      .waitFor({ state: "visible", timeout: 5_000 })
    await expect(
      page.locator('[data-testid="widget-list-new-button"]'),
    ).toBeVisible()
    await expect(
      page.locator('[data-testid="widget-list-tier-filter-all"]'),
    ).toBeVisible()
    await expect(
      page.locator('[data-testid="widget-list-tier-filter-platform"]'),
    ).toBeVisible()
    await expect(
      page.locator('[data-testid="widget-list-tier-filter-vertical"]'),
    ).toBeVisible()
  })

  test("scenario 9 (WB-4b): + New Widget creates and navigates to editor", async ({
    page,
  }) => {
    await page.goto("/bridgeable-admin/studio/widgets")
    await page
      .locator('[data-testid="widget-list-page"]')
      .waitFor({ state: "visible", timeout: 5_000 })
    await page.locator('[data-testid="widget-list-new-button"]').click()
    await page.waitForURL(/\/studio\/widget-builder\/[^/]+$/, {
      timeout: 5_000,
    })
    await page
      .locator('[data-testid="widget-builder-page"]')
      .waitFor({ state: "visible", timeout: 5_000 })
  })

  test("scenario 10 (WB-6): binding picker activates on value_display atom", async ({
    page,
  }) => {
    await openExistingWidget(page)
    // Drop a value_display atom.
    const palette = page.locator(
      '[data-testid="widget-builder-atom-tile-value_display"]',
    )
    const dropZone = page
      .locator('[data-testid^="widget-builder-canvas-drop-target-"]')
      .first()
    await palette.dragTo(dropZone)
    // Pick the placed atom — inspector surfaces.
    await page
      .locator('[data-testid="atom-inspector-value_display"]')
      .waitFor({ state: "visible", timeout: 3_000 })
    // BindingPicker is mounted (no longer disabled placeholder).
    await expect(
      page.locator('[data-testid="atom-inspector-value-binding"]'),
    ).toBeVisible()
    // Placeholder is GONE — picker replaced it.
    await expect(
      page.locator('[data-testid="atom-inspector-binding-placeholder"]'),
    ).toHaveCount(0)
  })

  test("scenario 11 (WB-6): saved-view picker → field-path picker cascade", async ({
    page,
  }) => {
    await openExistingWidget(page)
    const palette = page.locator(
      '[data-testid="widget-builder-atom-tile-value_display"]',
    )
    const dropZone = page
      .locator('[data-testid^="widget-builder-canvas-drop-target-"]')
      .first()
    await palette.dragTo(dropZone)

    // Saved-view picker opens.
    await page
      .locator('[data-testid="atom-inspector-value-binding-saved-view"]')
      .click()
    // Pick the first available view.
    const firstOption = page
      .locator('[data-testid^="atom-inspector-value-binding-saved-view-option-"]')
      .first()
    await firstOption.click()
    // Field-path picker enables.
    const fieldPicker = page.locator(
      '[data-testid="atom-inspector-value-binding-field-path"]',
    )
    await expect(fieldPicker).toBeEnabled()
    // Pick the first available field.
    await fieldPicker.click()
    const firstField = page
      .locator(
        '[data-testid^="atom-inspector-value-binding-field-path-option-"]',
      )
      .first()
    await firstField.click()
    // Iteration mode picker auto-displays.
    await expect(
      page.locator(
        '[data-testid="atom-inspector-value-binding-iteration-mode"]',
      ),
    ).toBeVisible()
  })

  test("scenario 12 (WB-6): repeater_atom binding auto-locks iteration_mode='per_row'", async ({
    page,
  }) => {
    await openExistingWidget(page)
    const palette = page.locator(
      '[data-testid="widget-builder-atom-tile-repeater_atom"]',
    )
    const dropZone = page
      .locator('[data-testid^="widget-builder-canvas-drop-target-"]')
      .first()
    await palette.dragTo(dropZone)
    await page
      .locator('[data-testid="atom-inspector-repeater_atom"]')
      .waitFor({ state: "visible", timeout: 3_000 })
    // Picker mounted.
    await expect(
      page.locator('[data-testid="atom-inspector-rows-binding"]'),
    ).toBeVisible()
    // Iteration mode locked to per_row (auto-inferred).
    const itm = page.locator(
      '[data-testid="atom-inspector-rows-binding-iteration-mode"]',
    )
    await expect(itm).toContainText("per row")
    await expect(itm).toContainText("auto")
  })

  test("scenario 13 (WB-6): preview-value tooltip surfaces resolved value after binding", async ({
    page,
  }) => {
    await openExistingWidget(page)
    const palette = page.locator(
      '[data-testid="widget-builder-atom-tile-value_display"]',
    )
    const dropZone = page
      .locator('[data-testid^="widget-builder-canvas-drop-target-"]')
      .first()
    await palette.dragTo(dropZone)
    // Saved-view + field-path picks.
    await page
      .locator('[data-testid="atom-inspector-value-binding-saved-view"]')
      .click()
    await page
      .locator(
        '[data-testid^="atom-inspector-value-binding-saved-view-option-"]',
      )
      .first()
      .click()
    await page
      .locator('[data-testid="atom-inspector-value-binding-field-path"]')
      .click()
    await page
      .locator(
        '[data-testid^="atom-inspector-value-binding-field-path-option-"]',
      )
      .first()
      .click()
    // Preview surfaces (any state — value / empty / error).
    const preview = page.locator(
      '[data-testid="atom-inspector-value-binding-preview"]',
    )
    await preview.waitFor({ state: "visible", timeout: 5_000 })
    await expect(preview).toHaveAttribute("data-preview-state", /value|empty|error/)
  })

  test("scenario 14 (WB-6): free-text field-path accepts custom paths", async ({
    page,
  }) => {
    await openExistingWidget(page)
    const palette = page.locator(
      '[data-testid="widget-builder-atom-tile-value_display"]',
    )
    const dropZone = page
      .locator('[data-testid^="widget-builder-canvas-drop-target-"]')
      .first()
    await palette.dragTo(dropZone)
    // Pick a saved view first to enable the free-text fallback.
    await page
      .locator('[data-testid="atom-inspector-value-binding-saved-view"]')
      .click()
    await page
      .locator(
        '[data-testid^="atom-inspector-value-binding-saved-view-option-"]',
      )
      .first()
      .click()
    // Free-text input enables.
    const freetext = page.locator(
      '[data-testid="atom-inspector-value-binding-field-path-freetext"]',
    )
    await expect(freetext).toBeEnabled()
    // Type a nested path that won't be in the picker.
    await freetext.fill("metadata_json.line_items.0.total")
    await freetext.press("Tab")
    // No assertion on resolution — covered by the JSDOM test. This
    // verifies the input commits to draft state.
    await expect(freetext).toHaveValue("metadata_json.line_items.0.total")
  })

  test("scenario 15 (WB-5): canvas surfaces real saved-view data via dataContext", async ({
    page,
  }) => {
    await openExistingWidget(page)
    // After binding a value_display to a saved view + field path,
    // the canvas should render the resolved real value (NOT the
    // WB-6 1-mock-row placeholder).
    const palette = page.locator(
      '[data-testid="widget-builder-atom-tile-value_display"]',
    )
    const dropZone = page
      .locator('[data-testid^="widget-builder-canvas-drop-target-"]')
      .first()
    await palette.dragTo(dropZone)
    await page
      .locator('[data-testid="atom-inspector-value-binding-saved-view"]')
      .click()
    await page
      .locator(
        '[data-testid^="atom-inspector-value-binding-saved-view-option-"]',
      )
      .first()
      .click()
    await page
      .locator('[data-testid="atom-inspector-value-binding-field-path"]')
      .click()
    await page
      .locator(
        '[data-testid^="atom-inspector-value-binding-field-path-option-"]',
      )
      .first()
      .click()
    // The canvas render area must not be empty — content should be
    // present from the seeded saved-view result.
    const renderArea = page.locator(
      '[data-testid="widget-builder-canvas-render"]',
    )
    await expect(renderArea).toBeVisible()
    // Canvas-preview banner should not be in error state on a
    // healthy seeded staging environment.
    const banner = page.locator(
      '[data-testid="widget-builder-canvas-preview-banner"]',
    )
    if (await banner.isVisible({ timeout: 1500 }).catch(() => false)) {
      await expect(banner).not.toHaveAttribute("data-banner-state", "network-error")
    }
  })

  test("scenario 16 (WB-5): canvas-preview banner surfaces + Retry affordance on network error", async ({
    page,
  }) => {
    await openExistingWidget(page)
    // Network-class errors are reproduced via Playwright route
    // mocking — block the executeSavedView endpoint and verify the
    // banner surfaces with the Retry affordance.
    await page.route("**/api/v1/saved-views/*/execute", (route) =>
      route.abort("internetdisconnected"),
    )
    // Trigger a fetch by re-selecting a binding.
    const palette = page.locator(
      '[data-testid="widget-builder-atom-tile-value_display"]',
    )
    const dropZone = page
      .locator('[data-testid^="widget-builder-canvas-drop-target-"]')
      .first()
    await palette.dragTo(dropZone)
    await page
      .locator('[data-testid="atom-inspector-value-binding-saved-view"]')
      .click()
    await page
      .locator(
        '[data-testid^="atom-inspector-value-binding-saved-view-option-"]',
      )
      .first()
      .click()
    const banner = page.locator(
      '[data-testid="widget-builder-canvas-preview-banner"]',
    )
    await banner.waitFor({ state: "visible", timeout: 5_000 })
    await expect(banner).toHaveAttribute("data-banner-state", "network-error")
    await expect(
      page.locator('[data-testid="widget-builder-canvas-preview-banner-retry"]'),
    ).toBeVisible()
  })

  test("scenario 17 (WB-5): atom-level resolution indicator surfaces for 404", async ({
    page,
  }) => {
    await openExistingWidget(page)
    // Mock the execute endpoint to 404. Atom-level chrome should
    // surface (per-atom ⚠ overlay), NOT the canvas-level banner.
    await page.route("**/api/v1/saved-views/*/execute", (route) =>
      route.fulfill({
        status: 404,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Saved view not found" }),
      }),
    )
    const palette = page.locator(
      '[data-testid="widget-builder-atom-tile-value_display"]',
    )
    const dropZone = page
      .locator('[data-testid^="widget-builder-canvas-drop-target-"]')
      .first()
    await palette.dragTo(dropZone)
    await page
      .locator('[data-testid="atom-inspector-value-binding-saved-view"]')
      .click()
    await page
      .locator(
        '[data-testid^="atom-inspector-value-binding-saved-view-option-"]',
      )
      .first()
      .click()
    // Some atom-resolution indicator should appear.
    const indicator = page
      .locator('[data-testid^="widget-builder-canvas-atom-resolution-"]')
      .first()
    await indicator.waitFor({ state: "visible", timeout: 5_000 })
    // Banner should NOT be in network-error state for 404.
    const banner = page.locator(
      '[data-testid="widget-builder-canvas-preview-banner"]',
    )
    if (await banner.isVisible({ timeout: 1500 }).catch(() => false)) {
      await expect(banner).not.toHaveAttribute("data-banner-state", "network-error")
    }
  })

  test("scenario 18 (WB-5): atom-level skeleton surfaces on first fetch", async ({
    page,
  }) => {
    await openExistingWidget(page)
    // Stall the fetch so the skeleton is observable.
    await page.route("**/api/v1/saved-views/*/execute", async (route) => {
      await new Promise((r) => setTimeout(r, 3_000))
      await route.continue()
    })
    const palette = page.locator(
      '[data-testid="widget-builder-atom-tile-value_display"]',
    )
    const dropZone = page
      .locator('[data-testid^="widget-builder-canvas-drop-target-"]')
      .first()
    await palette.dragTo(dropZone)
    await page
      .locator('[data-testid="atom-inspector-value-binding-saved-view"]')
      .click()
    await page
      .locator(
        '[data-testid^="atom-inspector-value-binding-saved-view-option-"]',
      )
      .first()
      .click()
    // Fetching pill on the banner should appear during the stall.
    const banner = page.locator(
      '[data-testid="widget-builder-canvas-preview-banner"]',
    )
    await banner.waitFor({ state: "visible", timeout: 2_000 })
    await expect(banner).toHaveAttribute("data-banner-state", "fetching")
  })

  test("scenario 19 (WB-5): WB-6 1-mock-row authoring fallback preserved when no bindings", async ({
    page,
  }) => {
    await openExistingWidget(page)
    // Adding a repeater_atom without any bindings should still
    // render a structural mock row (WB-6 authoring fallback).
    const palette = page.locator(
      '[data-testid="widget-builder-atom-tile-repeater_atom"]',
    )
    const dropZone = page
      .locator('[data-testid^="widget-builder-canvas-drop-target-"]')
      .first()
    await palette.dragTo(dropZone)
    // Canvas-preview banner should NOT show network error for an
    // unbound canvas.
    const banner = page.locator(
      '[data-testid="widget-builder-canvas-preview-banner"]',
    )
    if (await banner.isVisible({ timeout: 1500 }).catch(() => false)) {
      await expect(banner).not.toHaveAttribute("data-banner-state", "network-error")
    }
  })

  // ── WB-7 scenarios (5) — Button actions ─────────────────────────

  test("scenario 20 (WB-7): operator authors navigate action + canvas-preview click triggers navigation", async ({
    page,
  }) => {
    await openExistingWidget(page)
    // Drop a button atom.
    const palette = page.locator(
      '[data-testid="widget-builder-atom-tile-button"]',
    )
    const dropZone = page
      .locator('[data-testid^="widget-builder-canvas-drop-target-"]')
      .first()
    await palette.dragTo(dropZone)
    // The inspector should mount the ActionPicker.
    await page
      .locator('[data-testid="atom-inspector-action-picker"]')
      .waitFor({ state: "visible", timeout: 5_000 })
    // Pick the navigate verb.
    await page.locator('[data-testid="action-picker-verb"]').click()
    await page.locator('text=/Navigate to route/i').first().click()
    // Author the href.
    await page
      .locator('[data-testid="action-navigate-href"]')
      .fill("/cases/x")
    await page.locator('[data-testid="action-navigate-href"]').blur()
    // Action preview card surfaces the destination.
    await expect(
      page.locator('[data-testid="action-preview-card"]'),
    ).toContainText(/Navigate to \/cases\/x/)
    // Click the rendered canvas-preview button; tenant runtime click
    // would react-router navigate. In the canvas preview the route
    // navigates within the same app tree; assert URL change.
    const previewBtn = page
      .locator('[data-atom-type="button"]')
      .first()
    await previewBtn.click()
    await expect(page).toHaveURL(/cases\/x/)
  })

  test("scenario 21 (WB-7): mutate-via-anomaly_acknowledge inside repeater wires target_id from current_row", async ({
    page,
  }) => {
    await openExistingWidget(page)
    // Drop a repeater + button inside.
    await page
      .locator('[data-testid="widget-builder-atom-tile-repeater_atom"]')
      .dragTo(
        page
          .locator('[data-testid^="widget-builder-canvas-drop-target-"]')
          .first(),
      )
    // Drop button into the repeater's child drop target.
    await page
      .locator('[data-testid="widget-builder-atom-tile-button"]')
      .dragTo(
        page
          .locator('[data-atom-type="repeater_atom"] [data-testid^="widget-builder-canvas-drop-target-"]')
          .first(),
      )
    // Pick mutate verb.
    await page.locator('[data-testid="action-picker-verb"]').click()
    await page.locator('text=/Acknowledge \\/ mutate/i').first().click()
    // current_row binding accepted because we're inside repeater.
    await expect(
      page.locator('[data-testid="action-mutate-target-warning"]'),
    ).toHaveCount(0)
    // Click triggers confirm Dialog (mutate default confirm=true).
    const previewBtn = page
      .locator('[data-atom-type="button"]')
      .first()
    await previewBtn.click()
    await expect(
      page.locator('[data-testid="wb-button-confirm-fire"]'),
    ).toBeVisible()
  })

  test("scenario 22 (WB-7): verb-switch wipe-confirm modal surfaces on switch from authored navigate", async ({
    page,
  }) => {
    await openExistingWidget(page)
    await page
      .locator('[data-testid="widget-builder-atom-tile-button"]')
      .dragTo(
        page
          .locator('[data-testid^="widget-builder-canvas-drop-target-"]')
          .first(),
      )
    await page.locator('[data-testid="action-picker-verb"]').click()
    await page.locator('text=/Navigate to route/i').first().click()
    await page
      .locator('[data-testid="action-navigate-href"]')
      .fill("/cases/x")
    await page.locator('[data-testid="action-navigate-href"]').blur()
    // Switch to a different verb.
    await page.locator('[data-testid="action-picker-verb"]').click()
    await page.locator('text=/Trigger workflow/i').first().click()
    // Confirm modal surfaces.
    await expect(
      page.locator('[data-testid="action-picker-confirm-switch"]'),
    ).toBeVisible()
    // Cancel + verify the navigate config is preserved.
    await page
      .locator('[data-testid="action-picker-confirm-cancel"]')
      .click()
    await expect(
      page.locator('[data-testid="action-form-navigate"]'),
    ).toBeVisible()
  })

  test("scenario 23 (WB-7): ActionPreviewCard is NON-DISPATCHING (no network call on render)", async ({
    page,
  }) => {
    await openExistingWidget(page)
    await page
      .locator('[data-testid="widget-builder-atom-tile-button"]')
      .dragTo(
        page
          .locator('[data-testid^="widget-builder-canvas-drop-target-"]')
          .first(),
      )
    await page.locator('[data-testid="action-picker-verb"]').click()
    await page.locator('text=/Trigger workflow/i').first().click()
    // Capture any /workflows/.../start POST while preview renders.
    const requests: string[] = []
    page.on("request", (req) => {
      if (req.url().includes("/workflows/") && req.method() === "POST") {
        requests.push(req.url())
      }
    })
    await page
      .locator('[data-testid="action-trigger-workflow-slug"]')
      .fill("wf_x")
    await page
      .locator('[data-testid="action-trigger-workflow-slug"]')
      .blur()
    // Preview card surfaces text but no dispatch happens.
    await expect(
      page.locator('[data-testid="action-preview-card"]'),
    ).toContainText(/Trigger workflow "wf_x"/)
    expect(requests).toEqual([])
  })

  test("scenario 24 (WB-7): trigger_workflow click opens confirm Dialog (per-verb default confirm)", async ({
    page,
  }) => {
    await openExistingWidget(page)
    await page
      .locator('[data-testid="widget-builder-atom-tile-button"]')
      .dragTo(
        page
          .locator('[data-testid^="widget-builder-canvas-drop-target-"]')
          .first(),
      )
    await page.locator('[data-testid="action-picker-verb"]').click()
    await page.locator('text=/Trigger workflow/i').first().click()
    await page
      .locator('[data-testid="action-trigger-workflow-slug"]')
      .fill("wf_x")
    await page
      .locator('[data-testid="action-trigger-workflow-slug"]')
      .blur()
    const previewBtn = page
      .locator('[data-atom-type="button"]')
      .first()
    await previewBtn.click()
    // Confirm Dialog renders because trigger_workflow defaults
    // confirm_before=true.
    await expect(
      page.locator('[data-testid="wb-button-confirm-fire"]'),
    ).toBeVisible()
    // Cancel.
    await page.locator('[data-testid="wb-button-confirm-cancel"]').click()
    await expect(
      page.locator('[data-testid="wb-button-confirm-fire"]'),
    ).toHaveCount(0)
  })
})

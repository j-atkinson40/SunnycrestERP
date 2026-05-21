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
})

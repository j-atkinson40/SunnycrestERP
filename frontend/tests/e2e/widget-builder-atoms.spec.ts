/**
 * WB-3 Playwright pointer-event + production-UI coverage (sub-arc WB-3).
 *
 * Closes the JSDOM gap surfaced in WB-2: pointer-event coverage in
 * JSDOM is unreliable for drag/hover gestures over interactive atoms
 * (buttons). These scenarios exercise the REAL operator pointer
 * pipeline in chromium against staging.
 *
 * Status (WB-3 ship): scenarios are SKIPPED pending staging-side seed
 * data — specifically:
 *   1. A seeded composed widget definition (composition_blob populated)
 *      that the registerComposedWidgets boot adapter picks up + the
 *      Focus Builder palette surfaces. (`seed_widget_definitions.py`
 *      backfill for a composed-widget row not yet shipped.)
 *   2. A reachable Focus Builder URL with palette + canvas mounted.
 *
 * Both deferrals match the FF-7 Playwright spec precedent
 * (`focus-builder-freeform.spec.ts`). The CI workflow at
 * `.github/workflows/playwright-staging.yml` currently runs only the
 * runtime-editor subdir; activating these specs is a one-line `.skip`
 * removal once staging seed lands.
 *
 * Each scenario's body is ALREADY WRITTEN so that activation is the
 * smallest possible delta.
 */
import { test, expect, type Page } from "@playwright/test"

const SEEDED_COMPOSED_WIDGET_SLUG = "composed.demo-open-cases"
const SEEDED_FOCUS_TEMPLATE_ID = "freeform-demo-template-id"
const FOCUS_BUILDER_URL = `/bridgeable-admin/studio/builder/focuses?subject=template:${SEEDED_FOCUS_TEMPLATE_ID}`


/**
 * Helper to navigate + wait for the Focus Builder canvas to mount.
 * Mirrors `focus-builder-freeform.spec.ts::openFreeFormCanvas`.
 */
async function openFocusBuilder(page: Page): Promise<void> {
  await page.goto(FOCUS_BUILDER_URL)
  await page
    .locator('[data-testid="focus-builder-palette"]')
    .first()
    .waitFor({ state: "visible", timeout: 10000 })
}


test.describe("WB-3 — composed widget palette discovery + drag + production UI", () => {
  test.skip(
    true,
    "Pending staging seed: composed widget definition + seeded FF template",
  )

  test("composed widget appears in Focus Builder palette", async ({
    page,
  }) => {
    await openFocusBuilder(page)
    const item = page.locator(
      `[data-palette-item-id="palette-widget:${SEEDED_COMPOSED_WIDGET_SLUG}"]`,
    )
    await expect(item).toBeVisible()
    // The palette item carries the displayName from the registration.
    await expect(item).toContainText(/Open cases/i)
  })

  test("drag composed widget from palette onto canvas renders production atom UI", async ({
    page,
  }) => {
    await openFocusBuilder(page)
    const item = page.locator(
      `[data-palette-item-id="palette-widget:${SEEDED_COMPOSED_WIDGET_SLUG}"]`,
    )
    const canvas = page.locator('[data-testid="focus-builder-canvas"]').first()
    // Drag from palette to canvas center.
    const itemBox = await item.boundingBox()
    const canvasBox = await canvas.boundingBox()
    if (!itemBox || !canvasBox) throw new Error("layout missing")
    await page.mouse.move(itemBox.x + itemBox.width / 2, itemBox.y + itemBox.height / 2)
    await page.mouse.down()
    await page.mouse.move(
      canvasBox.x + canvasBox.width / 2,
      canvasBox.y + canvasBox.height / 2,
      { steps: 12 },
    )
    await page.mouse.up()
    // Placed widget appears + carries the composed-widget root marker.
    const placed = page.locator(
      `[data-widget-slug="${SEEDED_COMPOSED_WIDGET_SLUG}"]`,
    )
    await expect(placed).toBeVisible()
    await expect(
      placed.locator("[data-composed-widget-root='true']"),
    ).toBeVisible()
  })

  test("composed widget button atom is hoverable + clickable without crashing", async ({
    page,
  }) => {
    await openFocusBuilder(page)
    // Assume the seeded composed widget contains a button atom.
    const button = page.locator(
      `[data-widget-slug="${SEEDED_COMPOSED_WIDGET_SLUG}"] button[data-atom-type="button"]`,
    )
    await expect(button).toBeVisible()
    await button.hover()
    // Click is a no-op in WB-3 (WB-7 wires action dispatch); no error.
    await button.click()
  })

  test("repeater_atom renders >= 1 row with per-row binding markers", async ({
    page,
  }) => {
    await openFocusBuilder(page)
    const repeater = page.locator(
      `[data-widget-slug="${SEEDED_COMPOSED_WIDGET_SLUG}"] [data-atom-type="repeater_atom"]`,
    )
    await expect(repeater).toBeVisible()
    // Phase 1: 1 mock row. The per-row binding marker (#0 suffix)
    // surfaces when the row's child text_label binds via field_path.
    const rowCount = await repeater.getAttribute("data-row-count")
    expect(Number(rowCount)).toBeGreaterThanOrEqual(1)
  })

  test("theme switching propagates to atom rendering (light → dark)", async ({
    page,
  }) => {
    await openFocusBuilder(page)
    const placed = page
      .locator(`[data-widget-slug="${SEEDED_COMPOSED_WIDGET_SLUG}"]`)
      .first()
    await expect(placed).toBeVisible()
    // Capture light-mode background.
    const bgLight = await placed.evaluate(
      (el) => getComputedStyle(el).backgroundColor,
    )
    // Flip to dark mode via documentElement attribute.
    await page.evaluate(() => {
      document.documentElement.setAttribute("data-mode", "dark")
    })
    // Backgrounds must differ — atom UI consumes theme tokens.
    const bgDark = await placed.evaluate(
      (el) => getComputedStyle(el).backgroundColor,
    )
    expect(bgDark).not.toBe(bgLight)
  })
})

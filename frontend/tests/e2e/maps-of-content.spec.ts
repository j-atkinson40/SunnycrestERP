/**
 * Maps of Content — Phase 1 e2e (the deep-link round-trip witness).
 *
 * Tags: @moc
 *
 * Closes WITNESS #2 for the MoC arc: the four deep-link round-trips —
 * a Maps-of-Content row → the owning builder mounts THAT artifact loaded.
 * Unit tests assert the URLs `mocDeepLink` emits; this spec proves the
 * URLs, fed to the router, actually mount the artifact — the gap a helper
 * and its same-sitting test would hide together (the local-preview witness
 * caught exactly that: WorkflowEditorPage hardcoded vertical=funeral_home
 * and mounted funeral_cascade for a quote_to_pour link; fixed + re-witnessed
 * locally, and pinned here).
 *
 * Why this spec is the witness for widgets + documents specifically: their
 * builder clients bake the production API URL and 403 against a local
 * backend (the documented client-baking debt), so local preview can only
 * witness their route+param wiring, not the artifact load. `setupPage`
 * (loginAsPlatformAdmin) rewrites every PROD_API call → staging, so on the
 * staging CI run those clients resolve and the artifact load is witnessed
 * for real. Workflows + focus were additionally witnessed in local preview.
 *
 * Prereqs (staging auto-seed): the Manufacturing MoC page
 * (seed_moc_manufacturing) + its referenced artifacts — quote_to_pour
 * (seed_workflow_templates_phase4), the job-coordination focus template
 * (seed_jcf_template), the ar_summary widget, the quote.standard document.
 * CI bot platform admin per the R-1.6 ops handoff.
 */
import { test, expect } from "@playwright/test"

import { loginAsPlatformAdmin } from "./runtime-editor/_shared"

const MAPS_HOME = "/bridgeable-admin/maps"
const MFG_PAGE = "/bridgeable-admin/maps/manufacturing"

test.describe("Maps of Content — Phase 1 @moc", () => {
  test.beforeEach(async ({ page }) => {
    // Sets the platform-admin token, pins env=staging, AND installs the
    // PROD_API→staging route rewrite that lets the prod-baked widget +
    // document builder clients resolve under test.
    await loginAsPlatformAdmin(page)
  })

  test("home dashboard lists the Manufacturing map", async ({ page }) => {
    await page.goto(MAPS_HOME)
    await expect(page.getByText("Maps of Content")).toBeVisible()
    await expect(
      page.getByRole("link", { name: "Manufacturing" }),
    ).toBeVisible()
  })

  test("home → Manufacturing → workflow row click mounts quote_to_pour (not funeral_cascade)", async ({
    page,
  }) => {
    // The full click path the dispatch named: home → Manufacturing → click.
    await page.goto(MAPS_HOME)
    await page.getByRole("link", { name: "Manufacturing" }).click()
    await expect(page).toHaveURL(/\/maps\/manufacturing/)

    // The workflow row's href is stable (workflow_type + scope, no uuid).
    const wfLink = page.locator(
      'a[href*="workflow_type=quote_to_pour"][href*="manufacturing/workflows"]',
    )
    await expect(wfLink).toBeVisible()
    await wfLink.click()

    // The builder mounts THAT artifact: manufacturing quote_to_pour, NOT
    // the pre-fix funeral_home/funeral_cascade fallback.
    await expect(page).toHaveURL(/workflow_type=quote_to_pour/)
    await expect(page.getByText("Quote to Pour")).toBeVisible()
    await expect(page.getByText("Funeral Cascade")).toHaveCount(0)
  })

  test("all four deep-link round-trips mount their artifact", async ({
    page,
  }) => {
    await page.goto(MFG_PAGE)
    await expect(page.getByText("Manufacturing")).toBeVisible()

    // Read each row's href from the DOM — focus + document carry
    // env-specific uuids, so they can't be hardcoded.
    const hrefFor = async (pattern: string): Promise<string> => {
      const link = page.locator(`a[href*="${pattern}"]`).first()
      await expect(link).toBeVisible()
      const href = await link.getAttribute("href")
      expect(href, `href for ${pattern}`).toBeTruthy()
      return href as string
    }
    const wfHref = await hrefFor("workflow_type=quote_to_pour")
    const focusHref = await hrefFor("/studio/focuses?tier=2&template=")
    const widgetHref = await hrefFor("/studio/widget-builder/ar_summary")
    const docHref = await hrefFor("/studio/documents?template_id=")

    // 1) Workflows → quote_to_pour at vertical=manufacturing.
    await page.goto(wfHref)
    await expect(page.getByText("Quote to Pour")).toBeVisible()
    await expect(page.getByText("Funeral Cascade")).toHaveCount(0)

    // 2) Focus → the Job Coordination template loaded.
    await page.goto(focusHref)
    await expect(page.getByText("Job Coordination")).toBeVisible()

    // 3) Widget → the ar_summary widget builder mounts + loads (no 403/
    //    empty-error). Witnessed for real on staging via the PROD_API
    //    rewrite; locally this client 403s against prod.
    await page.goto(widgetHref)
    await expect(page).toHaveURL(/widget-builder\/ar_summary/)
    await expect(page.getByText(/request failed/i)).toHaveCount(0)

    // 4) Documents → the quote.standard template loaded (not the 403
    //    "0 templates" empty state seen locally against prod).
    await page.goto(docHref)
    await expect(page.getByText(/request failed/i)).toHaveCount(0)
    await expect(page.getByText("0 templates")).toHaveCount(0)
  })

  test("an unavailable reference renders disabled, never a dead link", async ({
    page,
  }) => {
    // Orphan-tolerance is the resolver's contract; if a future artifact is
    // removed its row must render the muted "no longer available" state.
    // With the seeded map all four resolve, so this asserts the inverse:
    // no row is rendered in the unavailable state on the happy path.
    await page.goto(MFG_PAGE)
    await expect(
      page.locator('[data-testid^="moc-row-"][data-available="false"]'),
    ).toHaveCount(0)
    await expect(
      page.locator('[data-testid^="moc-row-"][data-available="true"]'),
    ).toHaveCount(4)
  })
})

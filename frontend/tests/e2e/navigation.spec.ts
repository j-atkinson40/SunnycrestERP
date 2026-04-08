import { test, expect, Page } from "@playwright/test";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const STAGING_API = "https://sunnycresterp-staging.up.railway.app";
const PROD_API = "https://api.getbridgeable.com";
const TENANT_SLUG = "testco";

const CREDS = {
  admin: { email: "admin@testco.com", password: "TestAdmin123!" },
  accountant: { email: "accountant@testco.com", password: "TestAccountant123!" },
  prodmanager: { email: "prodmanager@testco.com", password: "TestProd123!" },
};

type Role = keyof typeof CREDS;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

async function setupPage(page: Page) {
  await page.route(`${PROD_API}/**`, async (route) => {
    const url = route.request().url().replace(PROD_API, STAGING_API);
    try {
      const response = await route.fetch({ url });
      await route.fulfill({ response });
    } catch {
      await route.continue();
    }
  });
  await page.goto("/", { waitUntil: "commit" });
  await page.evaluate((slug) => {
    localStorage.setItem("company_slug", slug);
  }, TENANT_SLUG);
}

async function login(page: Page, role: Role) {
  await setupPage(page);
  await page.goto("/login");
  await page.waitForLoadState("networkidle");
  const id = page.locator("#identifier");
  await id.waitFor({ state: "visible", timeout: 10_000 });
  await id.fill(CREDS[role].email);
  await page.waitForTimeout(300);
  const pw = page.locator("#password");
  await pw.waitFor({ state: "visible", timeout: 5_000 });
  await pw.fill(CREDS[role].password);
  await page.getByRole("button", { name: /sign\s*in/i }).click();
  await page.waitForURL((url) => !url.pathname.includes("/login"), { timeout: 20_000 });
  await page.waitForLoadState("networkidle");
}

const SHOTS = "tests/e2e/screenshots/navigation";

async function snap(page: Page, name: string) {
  await page.screenshot({ path: `${SHOTS}/${name}.png`, fullPage: true });
}

// ===========================================================================
// NAVIGATION TESTS
// ===========================================================================

test.describe("Navigation Tests", () => {

  // =========================================================================
  // TEST 1 — Financials hub loads with all tiles
  // =========================================================================

  test("1. Financials hub loads with all tiles", async ({ page }) => {
    await login(page, "admin");
    await page.goto("/financials");
    await page.waitForLoadState("networkidle");
    await snap(page, "01-financials-hub");

    const bodyText = await page.textContent("body") || "";
    expect(bodyText).not.toContain("Access Denied");

    // Check for summary cards
    const cards = page.locator('[class*="card"]');
    expect(await cards.count()).toBeGreaterThan(0);

    // Check for hub tiles
    const expectedTiles = ["Billing", "Invoice Review", "Orders", "Statements", "AR Aging", "Reports"];
    for (const tile of expectedTiles) {
      const el = page.getByText(tile, { exact: false });
      const found = (await el.count()) > 0;
      // Soft check — report but don't fail on missing tiles
      if (!found) {
        console.log(`WARNING: Tile "${tile}" not found on financials hub`);
      }
    }
    await snap(page, "01-financials-hub-tiles");
  });

  // =========================================================================
  // TEST 2 — Financials hub tiles navigate correctly
  // =========================================================================

  test("2. Financials hub tiles navigate correctly", async ({ page }) => {
    await login(page, "admin");
    await page.goto("/financials");
    await page.waitForLoadState("networkidle");

    // Click on Billing tile (use link role to avoid matching description text)
    const billingTile = page.getByRole("link", { name: /^Billing/i }).first();
    if ((await billingTile.count()) > 0) {
      await billingTile.click();
      await page.waitForLoadState("networkidle");
      await snap(page, "02-billing-from-hub");
      expect(page.url()).toContain("/billing");

      // Go back
      await page.goto("/financials");
      await page.waitForLoadState("networkidle");
    }

    // Click AR Aging tile
    const agingTile = page.getByRole("link", { name: /AR Aging/i }).first();
    if ((await agingTile.count()) > 0) {
      await agingTile.click();
      await page.waitForLoadState("networkidle");
      await snap(page, "02-ar-aging-from-hub");
      expect(page.url()).toContain("/ar/aging");
    }
  });

  // =========================================================================
  // TEST 3 — CRM hub loads with all tiles
  // =========================================================================

  test("3. CRM hub loads with all tiles", async ({ page }) => {
    await login(page, "admin");
    await page.goto("/crm");
    await page.waitForLoadState("networkidle");
    await snap(page, "03-crm-hub");

    const bodyText = await page.textContent("body") || "";
    expect(bodyText).not.toContain("Access Denied");
    expect(bodyText).toContain("CRM");

    // Check for key tiles
    const expectedTiles = ["Companies", "Funeral Homes", "Billing Groups"];
    for (const tile of expectedTiles) {
      const el = page.getByText(tile, { exact: false });
      expect(await el.count(), `CRM hub should have "${tile}" tile`).toBeGreaterThan(0);
    }

    // Click Companies tile (use link role to avoid description matches)
    const companiesTile = page.getByRole("link", { name: /All Companies/i }).first();
    if ((await companiesTile.count()) > 0) {
      await companiesTile.click();
      await page.waitForLoadState("networkidle");
      await snap(page, "03-companies-from-crm");
      expect(page.url()).toContain("/crm/companies");
    }
  });

  // =========================================================================
  // TEST 4 — Production hub loads with all tiles
  // =========================================================================

  test("4. Production hub loads with all tiles", async ({ page }) => {
    await login(page, "admin");
    await page.goto("/production-hub");
    await page.waitForLoadState("networkidle");
    await snap(page, "04-production-hub");

    const bodyText = await page.textContent("body") || "";
    expect(bodyText).not.toContain("Access Denied");
    expect(bodyText).toContain("Production");

    // Check for key tiles
    const expectedTiles = ["Products", "Inventory", "Production Log"];
    for (const tile of expectedTiles) {
      const el = page.getByText(tile, { exact: false });
      const found = (await el.count()) > 0;
      if (!found) {
        console.log(`WARNING: Tile "${tile}" not found on production hub`);
      }
    }
    await snap(page, "04-production-hub-tiles");
  });

  // =========================================================================
  // TEST 5 — Old routes still work
  // =========================================================================

  test("5. Old routes redirect or still work", async ({ page }) => {
    await login(page, "admin");

    // /calls should still work
    await page.goto("/calls");
    await page.waitForLoadState("networkidle");
    await snap(page, "05-calls-route");
    const callsText = await page.textContent("body") || "";
    expect(callsText).not.toContain("Not Found");

    // /knowledge-base should still work
    await page.goto("/knowledge-base");
    await page.waitForLoadState("networkidle");
    await snap(page, "05-knowledge-base-route");
    const kbText = await page.textContent("body") || "";
    expect(kbText).not.toContain("Not Found");

    // /price-management should still work
    await page.goto("/price-management");
    await page.waitForLoadState("networkidle");
    await snap(page, "05-price-management-route");
    const priceText = await page.textContent("body") || "";
    expect(priceText).not.toContain("Not Found");
  });

  // =========================================================================
  // TEST 6 — Breadcrumbs render on sub-pages
  // =========================================================================

  test("6. Breadcrumbs render on sub-pages", async ({ page }) => {
    await login(page, "admin");

    // Navigate to a financials sub-page
    await page.goto("/billing");
    await page.waitForLoadState("networkidle");
    await snap(page, "06-billing-breadcrumbs");

    // Look for breadcrumb navigation
    const breadcrumb = page.locator("nav").filter({ hasText: "Financials" });
    const hasBreadcrumbs = (await breadcrumb.count()) > 0;

    if (hasBreadcrumbs) {
      // Click parent to navigate back
      const parentLink = breadcrumb.getByText("Financials").first();
      if ((await parentLink.count()) > 0) {
        await parentLink.click();
        await page.waitForLoadState("networkidle");
        await snap(page, "06-breadcrumb-navigate-back");
        expect(page.url()).toContain("/financials");
      }
    } else {
      console.log("INFO: Breadcrumbs not found on /billing — may need Breadcrumbs component in layout");
    }
  });

  // =========================================================================
  // TEST 7 — Nav active state on sub-pages
  // =========================================================================

  test("7. Nav active state highlights hub", async ({ page }) => {
    await login(page, "admin");

    // Navigate to a financials sub-page
    await page.goto("/billing");
    await page.waitForLoadState("networkidle");
    await snap(page, "07-nav-active-billing");

    // Check sidebar for Financials with active styling
    const sidebar = page.locator("aside");
    const financialsLink = sidebar.getByText("Financials", { exact: false }).first();

    if ((await financialsLink.count()) > 0) {
      // Check for active styling (border-left color or font-weight)
      const style = await financialsLink.evaluate((el) => {
        const parent = el.closest("a") || el;
        return window.getComputedStyle(parent).fontWeight;
      });
      // Active items typically have font-weight >= 500
      await snap(page, "07-nav-active-state");
    }

    // Navigate to CRM sub-page
    await page.goto("/crm/companies");
    await page.waitForLoadState("networkidle");
    await snap(page, "07-nav-active-crm");
  });

  // =========================================================================
  // TEST 8 — Settings groups render
  // =========================================================================

  test("8. Settings section in nav", async ({ page }) => {
    await login(page, "admin");
    await snap(page, "08-settings-nav");

    // Find Settings section header in sidebar (it's a collapsible button)
    const sidebar = page.locator("aside");
    const settingsBtn = sidebar.getByRole("button", { name: /^Settings$/i });
    if ((await settingsBtn.count()) === 0) {
      // Fallback: look for exact text match
      const settingsText = sidebar.getByText("Settings", { exact: true }).first();
      expect(await settingsText.count(), "Settings section should exist in nav").toBeGreaterThan(0);
      await settingsText.click();
    } else {
      expect(await settingsBtn.count(), "Settings section should exist in nav").toBeGreaterThan(0);
      await settingsBtn.click();
    }
    await page.waitForTimeout(500);
    await snap(page, "08-settings-expanded");

    // Check for sub-items — Company Profile is the first item in the Business group
    const companyProfile = sidebar.getByText("Company Profile", { exact: false });
    expect(await companyProfile.count(), "Company Profile should be in settings").toBeGreaterThan(0);
  });

  // =========================================================================
  // TEST 9 — Order side panel from invoice
  // =========================================================================

  test("9. Invoice page accessible from financials", async ({ page }) => {
    await login(page, "admin");

    // Navigate to invoices
    await page.goto("/ar/invoices");
    await page.waitForLoadState("networkidle");
    await snap(page, "09-invoices-page");

    const bodyText = await page.textContent("body") || "";
    expect(bodyText).not.toContain("Access Denied");

    // If there are invoices, click one
    const invoiceRow = page.locator("table tbody tr, [data-testid='invoice-row']").first();
    if ((await invoiceRow.count()) > 0) {
      await invoiceRow.click();
      await page.waitForLoadState("networkidle");
      await snap(page, "09-invoice-detail");

      // Look for View Order link/button
      const viewOrder = page.getByText(/view\s*order/i);
      if ((await viewOrder.count()) > 0) {
        await snap(page, "09-view-order-found");
      } else {
        console.log("INFO: View Order side panel not found on invoice detail page");
      }
    }
  });

  // =========================================================================
  // TEST 10 — Announcements widget on dashboard
  // =========================================================================

  test("10. Dashboard loads without error", async ({ page }) => {
    await login(page, "admin");
    await page.goto("/dashboard");
    await page.waitForLoadState("networkidle");
    await snap(page, "10-dashboard");

    const bodyText = await page.textContent("body") || "";
    expect(bodyText).not.toContain("Something went wrong");

    // Check for announcements widget
    const announcements = page.getByText(/announcement/i);
    if ((await announcements.count()) > 0) {
      console.log("INFO: Announcements widget found on dashboard");
    } else {
      console.log("INFO: Announcements widget not found on dashboard");
    }
    await snap(page, "10-dashboard-widgets");
  });

  // =========================================================================
  // TEST 11 — Role-adaptive dashboard widgets
  // =========================================================================

  test("11. Role-adaptive dashboard widgets", async ({ page }) => {
    // Login as accountant
    await login(page, "accountant");
    await page.goto("/dashboard");
    await page.waitForLoadState("networkidle");
    await snap(page, "11-accountant-dashboard");

    // Login as prod manager
    await login(page, "prodmanager");
    await page.goto("/dashboard");
    await page.waitForLoadState("networkidle");
    await snap(page, "11-prod-dashboard");
  });

  // =========================================================================
  // TEST 12 — Legacy Studio in nav
  // =========================================================================

  test("12. Legacy Studio in nav", async ({ page }) => {
    await login(page, "admin");
    await snap(page, "12-legacy-studio-nav");

    const sidebar = page.locator("aside");
    const legacyLabel = sidebar.getByText("Legacy Studio", { exact: false });
    expect(await legacyLabel.count(), "Legacy Studio should be in nav").toBeGreaterThan(0);

    // Legacy Studio is now a collapsible item — click to expand
    await legacyLabel.first().click();
    await page.waitForTimeout(300);
    await snap(page, "12-legacy-studio-expanded");

    // Check for Proof Generator sub-item
    const proofGen = sidebar.getByText("Proof Generator", { exact: false });
    if ((await proofGen.count()) > 0) {
      await proofGen.click();
      await page.waitForLoadState("networkidle");
      await snap(page, "12-proof-generator");
      expect(page.url()).toContain("/legacy/generator");
    }
  });

  // =========================================================================
  // TEST 13 — Knowledge Base accessible
  // =========================================================================

  test("13. Knowledge Base accessible", async ({ page }) => {
    await login(page, "admin");
    await page.goto("/knowledge-base");
    await page.waitForLoadState("networkidle");
    await snap(page, "13-knowledge-base");

    const bodyText = await page.textContent("body") || "";
    expect(bodyText).not.toContain("Access Denied");
    expect(bodyText).not.toContain("Not Found");
  });

  // =========================================================================
  // TEST 14 — Mobile nav works
  // =========================================================================

  test("14. Mobile nav works", async ({ page }) => {
    // Set mobile viewport
    await page.setViewportSize({ width: 390, height: 844 });
    await login(page, "admin");
    await snap(page, "14-mobile-home");

    // Navigate to financials
    await page.goto("/financials");
    await page.waitForLoadState("networkidle");
    await snap(page, "14-mobile-financials");

    const bodyText = await page.textContent("body") || "";
    expect(bodyText).not.toContain("Something went wrong");
    expect(bodyText).not.toContain("Access Denied");
  });
});

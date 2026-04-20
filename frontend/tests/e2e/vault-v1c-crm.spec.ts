/**
 * Bridgeable Vault — Phase V-1c — CRM absorption E2E.
 *
 * Covers the CRM lift-and-shift: /crm/* → /vault/crm/*, CRM sidebar
 * entry in the Vault Hub, top-level CRM nav removed from manufacturing
 * and FH presets, old-path redirects, CRM widgets on the overview.
 */
import { test, expect, Page } from "@playwright/test";

const STAGING_BACKEND =
  process.env.BACKEND_URL ||
  "https://sunnycresterp-staging.up.railway.app";

const PROD_API = "https://api.getbridgeable.com";
const TENANT_SLUG = "testco";

const CREDS = { email: "admin@testco.com", password: "TestAdmin123!" };

async function setupPage(page: Page) {
  await page.route(`${PROD_API}/**`, async (route) => {
    const url = route.request().url().replace(PROD_API, STAGING_BACKEND);
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

async function login(page: Page) {
  await setupPage(page);
  await page.goto("/login");
  await page.waitForLoadState("networkidle");
  const identifierInput = page.locator("#identifier");
  await identifierInput.waitFor({ state: "visible", timeout: 10_000 });
  await identifierInput.fill(CREDS.email);
  await page.waitForTimeout(300);
  const passwordInput = page.locator("#password");
  await passwordInput.waitFor({ state: "visible", timeout: 5_000 });
  await passwordInput.fill(CREDS.password);
  await page.getByRole("button", { name: /sign\s*in/i }).click();
  await page.waitForURL((url) => !url.pathname.includes("/login"), {
    timeout: 20_000,
  });
}

test.describe("@tenant:sunnycrest Bridgeable Vault V-1c CRM", () => {
  // ── Routes accessible under /vault/crm/* ──────────────────────────

  test("1. /vault/crm landing renders", async ({ page }) => {
    await login(page);
    await page.goto("/vault/crm");
    await page.waitForLoadState("networkidle");
    // VaultHubLayout should be present with its sidebar.
    await expect(page.getByLabel("Vault sidebar")).toBeVisible();
  });

  test("2. /vault/crm/companies renders", async ({ page }) => {
    await login(page);
    await page.goto("/vault/crm/companies");
    await page.waitForLoadState("networkidle");
    const body = await page.textContent("body");
    expect(body).not.toContain("Something went wrong");
    await expect(page.getByLabel("Vault sidebar")).toBeVisible();
  });

  test("3. /vault/crm/pipeline renders", async ({ page }) => {
    await login(page);
    await page.goto("/vault/crm/pipeline");
    await page.waitForLoadState("networkidle");
    const body = await page.textContent("body");
    expect(body).not.toContain("Something went wrong");
  });

  test("4. /vault/crm/funeral-homes renders", async ({ page }) => {
    await login(page);
    await page.goto("/vault/crm/funeral-homes");
    await page.waitForLoadState("networkidle");
    const body = await page.textContent("body");
    expect(body).not.toContain("Something went wrong");
  });

  // ── Old path redirects ────────────────────────────────────────────

  test("5. /crm redirects to /vault/crm", async ({ page }) => {
    await login(page);
    await page.goto("/crm");
    await page.waitForURL(/\/vault\/crm(?:$|\?)/, { timeout: 5_000 });
    expect(page.url()).toContain("/vault/crm");
  });

  test("6. /crm/companies redirects to /vault/crm/companies", async ({
    page,
  }) => {
    await login(page);
    await page.goto("/crm/companies");
    await page.waitForURL(/\/vault\/crm\/companies/, { timeout: 5_000 });
    expect(page.url()).toContain("/vault/crm/companies");
  });

  test("7. /crm/pipeline redirects", async ({ page }) => {
    await login(page);
    await page.goto("/crm/pipeline");
    await page.waitForURL(/\/vault\/crm\/pipeline/, { timeout: 5_000 });
    expect(page.url()).toContain("/vault/crm/pipeline");
  });

  test("8. /crm/settings redirects to /vault/crm/settings", async ({
    page,
  }) => {
    await login(page);
    await page.goto("/crm/settings");
    await page.waitForURL(/\/vault\/crm\/settings/, { timeout: 5_000 });
    expect(page.url()).toContain("/vault/crm/settings");
  });

  // ── Sidebar integration ──────────────────────────────────────────

  test("9. CRM sidebar entry present in Vault Hub", async ({ page }) => {
    await login(page);
    await page.goto("/vault");
    await page.waitForLoadState("networkidle");
    const sidebar = page.getByLabel("Vault sidebar");
    await expect(sidebar).toBeVisible();
    await expect(sidebar.getByRole("link", { name: /^CRM$/ })).toBeVisible();
  });

  test("10. Click CRM in Vault sidebar navigates to /vault/crm", async ({
    page,
  }) => {
    await login(page);
    await page.goto("/vault");
    await page.waitForLoadState("networkidle");
    await page
      .getByLabel("Vault sidebar")
      .getByRole("link", { name: /^CRM$/ })
      .click();
    await page.waitForURL(/\/vault\/crm/, { timeout: 5_000 });
  });

  // ── Top-level CRM nav removed from manufacturing + FH ────────────

  test("11. No top-level CRM nav anchor pointing at /crm", async ({
    page,
  }) => {
    await login(page);
    await page.goto("/dashboard");
    await page.waitForLoadState("networkidle");
    // Post-V-1c, no visible anchor should point at bare /crm. The
    // Vault sidebar CRM entry points at /vault/crm which is fine.
    const staleAnchors = page.locator('a[href="/crm"]');
    const count = await staleAnchors.count();
    let visible = 0;
    for (let i = 0; i < count; i++) {
      if (await staleAnchors.nth(i).isVisible()) visible += 1;
    }
    expect(visible).toBe(0);
  });

  // ── API / activity endpoint ──────────────────────────────────────

  test("12. /api/v1/vault/activity/recent returns 200 for admin", async ({
    request,
    page,
  }) => {
    await login(page);
    const token = await page.evaluate(() =>
      localStorage.getItem("access_token"),
    );
    const slug = await page.evaluate(() =>
      localStorage.getItem("company_slug"),
    );
    const resp = await request.get(
      `${STAGING_BACKEND}/api/v1/vault/activity/recent?limit=5`,
      {
        headers: {
          Authorization: `Bearer ${token}`,
          "X-Company-Slug": slug ?? TENANT_SLUG,
        },
      },
    );
    expect(resp.status()).toBe(200);
    const body = await resp.json();
    expect(Array.isArray(body.activities)).toBe(true);
  });

  // ── CRM widgets on overview ──────────────────────────────────────

  test("13. /api/v1/vault/overview/widgets includes CRM widgets for admin", async ({
    request,
    page,
  }) => {
    await login(page);
    const token = await page.evaluate(() =>
      localStorage.getItem("access_token"),
    );
    const slug = await page.evaluate(() =>
      localStorage.getItem("company_slug"),
    );
    const resp = await request.get(
      `${STAGING_BACKEND}/api/v1/vault/overview/widgets`,
      {
        headers: {
          Authorization: `Bearer ${token}`,
          "X-Company-Slug": slug ?? TENANT_SLUG,
        },
      },
    );
    expect(resp.status()).toBe(200);
    const body = await resp.json();
    const ids = (body.widgets as Array<{ widget_id: string }>).map(
      (w) => w.widget_id,
    );
    expect(ids).toContain("vault_crm_recent_activity");
    expect(ids).toContain("at_risk_accounts");
  });
});

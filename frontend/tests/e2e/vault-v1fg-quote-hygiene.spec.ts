/**
 * Bridgeable Vault — Phase V-1f+g — Quote VaultItem hygiene E2E.
 *
 * Covers the frontend surface of V-1f+g:
 *   - Quoting Hub shows the "Customize quote template" deep-link
 *   - The link navigates to /vault/documents/templates with a search
 *     filter matching quote.standard
 *   - Delivery deliveries endpoint still accepts + renders requests
 *     (smoke check that the new caller_vault_item_id column didn't
 *     break anything upstream)
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

test.describe("@tenant:sunnycrest Bridgeable Vault V-1f+g Quote hygiene", () => {
  // ── Customize quote template deep-link ─────────────────────────────

  test("1. Quoting Hub renders with the Customize quote template link", async ({
    page,
  }) => {
    await login(page);
    await page.goto("/quoting");
    await page.waitForLoadState("networkidle");
    const link = page.getByRole("link", {
      name: /Customize quote template/i,
    });
    await expect(link).toBeVisible();
  });

  test("2. Customize quote template link points at Vault templates with search filter", async ({
    page,
  }) => {
    await login(page);
    await page.goto("/quoting");
    await page.waitForLoadState("networkidle");
    const link = page.getByRole("link", {
      name: /Customize quote template/i,
    });
    const href = await link.getAttribute("href");
    expect(href).toBeTruthy();
    expect(href!.startsWith("/vault/documents/templates")).toBe(true);
    // `search=quote.standard` filter narrows to the Quote template.
    expect(href!).toContain("search=quote.standard");
  });

  test("3. Clicking the link navigates to the templates library", async ({
    page,
  }) => {
    await login(page);
    await page.goto("/quoting");
    await page.waitForLoadState("networkidle");
    await page
      .getByRole("link", { name: /Customize quote template/i })
      .click();
    await page.waitForURL(/\/vault\/documents\/templates/, {
      timeout: 5_000,
    });
    expect(page.url()).toContain("/vault/documents/templates");
    expect(page.url()).toContain("search=quote.standard");
  });

  // ── Delivery deliveries endpoint smoke (ensure migration didn't
  //    break existing admin UI) ───────────────────────────────────────

  test("4. /api/v1/documents-v2/deliveries still returns 200 for admin", async ({
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
      `${STAGING_BACKEND}/api/v1/documents-v2/deliveries?limit=5`,
      {
        headers: {
          Authorization: `Bearer ${token}`,
          "X-Company-Slug": slug ?? TENANT_SLUG,
        },
      },
    );
    expect(resp.status()).toBe(200);
  });
});

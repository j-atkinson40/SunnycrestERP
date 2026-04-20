/**
 * Bridgeable Vault — Phase V-1a — Hub frame + nav restructure E2E.
 *
 * Asserts the nav entry + URL migrations + sidebar composition that
 * V-1a shipped. Pre-V-1a admin paths (/admin/documents/*, /admin/
 * intelligence/*) should redirect to their /vault/* equivalents.
 *
 * Test pattern mirrors `documents.spec.ts` — staging backend via the
 * claude-in-chrome prod→staging fetch redirect, testco tenant, admin
 * credentials.
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

test.describe("@tenant:sunnycrest Bridgeable Vault V-1a", () => {
  // ── Nav presence ───────────────────────────────────────────────────

  test("1. Bridgeable Vault nav entry visible in sidebar", async ({
    page,
  }) => {
    await login(page);
    // Admin user: entry should render. Look in the main sidebar.
    await expect(
      page.getByRole("link", { name: /Bridgeable Vault/i }).first()
    ).toBeVisible();
  });

  // ── /vault landing ────────────────────────────────────────────────

  test("2. /vault landing page renders", async ({ page }) => {
    await login(page);
    await page.goto("/vault");
    await page.waitForLoadState("networkidle");

    await expect(
      page.getByRole("heading", { name: /Bridgeable Vault/i })
    ).toBeVisible();
    // The landing-page description + service cards.
    await expect(
      page.getByText(/Your platform infrastructure hub/i)
    ).toBeVisible();
  });

  test("3. Vault sidebar lists Overview + Documents + Intelligence", async ({
    page,
  }) => {
    await login(page);
    await page.goto("/vault");
    await page.waitForLoadState("networkidle");

    const sidebar = page.getByLabel("Vault sidebar");
    await expect(sidebar).toBeVisible();
    await expect(
      sidebar.getByRole("link", { name: /Overview/i })
    ).toBeVisible();
    await expect(
      sidebar.getByRole("link", { name: /Documents/i })
    ).toBeVisible();
    await expect(
      sidebar.getByRole("link", { name: /Intelligence/i })
    ).toBeVisible();
  });

  // ── New /vault/* paths work ─────────────────────────────────────────

  test("4. Documents pages accessible under /vault/documents", async ({
    page,
  }) => {
    await login(page);
    await page.goto("/vault/documents/templates");
    await page.waitForLoadState("networkidle");

    await expect(
      page.getByRole("heading", { name: /Document Templates/i })
    ).toBeVisible();

    // Sidebar should highlight Documents as active.
    const sidebar = page.getByLabel("Vault sidebar");
    await expect(sidebar).toBeVisible();
  });

  test("5. Intelligence pages accessible under /vault/intelligence", async ({
    page,
  }) => {
    await login(page);
    await page.goto("/vault/intelligence/prompts");
    await page.waitForLoadState("networkidle");

    const body = await page.textContent("body");
    expect(body).not.toContain("Something went wrong");
    // Sidebar still visible on Intelligence pages.
    await expect(page.getByLabel("Vault sidebar")).toBeVisible();
  });

  // ── Pre-V-1a redirects ─────────────────────────────────────────────

  test("6. Old /admin/documents redirects to /vault/documents", async ({
    page,
  }) => {
    await login(page);
    await page.goto("/admin/documents/templates");
    // Redirect is client-side; wait for final URL.
    await page.waitForURL(/\/vault\/documents\/templates/, {
      timeout: 5_000,
    });
    expect(page.url()).toContain("/vault/documents/templates");
  });

  test("7. Old /admin/intelligence redirects to /vault/intelligence", async ({
    page,
  }) => {
    await login(page);
    await page.goto("/admin/intelligence/prompts");
    await page.waitForURL(/\/vault\/intelligence\/prompts/, {
      timeout: 5_000,
    });
    expect(page.url()).toContain("/vault/intelligence/prompts");
  });

  test("8. Old /admin/documents/inbox redirects to /vault/documents/inbox", async ({
    page,
  }) => {
    await login(page);
    await page.goto("/admin/documents/inbox");
    await page.waitForURL(/\/vault\/documents\/inbox/, { timeout: 5_000 });
    expect(page.url()).toContain("/vault/documents/inbox");
  });

  // ── API ────────────────────────────────────────────────────────────

  test("9. /api/v1/vault/services returns registered services", async ({
    request,
    page,
  }) => {
    await login(page);
    const token = await page.evaluate(() =>
      localStorage.getItem("access_token")
    );
    const slug = await page.evaluate(() =>
      localStorage.getItem("company_slug")
    );
    const resp = await request.get(
      `${STAGING_BACKEND}/api/v1/vault/services`,
      {
        headers: {
          Authorization: `Bearer ${token}`,
          "X-Company-Slug": slug ?? TENANT_SLUG,
        },
      }
    );
    expect(resp.status()).toBe(200);
    const body = await resp.json();
    const keys = (body.services as Array<{ service_key: string }>).map(
      (s) => s.service_key
    );
    expect(keys).toContain("documents");
    expect(keys).toContain("intelligence");
  });

  // ── Settings → Platform cleanup ────────────────────────────────────

  test("10. Settings → Platform no longer lists Documents/Intelligence entries", async ({
    page,
  }) => {
    await login(page);
    // Go to a page whose sidebar exposes the Settings section.
    await page.goto("/dashboard");
    await page.waitForLoadState("networkidle");

    // The Platform subgroup under Settings should not contain any
    // nav entry whose href starts with /admin/documents or
    // /admin/intelligence. Collect all anchors and assert.
    const stale = await page
      .locator('a[href^="/admin/documents"], a[href^="/admin/intelligence"]')
      .all();
    // Filter to visible anchors (some may be redirect fallbacks).
    let visibleStale = 0;
    for (const a of stale) {
      if (await a.isVisible()) visibleStale += 1;
    }
    expect(visibleStale).toBe(0);
  });
});

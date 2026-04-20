/**
 * Bridgeable Vault — Phase V-1d — Notifications as full service E2E.
 *
 * Covers the Notifications promotion: /notifications → /vault/notifications
 * with redirect, notifications entry in the Vault hub sidebar, FH nav
 * entry removed, unread-feed API stays wired.
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

test.describe("@tenant:sunnycrest Bridgeable Vault V-1d Notifications", () => {
  // ── /vault/notifications is the canonical path ──────────────────────

  test("1. /vault/notifications renders inside Vault Hub layout", async ({
    page,
  }) => {
    await login(page);
    await page.goto("/vault/notifications");
    await page.waitForLoadState("networkidle");
    const body = await page.textContent("body");
    expect(body).not.toContain("Something went wrong");
    // Vault sidebar present — confirms we're rendering under the hub layout.
    await expect(page.getByLabel("Vault sidebar")).toBeVisible();
  });

  // ── Old path redirect ────────────────────────────────────────────────

  test("2. /notifications redirects to /vault/notifications", async ({
    page,
  }) => {
    await login(page);
    await page.goto("/notifications");
    await page.waitForURL(/\/vault\/notifications(?:$|\?)/, {
      timeout: 5_000,
    });
    expect(page.url()).toContain("/vault/notifications");
  });

  // ── Vault hub sidebar entry ─────────────────────────────────────────

  test("3. Notifications entry present in Vault hub sidebar", async ({
    page,
  }) => {
    await login(page);
    await page.goto("/vault");
    await page.waitForLoadState("networkidle");
    const sidebar = page.getByLabel("Vault sidebar");
    await expect(sidebar).toBeVisible();
    await expect(
      sidebar.getByRole("link", { name: /^Notifications$/ }),
    ).toBeVisible();
  });

  test("4. Clicking Notifications in hub sidebar navigates to /vault/notifications", async ({
    page,
  }) => {
    await login(page);
    await page.goto("/vault");
    await page.waitForLoadState("networkidle");
    await page
      .getByLabel("Vault sidebar")
      .getByRole("link", { name: /^Notifications$/ })
      .click();
    await page.waitForURL(/\/vault\/notifications/, { timeout: 5_000 });
  });

  // ── Top-level nav no longer carries a Notifications entry ───────────

  test("5. No top-level /notifications nav anchor (FH preset cleaned)", async ({
    page,
  }) => {
    await login(page);
    await page.goto("/dashboard");
    await page.waitForLoadState("networkidle");
    // Post-V-1d nothing visible should link to bare /notifications.
    // The Vault sidebar Notifications entry points at /vault/notifications.
    const staleAnchors = page.locator('a[href="/notifications"]');
    const count = await staleAnchors.count();
    let visible = 0;
    for (let i = 0; i < count; i++) {
      if (await staleAnchors.nth(i).isVisible()) visible += 1;
    }
    expect(visible).toBe(0);
  });

  // ── /vault/services includes notifications ──────────────────────────

  test("6. /api/v1/vault/services includes notifications for admin", async ({
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
      `${STAGING_BACKEND}/api/v1/vault/services`,
      {
        headers: {
          Authorization: `Bearer ${token}`,
          "X-Company-Slug": slug ?? TENANT_SLUG,
        },
      },
    );
    expect(resp.status()).toBe(200);
    const body = await resp.json();
    const services = body.services as Array<{
      service_key: string;
      route_prefix: string;
    }>;
    const notif = services.find((s) => s.service_key === "notifications");
    expect(notif).toBeTruthy();
    expect(notif!.route_prefix).toBe("/vault/notifications");
  });

  // ── Notifications list endpoint still works ─────────────────────────

  test("7. /api/v1/notifications returns 200 for admin", async ({
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
      `${STAGING_BACKEND}/api/v1/notifications?per_page=5`,
      {
        headers: {
          Authorization: `Bearer ${token}`,
          "X-Company-Slug": slug ?? TENANT_SLUG,
        },
      },
    );
    expect(resp.status()).toBe(200);
    const body = await resp.json();
    expect(Array.isArray(body.items)).toBe(true);
  });
});

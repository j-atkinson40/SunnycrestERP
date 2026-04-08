/**
 * Smoke tests — minimal post-deploy health check.
 *
 * Runs in <2 minutes after every Railway deploy.
 * Failures are tagged @tenant:sunnycrest and logged
 * as platform_incidents via the incident reporter.
 *
 * 5 tests:
 *   1. Platform is up (API health check)
 *   2. Login works
 *   3. Dashboard loads
 *   4. Order station loads
 *   5. API returns no 500 errors
 */
import { test, expect } from "@playwright/test";

const STAGING_BACKEND =
  process.env.BACKEND_URL ||
  "https://sunnycresterp-staging.up.railway.app";

const STAGING_FRONTEND =
  process.env.STAGING_URL ||
  "https://determined-renewal-staging.up.railway.app";

// ---------------------------------------------------------------------------
// Login helper (copied from other test files for independence)
// ---------------------------------------------------------------------------

const CREDS: Record<string, { email: string; password: string }> = {
  admin: { email: "admin@testco.com", password: "TestAdmin123!" },
};

async function login(page: import("@playwright/test").Page) {
  await page.goto("/login");
  await page.waitForLoadState("networkidle");

  const emailInput = page.locator('input[type="email"], input[name="email"]');
  if ((await emailInput.count()) > 0) {
    await emailInput.fill(CREDS.admin.email);
    await page.waitForTimeout(300);
  }

  const passwordInput = page.locator(
    'input[type="password"], input[name="password"]'
  );
  if ((await passwordInput.count()) > 0) {
    await passwordInput.fill(CREDS.admin.password);
  }

  const submitBtn = page.locator(
    'button[type="submit"], button:has-text("Sign In"), button:has-text("Log In")'
  );
  if ((await submitBtn.count()) > 0) {
    await submitBtn.first().click();
  }

  // Wait for redirect away from /login
  await page.waitForURL((url) => !url.pathname.includes("/login"), {
    timeout: 15000,
  });
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

test.describe("@tenant:sunnycrest Smoke Tests", () => {
  test("1. Platform is up — API health check", async ({ request }) => {
    const resp = await request.get(`${STAGING_BACKEND}/api/health`);
    expect(resp.status()).toBe(200);

    const body = await resp.json();
    expect(body.status).toBe("healthy");
  });

  test("2. Login works", async ({ page }) => {
    await login(page);

    // Should not be on /login anymore
    expect(page.url()).not.toContain("/login");

    // No error toast visible
    const errorToast = page.locator('[data-sonner-toast][data-type="error"]');
    expect(await errorToast.count()).toBe(0);
  });

  test("3. Dashboard loads", async ({ page }) => {
    await login(page);

    await page.goto("/");
    await page.waitForLoadState("networkidle");

    // Page should not show error state
    const body = await page.textContent("body");
    expect(body).not.toContain("Something went wrong");

    // At least one nav item should be visible
    const nav = page.locator("aside");
    if ((await nav.count()) > 0) {
      const navText = await nav.textContent();
      expect(navText?.length).toBeGreaterThan(5);
    }
  });

  test("4. Order station loads", async ({ page }) => {
    await login(page);

    await page.goto("/order-station");
    await page.waitForLoadState("networkidle");

    // Page should not show error state
    const body = await page.textContent("body");
    expect(body).not.toContain("Something went wrong");
  });

  test("5. API returns no 500 errors", async ({ page }) => {
    await login(page);

    // Collect API responses
    const serverErrors: string[] = [];
    page.on("response", (response) => {
      if (
        response.url().includes("/api/") &&
        response.status() >= 500
      ) {
        serverErrors.push(
          `${response.status()} ${response.url()}`
        );
      }
    });

    // Navigate to dashboard — triggers multiple API calls
    await page.goto("/");
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(2000);

    expect(
      serverErrors,
      `Server errors detected: ${serverErrors.join(", ")}`
    ).toHaveLength(0);
  });
});

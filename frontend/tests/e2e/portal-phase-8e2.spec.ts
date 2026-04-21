/**
 * Portal Foundation — Workflow Arc Phase 8e.2 Playwright smoke tests.
 *
 * Three architectural-boundary smoke tests per the Phase 8e.2 audit
 * approval:
 *
 *   1. Branded login page renders with tenant logo/name + brand color
 *   2. Driver home renders post-login with portal data
 *   3. No DotNav, no command bar, no settings in the portal shell
 *
 * These are mocked self-contained tests — the backend is stubbed via
 * Playwright route interception. They verify the frontend shell +
 * routing + branding application, NOT end-to-end backend behavior.
 * Backend end-to-end coverage lives in the pytest tests at
 * `tests/test_portal_phase8e2.py`.
 */

import { test, expect, Page } from "@playwright/test";

const SLUG = "sunnycrest";
const BRAND_COLOR = "#1E40AF";
const DISPLAY_NAME = "Sunnycrest";

// Minimal branding payload reused across tests.
const brandingPayload = {
  slug: SLUG,
  display_name: DISPLAY_NAME,
  logo_url: null,
  brand_color: BRAND_COLOR,
  footer_text: null,
};

async function stubPortalBackend(page: Page) {
  // Public branding endpoint — no auth.
  await page.route(
    `**/api/v1/portal/${SLUG}/branding`,
    async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(brandingPayload),
      });
    },
  );

  // Login endpoint — returns a token pair.
  await page.route(
    `**/api/v1/portal/${SLUG}/login`,
    async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          access_token: "mock-access-token",
          refresh_token: "mock-refresh-token",
          token_type: "bearer",
          space_id: "sp_driver000001",
        }),
      });
    },
  );

  // /me endpoint — returns the portal user.
  await page.route("**/api/v1/portal/me", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: "pu_abc123",
        email: "driver@sunnycrest.com",
        first_name: "Jane",
        last_name: "Driver",
        company_id: "co_123",
        assigned_space_id: "sp_driver000001",
      }),
    });
  });

  // Driver summary.
  await page.route(
    "**/api/v1/portal/drivers/me/summary",
    async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          portal_user_id: "pu_abc123",
          driver_id: "dr_456",
          driver_name: "Jane Driver",
          today_stops_count: 4,
          tenant_display_name: DISPLAY_NAME,
        }),
      });
    },
  );
}

// ── Test 1 — Branded login ──────────────────────────────────────────

test("portal login renders with tenant branding", async ({ page }) => {
  await stubPortalBackend(page);
  await page.goto(`/portal/${SLUG}/login`);

  // Login form container renders.
  await expect(
    page.locator("[data-testid=portal-login-form-container]"),
  ).toBeVisible();

  // Tenant display name appears in the headline.
  await expect(page.getByText(DISPLAY_NAME)).toBeVisible();

  // Brand color applied to the login header via --portal-brand CSS var.
  const brandColor = await page.evaluate(() =>
    window
      .getComputedStyle(document.documentElement)
      .getPropertyValue("--portal-brand")
      .trim(),
  );
  expect(brandColor).toBe(BRAND_COLOR);

  // Submit button disabled until email + password present.
  const submit = page.locator("[data-testid=portal-login-submit]");
  await expect(submit).toBeDisabled();

  await page.locator("[data-testid=portal-login-email]").fill("x@y.com");
  await page.locator("[data-testid=portal-login-password]").fill("z");
  await expect(submit).toBeEnabled();
});

// ── Test 2 — Driver home post-login ─────────────────────────────────

test("portal driver home renders after login", async ({ page }) => {
  await stubPortalBackend(page);
  await page.goto(`/portal/${SLUG}/login`);

  // Fill + submit login.
  await page
    .locator("[data-testid=portal-login-email]")
    .fill("driver@sunnycrest.com");
  await page
    .locator("[data-testid=portal-login-password]")
    .fill("goodpass123");
  await page.locator("[data-testid=portal-login-submit]").click();

  // Wait for navigation to /portal/<slug>/driver.
  await page.waitForURL(`**/portal/${SLUG}/driver`);

  // Driver home renders.
  await expect(
    page.locator("[data-testid=portal-driver-home]"),
  ).toBeVisible();

  // Today's stops count renders as "4".
  await expect(
    page.locator("[data-testid=portal-driver-today-stops]"),
  ).toContainText("4");

  // Portal header carries tenant name (or logo — null here, so name).
  await expect(
    page.locator("[data-testid=portal-header]"),
  ).toContainText(DISPLAY_NAME);

  // Signed-in user's name in the header.
  await expect(
    page.locator("[data-testid=portal-header]"),
  ).toContainText("Jane Driver");
});

// ── Test 3 — No DotNav / command bar / settings in portal ───────────

test("portal shell has no DotNav, no command bar, no settings nav", async ({
  page,
}) => {
  await stubPortalBackend(page);
  await page.goto(`/portal/${SLUG}/login`);
  await page
    .locator("[data-testid=portal-login-email]")
    .fill("driver@sunnycrest.com");
  await page
    .locator("[data-testid=portal-login-password]")
    .fill("goodpass123");
  await page.locator("[data-testid=portal-login-submit]").click();
  await page.waitForURL(`**/portal/${SLUG}/driver`);

  // Phase 8a DotNav → absent.
  await expect(page.locator("[data-testid=dot-nav]")).toHaveCount(0);

  // Command bar trigger → absent. (Sidebar command bar button.)
  await expect(
    page.locator("[data-testid=command-bar-trigger]"),
  ).toHaveCount(0);

  // Settings nav entry → absent.
  await expect(
    page.getByRole("link", { name: /settings/i }),
  ).toHaveCount(0);

  // Cmd+K should NOT open a command bar (since there isn't one).
  // If command bar were mounted, pressing Cmd+K would toggle the
  // overlay with data-testid=command-bar-overlay.
  await page.keyboard.press("Meta+K");
  await expect(
    page.locator("[data-testid=command-bar-overlay]"),
  ).toHaveCount(0);

  // Portal-scoped DotNav is specifically absent.
  await expect(page.locator("[data-testid=dot-nav]")).toHaveCount(0);
});

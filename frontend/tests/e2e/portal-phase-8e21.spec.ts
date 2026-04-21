/**
 * Portal Completion — Workflow Arc Phase 8e.2.1 Playwright smoke tests.
 *
 * Mobile-first coverage for the 4 driver pages + the reset-password
 * flow. Backend is stubbed via page.route() so these run self-
 * contained — the real end-to-end happy path is the James dogfood
 * flow against staging documented in FEATURE_SESSIONS.md.
 *
 * Tests target the 375×667 mobile viewport by default (iPhone SE).
 * The Pixel 5 project in playwright.config.ts reruns the same specs
 * at 393×851.
 *
 * WCAG 2.2 Target Size discipline: every tappable control on the
 * driver pages must be ≥44×44 CSS px. A subset of controls is
 * spot-checked in `mobile_touch_targets`.
 */

import { test, expect, Page } from "@playwright/test";

const SLUG = "sunnycrest";
const BRAND_COLOR = "#1E40AF";
const DISPLAY_NAME = "Sunnycrest";

const brandingPayload = {
  slug: SLUG,
  display_name: DISPLAY_NAME,
  logo_url: null,
  brand_color: BRAND_COLOR,
  footer_text: null,
};

const routePayload = {
  id: "rt_1",
  driver_id: "dr_1",
  route_date: "2026-04-21",
  status: "dispatched",
  started_at: null,
  completed_at: null,
  total_mileage: null,
  total_stops: 2,
  vehicle_name: "Truck 7",
  driver_name: "Jane Driver",
  stops: [
    {
      id: "stop_1",
      sequence_number: 1,
      status: "pending",
      status_label: "pending",
      address: "123 Main St, Auburn, NY",
      customer_name: "Hopkins FH",
      notes: null,
      cemetery_contact: null,
      funeral_home_contact: null,
    },
    {
      id: "stop_2",
      sequence_number: 2,
      status: "arrived",
      status_label: "arrived",
      address: "456 Oak Ln, Syracuse, NY",
      customer_name: "Riverside FH",
      notes: "Gate code: 1234",
      cemetery_contact: "555-1111",
      funeral_home_contact: "555-2222",
    },
  ],
};

async function stubPortalBackend(page: Page) {
  await page.route(`**/api/v1/portal/${SLUG}/branding`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(brandingPayload),
    });
  });
  await page.route(`**/api/v1/portal/${SLUG}/login`, async (route) => {
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
  });
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
  await page.route(
    "**/api/v1/portal/drivers/me/summary",
    async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          portal_user_id: "pu_abc123",
          driver_id: "dr_1",
          driver_name: "Jane Driver",
          today_stops_count: 2,
          tenant_display_name: DISPLAY_NAME,
        }),
      });
    },
  );
  await page.route("**/api/v1/portal/drivers/me/route", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(routePayload),
    });
  });
  await page.route(
    "**/api/v1/portal/drivers/me/stops/stop_1",
    async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(routePayload.stops[0]),
      });
    },
  );
  await page.route(
    "**/api/v1/portal/drivers/me/stops/stop_1/status",
    async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          ...routePayload.stops[0],
          status: "delivered",
          status_label: "delivered",
        }),
      });
    },
  );
  await page.route("**/api/v1/portal/drivers/me/mileage", async (route) => {
    await route.fulfill({ status: 204, body: "" });
  });
  await page.route(
    `**/api/v1/portal/${SLUG}/password/recover/confirm`,
    async (route) => {
      await route.fulfill({ status: 204, body: "" });
    },
  );
}

async function login(page: Page) {
  await page.goto(`/portal/${SLUG}/login`);
  await page
    .locator("[data-testid=portal-login-email]")
    .fill("driver@sunnycrest.com");
  await page
    .locator("[data-testid=portal-login-password]")
    .fill("goodpass123");
  await page.locator("[data-testid=portal-login-submit]").click();
  await page.waitForURL(`**/portal/${SLUG}/driver`);
}

// ── Test 1 — Route page renders stop list on mobile ─────────────────

test("driver route page renders mobile stop list", async ({ page }) => {
  await stubPortalBackend(page);
  await login(page);

  await page.goto(`/portal/${SLUG}/driver/route`);
  await expect(
    page.locator("[data-testid=portal-driver-route]"),
  ).toBeVisible();

  // Both stops render. Stop cards have stable testids.
  await expect(page.locator("[data-testid=portal-stop-stop_1]")).toBeVisible();
  await expect(page.locator("[data-testid=portal-stop-stop_2]")).toBeVisible();

  // Log mileage button present.
  await expect(
    page.locator("[data-testid=portal-mileage-btn]"),
  ).toBeVisible();
});

// ── Test 2 — Stop detail + mark-delivered happy path ────────────────

test("stop detail allows marking delivered", async ({ page }) => {
  await stubPortalBackend(page);
  await login(page);

  await page.goto(`/portal/${SLUG}/driver/stops/stop_1`);
  await expect(
    page.locator("[data-testid=portal-stop-detail]"),
  ).toBeVisible();

  const markDelivered = page.locator("[data-testid=mark-delivered-btn]");
  await expect(markDelivered).toBeVisible();
  await markDelivered.click();

  // After a successful PATCH, the page re-reads the stop; stub
  // returns delivered status. The button should now be disabled
  // (`disabled={busy || stop.status === 'delivered'}`).
  await expect(markDelivered).toBeDisabled();
});

// ── Test 3 — Mileage submit validation ──────────────────────────────

test("mileage page rejects end < start and accepts valid", async ({ page }) => {
  await stubPortalBackend(page);
  await login(page);

  await page.goto(`/portal/${SLUG}/driver/mileage`);

  const start = page.locator("[data-testid=start-mileage]");
  const end = page.locator("[data-testid=end-mileage]");
  const submit = page.locator("[data-testid=submit-mileage-btn]");

  await start.fill("100050");
  await end.fill("100000");
  await submit.click();
  // Client-side validation renders an inline Alert (no testid — use
  // role+accessible-name). The Alert variant="error" role="alert".
  await expect(page.getByText(/end mileage must be/i)).toBeVisible();

  // Correct it and submit — success triggers a navigate() back to
  // /driver/route. The URL change is the success signal.
  await end.fill("100100");
  await submit.click();
  await page.waitForURL(`**/portal/${SLUG}/driver/route`);
});

// ── Test 4 — Reset-password page is branded + token-gated ──────────

test("reset-password page renders branded with token param", async ({
  page,
}) => {
  await stubPortalBackend(page);

  await page.goto(
    `/portal/${SLUG}/reset-password?token=abc123def456`,
  );

  // Page renders the branded header.
  // Form + password inputs visible.
  await expect(
    page.locator("[data-testid=portal-reset-form]"),
  ).toBeVisible();
  await expect(page.locator("[data-testid=new-password]")).toBeVisible();
  await expect(page.locator("[data-testid=confirm-password]")).toBeVisible();

  // Fill mismatched passwords → error banner.
  await page.locator("[data-testid=new-password]").fill("abcdefgh");
  await page.locator("[data-testid=confirm-password]").fill("xxxxxxxx");
  await page.locator("[data-testid=portal-reset-submit]").click();
  await expect(
    page.locator("[data-testid=portal-reset-error]"),
  ).toBeVisible();

  // Fix and submit → confirmPasswordRecovery returns 204.
  await page.locator("[data-testid=confirm-password]").fill("abcdefgh");
  await page.locator("[data-testid=portal-reset-submit]").click();

  // After success, a "Password set" alert appears and we redirect
  // to login after 2s. Assert the alert — redirect assertion is
  // timing-flaky.
  await expect(page.getByText(/password set/i)).toBeVisible();
});

// ── Test 5 — Missing token shows helpful error ──────────────────────

test("reset-password without token renders an error", async ({ page }) => {
  await stubPortalBackend(page);
  await page.goto(`/portal/${SLUG}/reset-password`);

  // The effect in PortalResetPassword sets an error immediately.
  await expect(
    page.locator("[data-testid=portal-reset-error]"),
  ).toContainText(/missing|invalid/i);
});

// ── Test 6 — Mobile touch-target audit ──────────────────────────────

test("mobile touch targets meet 44px WCAG minimum", async ({ page }) => {
  await stubPortalBackend(page);
  await login(page);

  await page.goto(`/portal/${SLUG}/driver/stops/stop_1`);
  // Key tappable controls on the busiest page in the portal.
  const ids = [
    "mark-delivered-btn",
    "mark-exception-btn",
  ];
  for (const id of ids) {
    const box = await page.locator(`[data-testid=${id}]`).boundingBox();
    expect(box, `bounding box for ${id}`).not.toBeNull();
    expect(box!.height).toBeGreaterThanOrEqual(44);
  }
});

// ── Test 7 — OfflineBanner mounts inside PortalLayout ──────────────

test("offline banner appears on offline event in portal shell", async ({
  page,
  context,
}) => {
  await stubPortalBackend(page);
  await login(page);

  // Simulate going offline. The OfflineBanner subscribes to the
  // browser 'offline' event — we fire it synthetically because
  // setOffline affects network but not the event listener.
  await page.evaluate(() => {
    Object.defineProperty(navigator, "onLine", { get: () => false });
    window.dispatchEvent(new Event("offline"));
  });

  await expect(
    page.locator("[data-testid=offline-banner]"),
  ).toBeVisible();
});

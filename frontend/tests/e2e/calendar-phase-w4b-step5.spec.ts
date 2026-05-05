/**
 * Bridgeable Calendar — Phase W-4b Layer 1 Step 5 cross-surface E2E.
 *
 * Lightweight smoke coverage of the four cross-surface rendering
 * deliverables Step 5 ships per Q7 confirmed pre-build:
 *
 *   1. calendar_glance_widget_definition — widget seeded in catalog
 *   2. calendar_glance_endpoint          — /widget-data/calendar-glance
 *   3. calendar_summary_endpoint         — /widget-data/calendar-summary
 *   4. today_calendar_endpoint           — /widget-data/today-calendar
 *   5. customer_pulse_events_endpoint    — /pulse/calendar-events-for-customer
 *   6. event_linkages_endpoint           — /calendar-events/{id}/linkages
 *   7. event_detail_route_render         — /calendar/events/:id renders or
 *                                          gracefully no-data when no events
 *
 * Spec discipline: lightweight smoke. Full functional coverage lives
 * in `backend/tests/test_calendar_step5_cross_surface.py` (28 tests).
 * Playwright here verifies the cross-surface contract surfaces don't
 * crash on a populated tenant + that the new event detail route mounts
 * inside the authenticated app shell.
 *
 * Staging-canonical: prod→staging fetch redirect, testco tenant.
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
  const id = page.locator("#identifier");
  await id.waitFor({ state: "visible", timeout: 10_000 });
  await id.fill(CREDS.email);
  await page.waitForTimeout(300);
  const pw = page.locator("#password");
  await pw.waitFor({ state: "visible", timeout: 5_000 });
  await pw.fill(CREDS.password);
  await page.getByRole("button", { name: /sign\s*in/i }).click();
  await page.waitForURL((url) => !url.pathname.includes("/login"), {
    timeout: 20_000,
  });
}


async function authedFetch(
  page: Page,
  path: string,
  init?: { method?: string; body?: unknown },
): Promise<{ status: number; body: unknown }> {
  return await page.evaluate(
    async ([url, method, body]) => {
      const res = await fetch(url as string, {
        method: (method as string) || "GET",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${localStorage.getItem("access_token") ?? ""}`,
          "X-Company-Slug": localStorage.getItem("company_slug") ?? "",
        },
        body: body ? JSON.stringify(body) : undefined,
      });
      let data: unknown = null;
      try {
        data = await res.json();
      } catch {
        // empty / non-JSON
      }
      return { status: res.status, body: data };
    },
    [path, init?.method ?? "GET", init?.body ?? null],
  );
}


test.describe("Calendar Step 5 — cross-surface rendering", () => {
  test("calendar_glance_endpoint_smoke", async ({ page }) => {
    await login(page);
    const r = await authedFetch(page, "/api/v1/widget-data/calendar-glance");
    // 200 OK regardless of whether tenant has any calendar accounts —
    // empty payload is canonical when no accessible accounts exist.
    expect(r.status).toBe(200);
    const data = r.body as Record<string, unknown>;
    expect(data).toHaveProperty("has_calendar_access");
    expect(data).toHaveProperty("pending_response_count");
  });

  test("calendar_summary_endpoint_smoke", async ({ page }) => {
    await login(page);
    const r = await authedFetch(
      page,
      "/api/v1/widget-data/calendar-summary?days=7",
    );
    expect(r.status).toBe(200);
    const data = r.body as Record<string, unknown>;
    expect(data).toHaveProperty("has_calendar_access");
    expect(data).toHaveProperty("window_days");
    expect(data).toHaveProperty("by_day");
  });

  test("today_calendar_endpoint_smoke", async ({ page }) => {
    await login(page);
    const r = await authedFetch(
      page,
      "/api/v1/widget-data/today-calendar",
    );
    expect(r.status).toBe(200);
    const data = r.body as Record<string, unknown>;
    expect(data).toHaveProperty("has_calendar_access");
    expect(data).toHaveProperty("today_event_count");
  });

  test("event_detail_route_renders", async ({ page }) => {
    await login(page);
    // Synthetic event id — Step 5 renders an "Event not found" empty
    // state (page.tsx fallback) when the event doesn't exist; verifies
    // the route mounts under AppLayout without crashing.
    await page.goto("/calendar/events/00000000-0000-0000-0000-000000000000");
    await page.waitForLoadState("networkidle");
    // Either the event detail card or the "Event not found" fallback
    // should render — both are valid Step 5 behaviors. Assert against
    // the back-link button which renders in both branches.
    const backLink = page.getByRole("button", { name: /back to calendar/i });
    await expect(backLink).toBeVisible({ timeout: 10_000 });
  });

  test("customer_pulse_events_endpoint_smoke", async ({ page }) => {
    await login(page);
    // Cross-tenant probe with a non-existent customer id should return
    // existence-hiding empty payload, NOT 404. Validates the canonical
    // probe-protection contract.
    const r = await authedFetch(
      page,
      "/api/v1/pulse/calendar-events-for-customer/00000000-0000-0000-0000-000000000000",
    );
    expect(r.status).toBe(200);
    const data = r.body as Record<string, unknown>;
    expect(data).toHaveProperty("customer_entity_id");
    expect(data).toHaveProperty("threads"); // common shape across email/calendar
    // ... fall-through check: if backend returns the canonical calendar
    // shape, customer_name is null + empty buckets
    if ("customer_name" in data) {
      expect(data.customer_name).toBeNull();
    }
  });

  test("event_linkages_endpoint_404_for_unknown_event", async ({ page }) => {
    await login(page);
    const r = await authedFetch(
      page,
      "/api/v1/calendar-events/00000000-0000-0000-0000-000000000000/linkages",
    );
    // Cross-tenant existence-hiding 404 — expected for unknown event id
    expect(r.status).toBe(404);
  });
});

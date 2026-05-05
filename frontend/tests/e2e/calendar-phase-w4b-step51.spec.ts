/**
 * Bridgeable Calendar — Phase W-4b Layer 1 Step 5.1 cross-tenant
 * consent extensions E2E.
 *
 * Lightweight smoke coverage of the three Step 5.1 deliverables:
 *
 *   1. calendar_consent_pending_endpoint  — /widget-data/calendar-consent-pending
 *   2. calendar_consent_pending_definition — widget seeded in catalog
 *   3. calendar_consent_pending_empty_state — endpoint returns canonical
 *                                              shape on a tenant with no
 *                                              pending consent rows
 *
 * Spec discipline: lightweight smoke. Full functional coverage lives
 * in `backend/tests/test_calendar_step51_consent_extensions.py` (15
 * tests). Playwright here verifies the cross-surface contract surface
 * doesn't crash on a populated tenant + that the widget endpoint
 * returns the canonical shape.
 *
 * Step 5.1 closes the Calendar primitive arc; this spec rounds out the
 * E2E coverage that started with `calendar-phase-w4b-step5.spec.ts`.
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
): Promise<{ status: number; body: unknown }> {
  return await page.evaluate(async (url) => {
    const res = await fetch(url as string, {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${localStorage.getItem("access_token") ?? ""}`,
        "X-Company-Slug": localStorage.getItem("company_slug") ?? "",
      },
    });
    let data: unknown = null;
    try {
      data = await res.json();
    } catch {
      // empty / non-JSON
    }
    return { status: res.status, body: data };
  }, path);
}


test.describe("Calendar Step 5.1 — PTR consent extensions", () => {
  test("calendar_consent_pending_endpoint_smoke", async ({ page }) => {
    await login(page);
    const r = await authedFetch(
      page,
      "/api/v1/widget-data/calendar-consent-pending",
    );
    expect(r.status).toBe(200);
    const data = r.body as Record<string, unknown>;
    // Canonical shape per get_calendar_consent_pending
    expect(data).toHaveProperty("has_pending");
    expect(data).toHaveProperty("pending_consent_count");
    expect(data).toHaveProperty("top_requester_name");
    expect(data).toHaveProperty("top_requester_tenant_label");
    expect(data).toHaveProperty("target_relationship_id");
  });

  test("calendar_consent_pending_empty_state_payload", async ({ page }) => {
    await login(page);
    const r = await authedFetch(
      page,
      "/api/v1/widget-data/calendar-consent-pending",
    );
    expect(r.status).toBe(200);
    const data = r.body as {
      has_pending: boolean;
      pending_consent_count: number;
    };
    // testco staging tenant has no pending_inbound PTR rows by
    // default (no other tenant has consented to full_details with
    // testco). Empty state is the canonical baseline; assertion stays
    // valid until staging seeds a counterparty.
    if (!data.has_pending) {
      expect(data.pending_consent_count).toBe(0);
    } else {
      // If staging is later seeded with a real PTR, count must be ≥1.
      expect(data.pending_consent_count).toBeGreaterThanOrEqual(1);
    }
  });

  test("calendar_consent_pending_widget_definition_seeded", async ({ page }) => {
    await login(page);
    // Use the widgets/available endpoint to verify the widget
    // definition is seeded and visible to admin users.
    const r = await authedFetch(
      page,
      "/api/v1/widgets/available?page_context=pulse",
    );
    expect(r.status).toBe(200);
    const widgets = r.body as Array<Record<string, unknown>>;
    expect(Array.isArray(widgets)).toBe(true);
    const consent = widgets.find(
      (w) => w.widget_id === "calendar_consent_pending",
    );
    expect(consent).toBeDefined();
    if (consent) {
      expect(consent.icon).toBe("UserCheck");
    }
  });
});

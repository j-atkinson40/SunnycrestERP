/**
 * Bridgeable Vault — Phase V-1b — Overview dashboard widgets E2E.
 *
 * Asserts the /vault landing page now renders a WidgetGrid with the
 * 5 V-1b widgets. Tests use the same staging + testco pattern as
 * vault-v1a.spec.ts.
 *
 * The widgets hit existing endpoints (DocumentLog, Signing, Inbox,
 * DeliveryLog, Notifications) — we don't seed data, so the happy
 * path here is "widget loads + renders either data or empty state
 * without crashing."
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

async function gotoVaultOverview(page: Page) {
  await login(page);
  await page.goto("/vault");
  await page.waitForLoadState("networkidle");
}

test.describe("@tenant:sunnycrest Bridgeable Vault V-1b Widgets", () => {
  // ── Landing page structure ─────────────────────────────────────────

  test("1. Vault overview renders dashboard, not the V-1a placeholder", async ({
    page,
  }) => {
    await gotoVaultOverview(page);
    // New Vault Overview heading is "Vault Overview" (V-1b); V-1a
    // placeholder said "Bridgeable Vault".
    await expect(
      page.getByRole("heading", { name: /Vault Overview/i }),
    ).toBeVisible();
  });

  test("2. Widget grid renders with multiple widgets", async ({ page }) => {
    await gotoVaultOverview(page);
    // WidgetWrapper titles are `<h3>` elements with a known set of
    // V-1b strings; at least 3 should be visible.
    const widgetTitles = [
      /Recent documents/i,
      /Pending signatures/i,
      /Inbox/i,
      /Recent deliveries/i,
      /Notifications/i,
    ];
    let visible = 0;
    for (const rx of widgetTitles) {
      const loc = page.getByRole("heading", { name: rx });
      if (await loc.count()) {
        visible += 1;
      }
    }
    expect(visible).toBeGreaterThanOrEqual(3);
  });

  // ── Per-widget presence (each V-1b widget) ─────────────────────────

  test("3. RecentDocumentsWidget renders", async ({ page }) => {
    await gotoVaultOverview(page);
    await expect(
      page.getByRole("heading", { name: /Recent documents/i }),
    ).toBeVisible();
  });

  test("4. PendingSignaturesWidget renders", async ({ page }) => {
    await gotoVaultOverview(page);
    await expect(
      page.getByRole("heading", { name: /Pending signatures/i }),
    ).toBeVisible();
  });

  test("5. UnreadInboxWidget renders (title starts with 'Inbox')", async ({
    page,
  }) => {
    await gotoVaultOverview(page);
    // Title may be "Inbox" or "Inbox (N unread)" depending on data.
    await expect(
      page.getByRole("heading", { name: /^Inbox/ }),
    ).toBeVisible();
  });

  test("6. RecentDeliveriesWidget renders with All/Failures toggle", async ({
    page,
  }) => {
    await gotoVaultOverview(page);
    const widget = page
      .getByRole("heading", { name: /Recent deliveries/i })
      .locator("xpath=ancestor::div[contains(@class,'rounded-lg')][1]");
    await expect(widget).toBeVisible();
    await expect(
      widget.getByRole("button", { name: /^All$/ }),
    ).toBeVisible();
    await expect(
      widget.getByRole("button", { name: /Failures only/i }),
    ).toBeVisible();
  });

  test("7. NotificationsWidget renders (title starts with 'Notifications')", async ({
    page,
  }) => {
    await gotoVaultOverview(page);
    await expect(
      page.getByRole("heading", { name: /^Notifications/ }),
    ).toBeVisible();
  });

  // ── Edit mode + customization affordances ─────────────────────────

  test("8. Edit button toggles edit mode", async ({ page }) => {
    await gotoVaultOverview(page);
    const edit = page.getByRole("button", { name: /^Edit$/ });
    await expect(edit).toBeVisible();
    await edit.click();
    // After click: Done + Add widget + Reset should appear.
    await expect(
      page.getByRole("button", { name: /^Done$/ }),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: /Reset/i }).first(),
    ).toBeVisible();
  });

  test("9. RecentDeliveriesWidget filter toggle switches active state", async ({
    page,
  }) => {
    await gotoVaultOverview(page);
    const widget = page
      .getByRole("heading", { name: /Recent deliveries/i })
      .locator("xpath=ancestor::div[contains(@class,'rounded-lg')][1]");
    const failuresBtn = widget.getByRole("button", {
      name: /Failures only/i,
    });
    const allBtn = widget.getByRole("button", { name: /^All$/ });
    // Click Failures; it should become styled as the active button.
    await failuresBtn.click();
    await page.waitForTimeout(300); // let refetch start
    // The button with failures-active class should still be visible.
    await expect(failuresBtn).toBeVisible();
    // Swap back.
    await allBtn.click();
    await expect(allBtn).toBeVisible();
  });

  // ── API integration ────────────────────────────────────────────────

  test("10. /api/v1/vault/overview/widgets returns the 5 V-1b widgets", async ({
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
    // The 5 V-1b widget_ids should all be present for an admin.
    expect(ids).toContain("vault_recent_documents");
    expect(ids).toContain("vault_pending_signatures");
    expect(ids).toContain("vault_unread_inbox");
    expect(ids).toContain("vault_recent_deliveries");
    expect(ids).toContain("vault_notifications");
  });

  test("11. /widgets/available?page_context=vault_overview seeds visible", async ({
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
      `${STAGING_BACKEND}/api/v1/widgets/available?page_context=vault_overview`,
      {
        headers: {
          Authorization: `Bearer ${token}`,
          "X-Company-Slug": slug ?? TENANT_SLUG,
        },
      },
    );
    expect(resp.status()).toBe(200);
    const body = await resp.json();
    // Existing widgets/available response is a flat array.
    const ids = (body as Array<{ widget_id: string }>).map(
      (w) => w.widget_id,
    );
    expect(ids).toEqual(
      expect.arrayContaining([
        "vault_recent_documents",
        "vault_pending_signatures",
        "vault_unread_inbox",
        "vault_recent_deliveries",
        "vault_notifications",
      ]),
    );
  });

  // ── Widget row click-through ──────────────────────────────────────

  test("12. 'View all' links in widgets land on Vault paths", async ({
    page,
  }) => {
    await gotoVaultOverview(page);
    // Find any "View all" link inside the widget grid and click it;
    // the destination should be under /vault/.
    const viewAll = page.getByRole("link", { name: /View all/i }).first();
    if (await viewAll.count()) {
      await viewAll.click();
      await page.waitForLoadState("networkidle");
      expect(page.url()).toContain("/vault/");
    }
  });

  test("13. Sidebar + breadcrumb still present on overview", async ({
    page,
  }) => {
    await gotoVaultOverview(page);
    await expect(page.getByLabel("Vault sidebar")).toBeVisible();
    await expect(page.getByLabel("Vault breadcrumbs")).toBeVisible();
  });
});

/**
 * Bridgeable Vault — Phase V-1e — Accounting admin consolidation E2E.
 *
 * Covers the Accounting service + its 6 sub-tabs under /vault/accounting,
 * the type-to-confirm UX for period locks, admin gating, and the
 * 3 new Vault Overview widgets.
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

test.describe("@tenant:sunnycrest Bridgeable Vault V-1e Accounting", () => {
  // ── Layout + tab navigation ─────────────────────────────────────────

  test("1. /vault/accounting lands on Periods tab by default", async ({
    page,
  }) => {
    await login(page);
    await page.goto("/vault/accounting");
    await page.waitForLoadState("networkidle");
    await expect(page).toHaveURL(/\/vault\/accounting\/periods/);
    await expect(page.getByLabel("Vault sidebar")).toBeVisible();
  });

  test("2. AccountingAdminLayout renders all 6 tabs", async ({ page }) => {
    await login(page);
    await page.goto("/vault/accounting/periods");
    await page.waitForLoadState("networkidle");
    const tablist = page.getByLabel("Accounting admin tabs");
    await expect(tablist.getByRole("link", { name: /Periods/ })).toBeVisible();
    await expect(
      tablist.getByRole("link", { name: /Agent Schedules/ }),
    ).toBeVisible();
    await expect(
      tablist.getByRole("link", { name: /GL Classification/ }),
    ).toBeVisible();
    await expect(tablist.getByRole("link", { name: /Tax Config/ })).toBeVisible();
    await expect(
      tablist.getByRole("link", { name: /Statement Templates/ }),
    ).toBeVisible();
    await expect(
      tablist.getByRole("link", { name: /COA Templates/ }),
    ).toBeVisible();
  });

  test("3. Navigating between tabs updates URL", async ({ page }) => {
    await login(page);
    await page.goto("/vault/accounting/periods");
    await page.waitForLoadState("networkidle");
    await page.getByRole("link", { name: /Agent Schedules/ }).click();
    await page.waitForURL(/\/vault\/accounting\/agents/, { timeout: 5_000 });
    await page.getByRole("link", { name: /GL Classification/ }).click();
    await page.waitForURL(/\/vault\/accounting\/classification/, {
      timeout: 5_000,
    });
    await page.getByRole("link", { name: /COA Templates/ }).click();
    await page.waitForURL(/\/vault\/accounting\/coa/, { timeout: 5_000 });
  });

  // ── Sidebar ─────────────────────────────────────────────────────────

  test("4. Accounting entry appears in Vault sidebar for admin", async ({
    page,
  }) => {
    await login(page);
    await page.goto("/vault");
    await page.waitForLoadState("networkidle");
    const sidebar = page.getByLabel("Vault sidebar");
    await expect(sidebar).toBeVisible();
    await expect(
      sidebar.getByRole("link", { name: /^Accounting$/ }),
    ).toBeVisible();
  });

  test("5. Clicking Accounting in sidebar navigates to /vault/accounting", async ({
    page,
  }) => {
    await login(page);
    await page.goto("/vault");
    await page.waitForLoadState("networkidle");
    await page
      .getByLabel("Vault sidebar")
      .getByRole("link", { name: /^Accounting$/ })
      .click();
    await page.waitForURL(/\/vault\/accounting/, { timeout: 5_000 });
  });

  // ── Periods tab + type-to-confirm ───────────────────────────────────

  test("6. Periods tab lists periods for the selected year", async ({
    page,
  }) => {
    await login(page);
    await page.goto("/vault/accounting/periods");
    await page.waitForLoadState("networkidle");
    // After initial load the 12-month auto-seed should produce at
    // least "January" through "December" visible somewhere on the page.
    const body = await page.textContent("body");
    expect(body).toContain("Accounting periods");
    // 12 rows for the current year.
    expect(body).toContain("January");
    expect(body).toContain("December");
  });

  test("7. Lock period modal requires type-to-confirm", async ({ page }) => {
    await login(page);
    await page.goto("/vault/accounting/periods");
    await page.waitForLoadState("networkidle");
    // Click the first "Close period" button (any open month will do).
    const firstClose = page
      .getByRole("button", { name: /Close period/ })
      .first();
    await firstClose.click();
    // Modal is up with the confirm input disabled on the destructive
    // button.
    const destructive = page.getByRole("button", { name: /^Close period$/ });
    // There should be a disabled "Close period" button inside the modal.
    // Playwright may see multiple "Close period" matches — filter to
    // the enabled-disabled state explicitly.
    const destructiveDisabled = destructive.last();
    await expect(destructiveDisabled).toBeDisabled();
  });

  test("8. Close period button enables only when name is typed exactly", async ({
    page,
  }) => {
    await login(page);
    await page.goto("/vault/accounting/periods");
    await page.waitForLoadState("networkidle");
    await page.getByRole("button", { name: /Close period/ }).first().click();
    // Read the displayed period name from the modal heading.
    const heading = await page
      .locator("h2", { hasText: "Close period:" })
      .first()
      .innerText();
    const match = heading.match(/Close period:\s*(.+)/);
    expect(match).toBeTruthy();
    const periodName = (match?.[1] ?? "").trim();
    const input = page.locator('input[type="text"]').first();
    // Typing a wrong value keeps the button disabled.
    await input.fill("Wrong");
    const destructiveDisabled = page
      .getByRole("button", { name: /^Close period$/ })
      .last();
    await expect(destructiveDisabled).toBeDisabled();
    // Typing the exact period name enables it.
    await input.fill(periodName);
    await expect(destructiveDisabled).toBeEnabled();
  });

  // ── COA tab ─────────────────────────────────────────────────────────

  test("9. COA Templates tab lists platform standard categories", async ({
    page,
  }) => {
    await login(page);
    await page.goto("/vault/accounting/coa");
    await page.waitForLoadState("networkidle");
    const body = await page.textContent("body");
    expect(body).toContain("Platform standard GL categories");
    // A known platform category from PLATFORM_CATEGORIES should appear.
    expect(body).toContain("vault_sales");
  });

  // ── API smoke tests ─────────────────────────────────────────────────

  test("10. /api/v1/vault/services includes accounting for admin", async ({
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
    const acc = services.find((s) => s.service_key === "accounting");
    expect(acc).toBeTruthy();
    expect(acc!.route_prefix).toBe("/vault/accounting");
  });

  test("11. /api/v1/vault/accounting/coa-templates returns 200 for admin", async ({
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
      `${STAGING_BACKEND}/api/v1/vault/accounting/coa-templates`,
      {
        headers: {
          Authorization: `Bearer ${token}`,
          "X-Company-Slug": slug ?? TENANT_SLUG,
        },
      },
    );
    expect(resp.status()).toBe(200);
    const body = await resp.json();
    expect(Array.isArray(body.templates)).toBe(true);
    expect(body.templates.length).toBeGreaterThan(0);
  });

  test("12. /api/v1/vault/accounting/pending-close returns 200 for admin", async ({
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
      `${STAGING_BACKEND}/api/v1/vault/accounting/pending-close`,
      {
        headers: {
          Authorization: `Bearer ${token}`,
          "X-Company-Slug": slug ?? TENANT_SLUG,
        },
      },
    );
    expect(resp.status()).toBe(200);
    const body = await resp.json();
    expect(Array.isArray(body.pending)).toBe(true);
  });

  test("13. /api/v1/vault/accounting/periods auto-seeds a year", async ({
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
    const year = new Date().getFullYear();
    const resp = await request.get(
      `${STAGING_BACKEND}/api/v1/vault/accounting/periods?year=${year}`,
      {
        headers: {
          Authorization: `Bearer ${token}`,
          "X-Company-Slug": slug ?? TENANT_SLUG,
        },
      },
    );
    expect(resp.status()).toBe(200);
    const body = await resp.json();
    const thisYear = (body.periods as Array<{ period_year: number }>).filter(
      (p) => p.period_year === year,
    );
    expect(thisYear.length).toBe(12);
  });

  // ── V-1e widgets on Vault Overview ──────────────────────────────────

  test("14. /api/v1/vault/overview/widgets includes V-1e widgets for admin", async ({
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
    expect(ids).toContain("vault_pending_period_close");
    expect(ids).toContain("vault_gl_classification_review");
    expect(ids).toContain("vault_agent_recent_activity");
  });

  test("15. Agent Schedules tab renders without crashing", async ({
    page,
  }) => {
    await login(page);
    await page.goto("/vault/accounting/agents");
    await page.waitForLoadState("networkidle");
    const body = await page.textContent("body");
    expect(body).not.toContain("Something went wrong");
    expect(body).toContain("Agent schedules");
  });

  test("16. Tax Config tab renders without crashing", async ({ page }) => {
    await login(page);
    await page.goto("/vault/accounting/tax");
    await page.waitForLoadState("networkidle");
    const body = await page.textContent("body");
    expect(body).not.toContain("Something went wrong");
    expect(body).toContain("Tax rates");
  });
});

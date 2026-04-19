/**
 * Shared auth + routing setup for Intelligence admin E2E tests.
 *
 * Mirrors the pattern from tests/e2e/smoke.spec.ts — intercepts prod API
 * calls to the staging backend, seeds tenant slug, and logs in as admin.
 *
 * All tests in this folder target staging (see playwright.config.ts).
 * Staging must have Phase 3b + 3c deployed for tests to pass.
 */
import type { Page } from "@playwright/test";

const STAGING_BACKEND =
  process.env.BACKEND_URL ||
  "https://sunnycresterp-staging.up.railway.app";
const PROD_API = "https://api.getbridgeable.com";
const TENANT_SLUG = "testco";

const ADMIN_CREDS = {
  email: "admin@testco.com",
  password: "TestAdmin123!",
};

export async function setupPage(page: Page): Promise<void> {
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

export async function loginAsAdmin(page: Page): Promise<void> {
  await setupPage(page);

  await page.goto("/login");
  await page.waitForLoadState("networkidle");

  const identifier = page.locator("#identifier");
  await identifier.waitFor({ state: "visible", timeout: 10_000 });
  await identifier.fill(ADMIN_CREDS.email);
  await page.waitForTimeout(300);

  const password = page.locator("#password");
  await password.waitFor({ state: "visible", timeout: 5_000 });
  await password.fill(ADMIN_CREDS.password);

  await page.getByRole("button", { name: /sign\s*in/i }).click();
  await page.waitForURL((url) => !url.pathname.includes("/login"), {
    timeout: 20_000,
  });
}

/** Convenience — log in + land on the prompts library. */
export async function openPromptLibrary(page: Page): Promise<void> {
  await loginAsAdmin(page);
  await page.goto("/admin/intelligence/prompts");
  await page.waitForLoadState("networkidle");
}

/** Convenience — log in + land on the executions log. */
export async function openExecutionLog(page: Page): Promise<void> {
  await loginAsAdmin(page);
  await page.goto("/admin/intelligence/executions");
  await page.waitForLoadState("networkidle");
}

/** Convenience — log in + land on experiments library. */
export async function openExperimentLibrary(page: Page): Promise<void> {
  await loginAsAdmin(page);
  await page.goto("/admin/intelligence/experiments");
  await page.waitForLoadState("networkidle");
}

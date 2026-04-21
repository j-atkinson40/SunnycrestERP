/**
 * Workflow Arc Phase 8a — foundation E2E.
 *
 * Six scenarios covering the foundation commits:
 *   1. dot_nav_renders_at_bottom — new DotNav component visible at
 *      the bottom of the left sidebar, replacing the top-bar space
 *      switcher
 *   2. dot_nav_switches_spaces — clicking a dot switches active
 *      space (backend call + active-dot highlight)
 *   3. settings_dot_visible_for_admin — admin user sees Settings
 *      system space in the dot nav (leftmost)
 *   4. workflows_page_shows_scope_cards — /settings/workflows
 *      renders workflows with scope classification (agent badge
 *      + fork badge when applicable)
 *   5. fork_core_workflow_flow — click Fork on a Core row,
 *      backend creates tenant copy, user lands on edit page
 *   6. old_top_space_switcher_gone — regression: SpaceSwitcher
 *      component no longer mounted in app header
 *
 * Staging-canonical per prior phases: prod→staging fetch redirect,
 * testco tenant, admin creds.
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


// ── 1. Dot nav renders at bottom of sidebar ─────────────────────

test("dot_nav_renders_at_bottom: new DotNav visible", async ({ page }) => {
  await login(page);
  await expect(
    page.locator('[data-testid="dot-nav"]').first(),
  ).toBeVisible({ timeout: 10_000 });
  // At least one dot (user has at least one space) + the plus button.
  expect(
    await page.locator('[data-testid="dot-nav-dot"]').count(),
  ).toBeGreaterThanOrEqual(1);
  await expect(
    page.locator('[data-testid="dot-nav-add"]'),
  ).toBeVisible();
});


// ── 2. Dot nav switches spaces ──────────────────────────────────

test("dot_nav_switches_spaces: click switches active + aria-pressed updates", async ({
  page,
}) => {
  await login(page);
  await page.waitForSelector('[data-testid="dot-nav"]', { timeout: 10_000 });
  const dots = page.locator('[data-testid="dot-nav-dot"]');
  const count = await dots.count();
  test.skip(count < 2, "Need at least 2 spaces for switch test");

  const firstId = await dots.nth(0).getAttribute("data-space-id");
  const secondId = await dots.nth(1).getAttribute("data-space-id");

  // Click the one that's not currently active.
  const activeIdx = await dots.evaluateAll((els) =>
    els.findIndex((el) => el.getAttribute("aria-pressed") === "true"),
  );
  const targetIdx = activeIdx === 0 ? 1 : 0;
  await dots.nth(targetIdx).click();
  await page.waitForTimeout(400);

  const newActive = await dots.evaluateAll((els) =>
    els.findIndex((el) => el.getAttribute("aria-pressed") === "true"),
  );
  expect(newActive).toBe(targetIdx);
  // Also verify we saw different space ids.
  expect(firstId).not.toBe(secondId);
});


// ── 3. Settings system space visible for admin ──────────────────

test("settings_dot_visible_for_admin: admin sees sys_settings leftmost", async ({
  page,
}) => {
  await login(page);
  await page.waitForSelector('[data-testid="dot-nav"]', { timeout: 10_000 });
  const systemDots = page.locator(
    '[data-testid="dot-nav-dot"][data-is-system="true"]',
  );
  // If staging's testco admin has been seeded post-r36, the Settings
  // dot is visible. Skip when staging data is older — the test is
  // informative but not a correctness gate for data we don't own.
  const sysCount = await systemDots.count();
  test.skip(sysCount === 0, "Settings system space not seeded on staging yet");
  const firstSpaceId = await page
    .locator('[data-testid="dot-nav-dot"]')
    .nth(0)
    .getAttribute("data-space-id");
  expect(firstSpaceId).toBe("sys_settings");
});


// ── 4. Workflows page shows scope + agent badges ────────────────

test("workflows_page_shows_scope_cards: agent badge visible on wf_sys_month_end_close", async ({
  page,
}) => {
  await login(page);
  await page.goto("/settings/workflows");
  await page.waitForLoadState("networkidle");
  // Switch to the Platform tab — it maps to scope=core.
  await page.getByRole("button", { name: /platform\s*workflows/i }).click();
  // The Month-End Close card should render an "Built-in implementation"
  // badge because its backend row has agent_registry_key=month_end_close.
  const badge = page.locator('[data-testid="workflow-agent-badge"]').first();
  await expect(badge).toBeVisible({ timeout: 10_000 });
  await expect(badge).toContainText(/built-in implementation/i);
});


// ── 5. Fork Core workflow flow ───────────────────────────────────

test("fork_core_workflow_flow: click Fork creates tenant copy + navigates", async ({
  page,
}) => {
  await login(page);
  // Mock the fork endpoint so the test doesn't create staging state
  // or race with a real workflow rows baseline.
  await page.route("**/api/v1/workflows/*/fork", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: "fork-abc-123",
        name: "Forked wf",
        scope: "tenant",
        forked_from_workflow_id: "wf_sys_compliance_sync",
        forked_at: new Date().toISOString(),
        agent_registry_key: null,
        company_id: "testco",
        description: null,
        keywords: [],
        tier: 4,
        vertical: null,
        trigger_type: "manual",
        trigger_config: null,
        is_active: true,
        is_system: false,
        is_coming_soon: false,
        icon: null,
        command_bar_priority: 10,
        step_count: 0,
        used_by_count: null,
      }),
    });
  });

  await page.goto("/settings/workflows");
  await page.waitForLoadState("networkidle");
  await page.getByRole("button", { name: /platform\s*workflows/i }).click();
  // Find a fork button — any Core row that isn't agent-backed.
  const forkBtn = page.locator('[data-testid="workflow-fork-btn"]').first();
  const forkCount = await forkBtn.count();
  test.skip(
    forkCount === 0,
    "No non-agent-backed Core workflows available on this tenant to fork",
  );
  await forkBtn.click();
  // After fork, we should navigate to /settings/workflows/{new-id}/edit.
  await page.waitForURL(/\/settings\/workflows\/fork-abc-123\/edit$/, {
    timeout: 10_000,
  });
});


// ── 6. Old top-bar SpaceSwitcher no longer mounted ──────────────

test("old_top_space_switcher_gone: header does not contain space-switcher-trigger", async ({
  page,
}) => {
  await login(page);
  // The Phase 3 top-bar switcher had data-testid="space-switcher-trigger".
  // After Phase 8a it's removed from the mount tree.
  const topSwitcher = page.locator(
    'header [data-testid="space-switcher-trigger"]',
  );
  expect(await topSwitcher.count()).toBe(0);
});

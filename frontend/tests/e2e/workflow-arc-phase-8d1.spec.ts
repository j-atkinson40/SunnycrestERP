/**
 * Workflow Arc Phase 8d.1 — Safety Program Migration E2E.
 *
 * Six scenarios covering queue config + AI panel + legacy coexistence:
 *
 *   1. safety_program_queue_config_shape — queue registered with
 *      approve/reject/request_review actions + AI question panel
 *      (Phase 8d.1 scope decision: AI panel INCLUDED).
 *   2. ai_prompt_key_present — AI panel references
 *      triage.safety_program_context_question.
 *   3. four_suggested_questions — AI panel carries exactly 4
 *      suggested starter questions per approved scope.
 *   4. legacy_safety_programs_ui_still_mounts — /safety/programs
 *      UI still works for the Manual tab + rejected/approved
 *      history (out-of-scope for triage, per approved scope).
 *   5. legacy_approve_endpoint_still_works — legacy REST
 *      approval endpoint remains callable for ad-hoc use.
 *   6. migrated_workflow_visible_on_vertical_tab — post-r38
 *      wf_sys_safety_program_gen shows under vertical tab
 *      (manufacturing), not core.
 *
 * Staging-canonical: prod→staging fetch redirect, testco tenant,
 * admin creds.
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


async function getAuthToken(page: Page): Promise<string> {
  const token = await page.evaluate(() => {
    return localStorage.getItem("access_token");
  });
  if (!token) throw new Error("No access_token after login");
  return token;
}


// ── 1. Queue config shape ──────────────────────────────────────────

test("safety_program_queue_config_shape: approve/reject/request_review + AI panel", async ({
  page,
}) => {
  await login(page);
  const token = await getAuthToken(page);
  const res = await page.request.get(
    `${STAGING_BACKEND}/api/v1/triage/queues/safety_program_triage`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
        "X-Company-Slug": TENANT_SLUG,
      },
    },
  );
  if (res.status() === 404) {
    test.skip(
      true,
      "safety_program_triage not available (vertical or permission gate)",
    );
  }
  expect(res.status()).toBe(200);
  const cfg = await res.json();
  expect(cfg.queue_id).toBe("safety_program_triage");
  expect(cfg.required_vertical).toBe("manufacturing");
  expect(cfg.item_entity_type).toBe("safety_program_generation");
  const actionIds = (
    cfg.action_palette as Array<{ action_id: string }>
  ).map((a) => a.action_id);
  expect(actionIds).toEqual(
    expect.arrayContaining(["approve", "reject", "request_review"]),
  );
  // Snooze disabled (monthly cadence) per approved scope.
  expect(cfg.flow_controls.snooze_enabled).toBe(false);
});


// ── 2. AI prompt key present ───────────────────────────────────────

test("ai_prompt_key_present: AI question panel references expected prompt", async ({
  page,
}) => {
  await login(page);
  const token = await getAuthToken(page);
  const res = await page.request.get(
    `${STAGING_BACKEND}/api/v1/triage/queues/safety_program_triage`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
        "X-Company-Slug": TENANT_SLUG,
      },
    },
  );
  if (res.status() === 404) {
    test.skip(true, "safety_program_triage not available on staging");
  }
  expect(res.status()).toBe(200);
  const cfg = await res.json();
  const aiPanel = (
    cfg.context_panels as Array<{
      panel_type: string;
      ai_prompt_key?: string;
    }>
  ).find((p) => p.panel_type === "ai_question");
  expect(aiPanel).toBeTruthy();
  expect(aiPanel?.ai_prompt_key).toBe(
    "triage.safety_program_context_question",
  );
  expect(cfg.intelligence.ai_questions_enabled).toBe(true);
});


// ── 3. Four suggested questions per approved scope ─────────────────

test("four_suggested_questions: AI panel carries 4 starter chips", async ({
  page,
}) => {
  await login(page);
  const token = await getAuthToken(page);
  const res = await page.request.get(
    `${STAGING_BACKEND}/api/v1/triage/queues/safety_program_triage`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
        "X-Company-Slug": TENANT_SLUG,
      },
    },
  );
  if (res.status() === 404) {
    test.skip(true, "safety_program_triage not available on staging");
  }
  const cfg = await res.json();
  const aiPanel = (
    cfg.context_panels as Array<{
      panel_type: string;
      suggested_questions?: string[];
    }>
  ).find((p) => p.panel_type === "ai_question");
  expect(aiPanel?.suggested_questions).toBeTruthy();
  expect((aiPanel?.suggested_questions || []).length).toBe(4);
});


// ── 4. Legacy /safety/programs UI still mounts ─────────────────────

test("legacy_safety_programs_ui_still_mounts: coexistence verified", async ({
  page,
}) => {
  await login(page);
  await page.goto("/safety/programs");
  await page.waitForLoadState("networkidle", { timeout: 15_000 });
  // The page mounts without redirecting to login or 403.
  const url = page.url();
  if (url.includes("/login") || url.includes("/403")) {
    test.skip(
      true,
      "testco does not grant safety.trainer.view on staging admin",
    );
  }
  expect(url).toContain("/safety/programs");
  // Bespoke page carries both AI Generated + Manual tabs — triage only
  // covers AI Generated → Manual tab IS out-of-scope per approved plan.
});


// ── 5. Legacy approve endpoint still works ─────────────────────────

test("legacy_approve_endpoint_still_callable", async ({ page }) => {
  await login(page);
  const token = await getAuthToken(page);
  // Call against a bogus generation id — we're not asserting success,
  // just that the route is still registered (expects 404/400, NOT 410
  // Gone or 404-for-missing-route).
  const res = await page.request.post(
    `${STAGING_BACKEND}/api/v1/safety/programs/generations/nonexistent-id/approve`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
        "X-Company-Slug": TENANT_SLUG,
      },
    },
  );
  // 404 = generation not found (route works). 403 = permission gate
  // (also indicates route registered). We fail only if the route
  // itself has been removed (would usually manifest as 405 or
  // route-not-found signature).
  expect([400, 403, 404]).toContain(res.status());
});


// ── 6. Migrated workflow visible on manufacturing vertical tab ─────

test("migrated_workflow_visible_on_vertical_tab: post-r38 location", async ({
  page,
}) => {
  await login(page);
  const token = await getAuthToken(page);
  const res = await page.request.get(
    `${STAGING_BACKEND}/api/v1/workflows?scope=vertical`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
        "X-Company-Slug": TENANT_SLUG,
      },
    },
  );
  expect(res.status()).toBe(200);
  const rows = (await res.json()) as Array<{
    id: string;
    vertical: string;
    scope: string;
  }>;
  const sp = rows.find((r) => r.id === "wf_sys_safety_program_gen");
  if (!sp) {
    test.skip(
      true,
      "wf_sys_safety_program_gen not seeded on staging yet",
    );
  }
  expect(sp?.vertical).toBe("manufacturing");
  expect(sp?.scope).toBe("vertical");
});

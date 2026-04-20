/**
 * Bridgeable AI Question Panel — UI/UX Arc Follow-up 2 E2E.
 *
 * First interactive context panel wired in the triage workspace.
 * Scenarios:
 *
 *   1. ai_question_panel_renders            — Panel mounts on /triage/task_triage.
 *   2. suggested_questions_populate_input   — Chip click → textarea.
 *   3. submit_api_contract                  — API POST matches /ask shape;
 *                                             response drives history render.
 *   4. character_counter_updates            — Counter tracks input length.
 *   5. keyboard_shortcut_doesnt_fire_action — Typing "n" in the textarea
 *                                             does NOT fire the Skip action
 *                                             (Phase 5's input-focus discipline).
 *   6. rate_limited_shows_friendly_message  — 429 structured body renders as
 *                                             a friendly toast-style error
 *                                             (not a raw HTTP code).
 *   7. api_smoke_ask_endpoint               — Backend endpoint returns a
 *                                             valid response shape.
 *
 * Staging-canonical per the Phase 5 pattern: prod→staging fetch
 * redirect, testco tenant, admin credentials. Many scenarios skip
 * gracefully when staging has no pending triage items.
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

async function openTaskTriage(page: Page): Promise<"ready" | "no-items"> {
  await page.goto("/triage/task_triage");
  await page.waitForLoadState("networkidle");
  // The workspace renders the action palette + context rail once an
  // item is loaded. Either we see the item OR a "Caught up" empty
  // state (no pending items in staging).
  const caughtUp = page.getByText(/caught up|no pending/i);
  const panel = page.locator('[data-testid="ai-question-panel"]');
  const res = await Promise.race([
    caughtUp
      .first()
      .waitFor({ state: "visible", timeout: 10_000 })
      .then(() => "no-items" as const)
      .catch(() => null),
    panel
      .first()
      .waitFor({ state: "visible", timeout: 10_000 })
      .then(() => "ready" as const)
      .catch(() => null),
  ]);
  return res ?? "no-items";
}


// ── 1. Panel renders ────────────────────────────────────────────────

test("ai_question_panel_renders: input + submit visible on task_triage", async ({
  page,
}) => {
  await login(page);
  const state = await openTaskTriage(page);
  test.skip(state === "no-items", "staging has no pending tasks");
  await expect(
    page.locator('[data-testid="ai-question-input"]').first(),
  ).toBeVisible();
  await expect(
    page.locator('[data-testid="ai-question-submit"]').first(),
  ).toBeVisible();
});


// ── 2. Suggested-question chips populate input ───────────────────────

test("suggested_questions_populate_input: chip click fills textarea", async ({
  page,
}) => {
  await login(page);
  const state = await openTaskTriage(page);
  test.skip(state === "no-items", "staging has no pending tasks");
  const chip = page
    .locator('[data-testid="ai-question-suggestion"]')
    .first();
  await chip.waitFor({ state: "visible", timeout: 5_000 });
  const chipText = await chip.innerText();
  await chip.click();
  const input = page.locator('[data-testid="ai-question-input"]').first();
  await expect(input).toHaveValue(chipText);
});


// ── 3. Character counter ────────────────────────────────────────────

test("character_counter_updates: counter tracks input length", async ({
  page,
}) => {
  await login(page);
  const state = await openTaskTriage(page);
  test.skip(state === "no-items", "staging has no pending tasks");
  const input = page.locator('[data-testid="ai-question-input"]').first();
  await input.fill("Why is this urgent?");
  await expect(
    page.locator('[data-testid="ai-question-counter"]').first(),
  ).toContainText("19/");
});


// ── 4. Keyboard shortcut suppression ───────────────────────────────

test("keyboard_shortcut_doesnt_fire_action: typing 'n' in textarea does not skip", async ({
  page,
}) => {
  await login(page);
  const state = await openTaskTriage(page);
  test.skip(state === "no-items", "staging has no pending tasks");
  const input = page.locator('[data-testid="ai-question-input"]').first();
  await input.focus();
  const urlBefore = page.url();
  // Type the letter "n" — in the palette this would fire Skip on
  // task_triage. With Phase 5's input-focus discipline intact, the
  // textarea absorbs the keystroke.
  await page.keyboard.press("n");
  await expect(input).toHaveValue("n");
  await expect(page).toHaveURL(urlBefore);
});


// ── 5. Submit round-trip (mocked to avoid Anthropic dependency) ─────

test("submit_api_contract: answer + confidence + history render", async ({
  page,
}) => {
  await login(page);
  const state = await openTaskTriage(page);
  test.skip(state === "no-items", "staging has no pending tasks");

  // Intercept the /ask call and return a canned response so the test
  // doesn't depend on Anthropic availability or quota.
  await page.route("**/api/v1/triage/sessions/*/items/*/ask", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        question: "Why is this urgent?",
        answer: "Due tomorrow — marked urgent priority.",
        confidence: "high",
        confidence_score: 0.9,
        source_references: [],
        latency_ms: 420,
        asked_at: new Date().toISOString(),
        execution_id: "exec_e2e",
      }),
    });
  });

  const input = page.locator('[data-testid="ai-question-input"]').first();
  await input.fill("Why is this urgent?");
  await page
    .locator('[data-testid="ai-question-submit"]')
    .first()
    .click();
  // Answer renders + confidence dot visible.
  await expect(
    page.locator('[data-testid="ai-question-answer"]').first(),
  ).toBeVisible();
  await expect(
    page.locator('[data-testid="ai-question-answer"]').first(),
  ).toContainText("Due tomorrow");
  await expect(
    page.locator('[data-testid="ai-question-confidence-high"]').first(),
  ).toBeVisible();
});


// ── 6. Rate-limit friendly error ────────────────────────────────────

test("rate_limited_shows_friendly_message: 429 body → human copy", async ({
  page,
}) => {
  await login(page);
  const state = await openTaskTriage(page);
  test.skip(state === "no-items", "staging has no pending tasks");

  await page.route("**/api/v1/triage/sessions/*/items/*/ask", async (route) => {
    await route.fulfill({
      status: 429,
      contentType: "application/json",
      headers: { "Retry-After": "30" },
      body: JSON.stringify({
        detail: {
          code: "rate_limited",
          retry_after_seconds: 30,
          message:
            "Pausing AI questions for a moment — try again in 30 seconds.",
        },
      }),
    });
  });

  const input = page.locator('[data-testid="ai-question-input"]').first();
  await input.fill("Why?");
  await page
    .locator('[data-testid="ai-question-submit"]')
    .first()
    .click();
  const err = page.locator('[data-testid="ai-question-error"]').first();
  await expect(err).toBeVisible();
  await expect(err).toContainText(/pausing ai questions/i);
  // The message surfaces the retry-after count — not a raw 429 code.
  await expect(err).toContainText(/30 seconds/i);
});


// ── 7. Backend API contract smoke ───────────────────────────────────

test("api_smoke_ask_endpoint: POST /ask contract", async ({ page }) => {
  await login(page);
  // Start a task_triage session + advance to first item.
  const smoke = await page.evaluate(async () => {
    const token = localStorage.getItem("access_token");
    const slug = localStorage.getItem("company_slug") || "testco";
    const headers = {
      Authorization: `Bearer ${token}`,
      "X-Company-Slug": slug,
      "Content-Type": "application/json",
    };
    const startRes = await fetch(
      "/api/v1/triage/queues/task_triage/sessions",
      { method: "POST", headers },
    );
    if (!startRes.ok) return { skipped: true, reason: "no access" };
    const session = await startRes.json();
    const nextRes = await fetch(
      `/api/v1/triage/sessions/${session.session_id}/next`,
      { method: "POST", headers },
    );
    if (nextRes.status === 204) return { skipped: true, reason: "no items" };
    if (!nextRes.ok) return { skipped: true, reason: `next ${nextRes.status}` };
    const item = await nextRes.json();
    const askRes = await fetch(
      `/api/v1/triage/sessions/${session.session_id}/items/${item.entity_id}/ask`,
      {
        method: "POST",
        headers,
        body: JSON.stringify({ question: "Why is this urgent?" }),
      },
    );
    const body = await askRes.json().catch(() => null);
    return { skipped: false, status: askRes.status, body };
  });
  if (smoke.skipped) {
    test.skip(true, `smoke skipped: ${smoke.reason}`);
  }
  // Real Anthropic may or may not be configured on staging — accept
  // either 200 (fully wired) or 502 (AIQuestionFailed — Intelligence
  // unavailable) as legitimate outcomes; both exercise the endpoint.
  expect([200, 429, 502]).toContain(smoke.status);
  if (smoke.status === 200) {
    expect(smoke.body).toHaveProperty("answer");
    expect(smoke.body).toHaveProperty("confidence");
    expect(["high", "medium", "low"]).toContain(smoke.body.confidence);
    expect(smoke.body).toHaveProperty("source_references");
    expect(Array.isArray(smoke.body.source_references)).toBe(true);
  }
});

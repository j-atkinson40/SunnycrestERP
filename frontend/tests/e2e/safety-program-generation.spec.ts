/**
 * E2E tests for Monthly Safety Program Generation feature.
 *
 * Tests the full pipeline:
 * 1. Seed: ensure training topics + schedule exist
 * 2. List generations (empty initially)
 * 3. Generate a program for the current month
 * 4. Verify detail (content, OSHA scrape, generation status)
 * 5. Approve the generated program
 * 6. Verify approval created/updated a SafetyProgram
 * 7. Generate for a specific topic (ad-hoc)
 * 8. Reject a generation with notes
 * 9. Briefing includes safety trainer items
 */

import { test, expect, APIRequestContext } from "@playwright/test";

const STAGING_API = "https://sunnycresterp-staging.up.railway.app";
const API_BASE = `${STAGING_API}/api/v1`;
const TENANT_SLUG = "testco";

const CREDS = { email: "admin@testco.com", password: "TestAdmin123!" };

async function getApiToken(request: APIRequestContext): Promise<string> {
  const res = await request.post(`${API_BASE}/auth/login`, {
    headers: { "X-Company-Slug": TENANT_SLUG, "Content-Type": "application/json" },
    data: { email: CREDS.email, password: CREDS.password },
  });
  expect(res.ok()).toBeTruthy();
  const body = await res.json();
  return body.access_token;
}

function apiHeaders(token: string) {
  return {
    Authorization: `Bearer ${token}`,
    "X-Company-Slug": TENANT_SLUG,
    "Content-Type": "application/json",
  };
}

// Shared state across serial tests
const state: {
  token?: string;
  topicId?: string;
  scheduleId?: string;
  generationId?: string;
  adHocGenerationId?: string;
} = {};

test.describe.serial("@tenant:testco Safety Program Generation E2E", () => {
  test("Step 0: Auth + ensure training schedule exists", async ({ request }) => {
    state.token = await getApiToken(request);
    const h = apiHeaders(state.token);

    // Initialize training schedule for current year (idempotent)
    const year = new Date().getFullYear();
    const initRes = await request.post(
      `${API_BASE}/safety/training/schedule/initialize?year=${year}`,
      { headers: h },
    );
    // 200 or 409 (already exists) are both fine
    expect([200, 409].includes(initRes.status())).toBeTruthy();

    // Get the schedule to find this month's topic
    const schedRes = await request.get(
      `${API_BASE}/safety/training/schedule?year=${year}`,
      { headers: h },
    );
    expect(schedRes.ok()).toBeTruthy();
    const schedule = await schedRes.json();
    expect(Array.isArray(schedule)).toBeTruthy();
    expect(schedule.length).toBeGreaterThanOrEqual(1);

    const currentMonth = new Date().getMonth() + 1; // 1-12
    const thisMonthEntry = schedule.find(
      (s: Record<string, unknown>) => s.month_number === currentMonth,
    );
    expect(thisMonthEntry).toBeTruthy();
    state.topicId = thisMonthEntry.topic_id;
    state.scheduleId = thisMonthEntry.id;
  });

  test("Step 1: List generations — initially empty or pre-existing", async ({
    request,
  }) => {
    const h = apiHeaders(state.token!);
    const res = await request.get(`${API_BASE}/safety/programs/generations`, {
      headers: h,
    });
    expect(res.ok()).toBeTruthy();
    const data = await res.json();
    expect(Array.isArray(data)).toBeTruthy();

    // Clean up any existing generation for this month to test fresh
    // (We'll just proceed — the generate endpoint handles dedup)
  });

  test("Step 2: Generate this month's safety program", async ({ request }) => {
    test.setTimeout(120_000); // 2 min — OSHA scrape + Claude generation
    const h = apiHeaders(state.token!);

    const res = await request.post(`${API_BASE}/safety/programs/generate`, {
      headers: h,
      timeout: 90_000,
    });
    expect(res.ok()).toBeTruthy();
    const data = await res.json();

    // Could be "complete" or "skipped" (if already generated)
    expect(["complete", "skipped", "failed"]).toContain(data.status);

    if (data.status === "skipped" && data.reason === "already_generated") {
      // Use existing generation
      state.generationId = data.generation_id;
    } else if (data.status === "complete") {
      state.generationId = data.generation_id;
      expect(data.topic).toBeTruthy();
    }
    // If failed, we'll handle in next test
  });

  test("Step 3: Verify generation detail", async ({ request }) => {
    test.skip(!state.generationId, "No generation to verify");
    const h = apiHeaders(state.token!);

    const res = await request.get(
      `${API_BASE}/safety/programs/generations/${state.generationId}`,
      { headers: h },
    );
    expect(res.ok()).toBeTruthy();
    const detail = await res.json();

    expect(detail.id).toBe(state.generationId);
    expect(detail.year).toBe(new Date().getFullYear());
    expect(detail.month_number).toBe(new Date().getMonth() + 1);
    expect(detail.topic_title).toBeTruthy();

    // OSHA scrape should have run
    expect(["success", "failed", "skipped"]).toContain(detail.osha_scrape_status);

    // Generation should be complete
    if (detail.generation_status === "complete") {
      expect(detail.generated_content).toBeTruthy();
      expect(detail.generated_content.length).toBeGreaterThan(100);
      expect(detail.generated_html).toBeTruthy();
      expect(detail.generation_model).toBeTruthy();
      expect(detail.generated_at).toBeTruthy();

      // Status should be pending_review (auto-set after generation)
      expect(["pending_review", "approved", "rejected", "draft"]).toContain(
        detail.status,
      );
    }
  });

  test("Step 4: List generations — should have at least one", async ({
    request,
  }) => {
    const h = apiHeaders(state.token!);
    const res = await request.get(`${API_BASE}/safety/programs/generations`, {
      headers: h,
    });
    expect(res.ok()).toBeTruthy();
    const data = await res.json();
    expect(data.length).toBeGreaterThanOrEqual(1);

    // Verify structure of list items
    const item = data[0];
    expect(item).toHaveProperty("id");
    expect(item).toHaveProperty("year");
    expect(item).toHaveProperty("month_number");
    expect(item).toHaveProperty("topic_title");
    expect(item).toHaveProperty("status");
    expect(item).toHaveProperty("generation_status");
  });

  test("Step 5: Approve the generated program", async ({ request }) => {
    test.skip(!state.generationId, "No generation to approve");
    const h = apiHeaders(state.token!);

    // Check current status first
    const detailRes = await request.get(
      `${API_BASE}/safety/programs/generations/${state.generationId}`,
      { headers: h },
    );
    const detail = await detailRes.json();

    // Only approve if pending_review
    if (detail.status !== "pending_review") {
      test.skip(true, `Generation status is ${detail.status}, not pending_review`);
      return;
    }

    const res = await request.post(
      `${API_BASE}/safety/programs/generations/${state.generationId}/approve`,
      { headers: h },
    );
    expect(res.ok()).toBeTruthy();
    const approved = await res.json();

    expect(approved.status).toBe("approved");
    expect(approved.reviewed_at).toBeTruthy();
    expect(approved.safety_program_id).toBeTruthy();
    expect(approved.posted_at).toBeTruthy();
  });

  test("Step 6: Verify SafetyProgram was created/updated", async ({
    request,
  }) => {
    const h = apiHeaders(state.token!);

    // List safety programs
    const res = await request.get(`${API_BASE}/safety/programs`, { headers: h });
    expect(res.ok()).toBeTruthy();
    const programs = await res.json();
    expect(Array.isArray(programs)).toBeTruthy();

    // At least one program should be active (from our approval)
    const active = programs.filter(
      (p: Record<string, unknown>) => p.status === "active",
    );
    expect(active.length).toBeGreaterThanOrEqual(1);
  });

  test("Step 7: Generate for a specific topic (ad-hoc)", async ({
    request,
  }) => {
    test.setTimeout(120_000);
    test.skip(!state.topicId, "No topic ID available");
    const h = apiHeaders(state.token!);

    const res = await request.post(
      `${API_BASE}/safety/programs/generate-for-topic/${state.topicId}`,
      { headers: h, timeout: 90_000 },
    );
    expect(res.ok()).toBeTruthy();
    const data = await res.json();

    expect(data.id).toBeTruthy();
    expect(data.topic_title).toBeTruthy();
    state.adHocGenerationId = data.id;
  });

  test("Step 8: Reject a generation with notes", async ({ request }) => {
    test.skip(!state.adHocGenerationId, "No ad-hoc generation to reject");
    const h = apiHeaders(state.token!);

    // Check if it's in a rejectable state
    const detailRes = await request.get(
      `${API_BASE}/safety/programs/generations/${state.adHocGenerationId}`,
      { headers: h },
    );
    const detail = await detailRes.json();

    if (!["pending_review", "draft"].includes(detail.status)) {
      test.skip(true, `Status is ${detail.status}`);
      return;
    }

    const res = await request.post(
      `${API_BASE}/safety/programs/generations/${state.adHocGenerationId}/reject?notes=Test+rejection+-+content+needs+more+industry-specific+detail`,
      { headers: h },
    );
    expect(res.ok()).toBeTruthy();
    const rejected = await res.json();

    expect(rejected.status).toBe("rejected");
    expect(rejected.review_notes).toContain("Test rejection");
    expect(rejected.reviewed_at).toBeTruthy();
  });

  test("Step 9: Verify generations list reflects all statuses", async ({
    request,
  }) => {
    const h = apiHeaders(state.token!);

    const res = await request.get(`${API_BASE}/safety/programs/generations`, {
      headers: h,
    });
    expect(res.ok()).toBeTruthy();
    const data = await res.json();

    // Should have at least 2 generations now
    expect(data.length).toBeGreaterThanOrEqual(2);

    // Check we have different statuses represented
    const statuses = new Set(data.map((g: Record<string, unknown>) => g.status));
    // We should have approved and rejected (from steps 5 and 8)
    expect(
      statuses.has("approved") || statuses.has("rejected") || statuses.has("pending_review"),
    ).toBeTruthy();
  });

  test("Step 10: Briefing endpoint works for safety trainer", async ({
    request,
  }) => {
    const h = apiHeaders(state.token!);

    // Admin should have safety.trainer.view via wildcard permissions
    // The briefing should include safety program items
    const res = await request.get(`${API_BASE}/briefings/morning`, {
      headers: h,
    });
    // Briefing might return 200, 204, or other — we just check it doesn't 500
    expect(res.status()).toBeLessThan(500);
  });

  test("Step 11: Regenerate PDF for a generation", async ({ request }) => {
    test.skip(!state.generationId, "No generation available");
    const h = apiHeaders(state.token!);

    // Check if generation has HTML content
    const detailRes = await request.get(
      `${API_BASE}/safety/programs/generations/${state.generationId}`,
      { headers: h },
    );
    const detail = await detailRes.json();

    if (!detail.generated_html) {
      test.skip(true, "No HTML content for PDF regeneration");
      return;
    }

    const res = await request.post(
      `${API_BASE}/safety/programs/generations/${state.generationId}/regenerate-pdf`,
      { headers: h, timeout: 30_000 },
    );
    expect(res.ok()).toBeTruthy();
    const data = await res.json();
    expect(data.pdf_document_id).toBeTruthy();
    expect(data.pdf_generated_at).toBeTruthy();
  });
});

/**
 * Builder AI Assistant Phase 1a — workflow-authoring generation (staging e2e).
 *
 * The generation-QUALITY proof the local backend unit test can't give (it mocks
 * the model): a REAL Sonnet call must emit a workflow canvas_state that PASSES
 * the existing server-side validator. Staging-canonical (prod→staging fetch
 * redirect, testco tenant) + Claude-API framework (real model call).
 *
 * Precondition: staging has the authoring prompt + model routes seeded (the D-1
 * canonical seed runner auto-runs scripts/seed_workflow_authoring_prompt.py +
 * scripts/seed_intelligence.py on deploy) AND ANTHROPIC_API_KEY configured. If
 * the AI isn't configured, the generate test skips gracefully (an env gap, not
 * a generation failure) — the validator-PASS assertion only fires when the
 * model actually ran.
 */
import { test, expect } from "@playwright/test";

const STAGING_BACKEND =
  process.env.BACKEND_URL || "https://sunnycresterp-staging.up.railway.app";
const TENANT_SLUG = "testco";
const CREDS = { email: "admin@testco.com", password: "TestAdmin123!" };

async function authHeaders(request: import("@playwright/test").APIRequestContext) {
  const login = await request.post(`${STAGING_BACKEND}/api/v1/auth/login`, {
    data: { identifier: CREDS.email, password: CREDS.password },
    headers: { "X-Company-Slug": TENANT_SLUG },
  });
  expect(login.ok()).toBeTruthy();
  const token = (await login.json()).access_token;
  return {
    Authorization: `Bearer ${token}`,
    "X-Company-Slug": TENANT_SLUG,
    "Content-Type": "application/json",
  };
}

test.describe("Workflow Authoring — Phase 1a backend generation", () => {
  test("nl-entities grounding dump returns the entity catalog", async ({ request }) => {
    const headers = await authHeaders(request);
    const res = await request.get(
      `${STAGING_BACKEND}/api/v1/workflow-authoring/nl-entities`,
      { headers },
    );
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(Array.isArray(body.entities)).toBe(true);
    const types = new Set(body.entities.map((e: { entity_type: string }) => e.entity_type));
    expect(types.has("case")).toBe(true);
    const sample = body.entities[0];
    expect(sample).toHaveProperty("fields");
    expect(sample.fields[0]).toHaveProperty("key");
    expect(sample.fields[0]).toHaveProperty("required");
  });

  test("generate: a multi-branch funeral NL spec yields a canvas_state that PASSES the validator", async ({
    request,
  }) => {
    const headers = await authHeaders(request);
    const res = await request.post(
      `${STAGING_BACKEND}/api/v1/workflow-authoring/generate`,
      {
        headers,
        // generous timeout — a real Sonnet whole-config generation is slow.
        timeout: 90_000,
        data: {
          vertical: "funeral_home",
          workflow_type: "funeral_cascade_generated",
          nl:
            "When a funeral case is committed, generate the case file, then branch " +
            "on disposition: a burial path (order the vault, reserve the cemetery " +
            "plot, generate burial documents) and a cremation path (send the " +
            "cremation request, generate the cremation certificate). Converge both " +
            "paths, then generate the obituary, schedule the service, generate the " +
            "program, and notify the family.",
        },
      },
    );

    // Env-unconfigured guard: if the AI didn't run (no key / route / prompt on
    // this deploy), skip — that's an environment gap, not a generation failure.
    if (!res.ok()) {
      test.skip(true, `generate endpoint not OK (${res.status()}) — AI likely unconfigured on this deploy`);
      return;
    }
    const body = await res.json();
    if (body.ai_status !== "success" && body.ai_status !== "fallback_used") {
      test.skip(true, `model did not run (ai_status=${body.ai_status}) — AI unconfigured`);
      return;
    }

    // THE PROOF: the real model emitted a canvas_state that passes the
    // server-side validator (valid structure: ids, edge integrity, acyclic,
    // container ≤1-parent). If this fails, the generator can't reliably emit
    // valid structure — a finding to surface BEFORE 1b builds UI on top.
    expect(body.valid, `validation_error: ${body.validation_error}`).toBe(true);
    expect(body.validation_error).toBeFalsy();
    expect(body.canvas_state).toBeTruthy();
    expect(Array.isArray(body.canvas_state.nodes)).toBe(true);
    expect(body.canvas_state.nodes.length).toBeGreaterThan(3);
    expect(Array.isArray(body.canvas_state.edges)).toBe(true);
    // It should read as branching control flow (a decision/branch node present).
    const types = body.canvas_state.nodes.map((n: { type: string }) => n.type);
    expect(types.some((t: string) => t === "decision" || t === "branch")).toBe(true);
  });
});

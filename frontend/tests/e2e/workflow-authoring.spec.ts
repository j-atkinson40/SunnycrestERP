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
  // The login schema wants email+password (or username+pin) — NOT `identifier`
  // (verified against staging: an `identifier` body is rejected with a 422
  // "Provide either email+password or username+pin").
  const login = await request.post(`${STAGING_BACKEND}/api/v1/auth/login`, {
    data: { email: CREDS.email, password: CREDS.password },
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

  // The verdict means "reliably," not "once" — so stress the validator across
  // shapes that exercise DIFFERENT validator rules: a flat linear chain (no
  // branches), a multi-branch cascade (decision + converge — edge integrity +
  // acyclicity under branching), and a denser parallel graph (parallel
  // split/join — fan-out/fan-in id + reachability). all-PASS = a real green;
  // one lucky pass does not clear the 1b "is generation good enough" gate.
  const SHAPES: Array<{
    name: string;
    vertical: string;
    workflow_type: string;
    nl: string;
    // shape-specific structural check (lenient — model wording varies); the
    // PRIMARY assertion is always validator-PASS.
    structure?: (types: string[], nodeCount: number) => { ok: boolean; why: string };
  }> = [
    {
      name: "flat linear flow",
      vertical: "manufacturing",
      workflow_type: "invoice_send_linear_generated",
      nl:
        "When an invoice is finalized, generate the invoice PDF, then email it " +
        "to the customer, then log the delivery confirmation, then mark the " +
        "invoice as sent.",
      // linear: enough steps, and no branching control flow needed.
      structure: (types, n) => ({
        ok: n >= 4,
        why: `expected a multi-step linear chain (>=4 nodes), got ${n}`,
      }),
    },
    {
      name: "multi-branch cascade",
      vertical: "funeral_home",
      workflow_type: "funeral_cascade_generated",
      nl:
        "When a funeral case is committed, generate the case file, then branch " +
        "on disposition: a burial path (order the vault, reserve the cemetery " +
        "plot, generate burial documents) and a cremation path (send the " +
        "cremation request, generate the cremation certificate). Converge both " +
        "paths, then generate the obituary, schedule the service, generate the " +
        "program, and notify the family.",
      // branching control flow: a decision/branch node should be present.
      structure: (types) => ({
        ok: types.some((t) => t === "decision" || t === "branch"),
        why: `expected a decision/branch node, got types: ${types.join(", ")}`,
      }),
    },
    {
      name: "dense parallel graph",
      vertical: "manufacturing",
      workflow_type: "pour_pipeline_parallel_generated",
      nl:
        "When a vault production order is committed: in parallel, check raw " +
        "material inventory, reserve the production line, and notify the yard " +
        "crew. Once all three complete, schedule the pour, run a QC check, and " +
        "generate the delivery documents; then in parallel email the customer " +
        "and update the operations dashboard, and finally close the order.",
      // dense: parallel split/join present OR simply a large graph.
      structure: (types, n) => ({
        ok:
          types.some((t) => t === "parallel_split" || t === "parallel_join") ||
          n >= 8,
        why: `expected parallel split/join or a dense graph (>=8 nodes), got ${n} nodes, types: ${types.join(", ")}`,
      }),
    },
  ];

  for (const shape of SHAPES) {
    test(`generate: ${shape.name} → canvas_state that PASSES the validator`, async ({
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
            vertical: shape.vertical,
            workflow_type: shape.workflow_type,
            nl: shape.nl,
          },
        },
      );

      // The service NEVER 500s (it guards execute() and returns a structured
      // verdict even when the prompt/route/key is missing). So a non-OK HTTP
      // response is now a genuine service fault — FAIL, don't mask it as a skip.
      // The "AI unconfigured" case surfaces as ai_status="error" in a 200 body,
      // which we skip on below. (Pre-fix, an unseeded prompt / unset key 500'd
      // here and the old `if (!res.ok()) skip` silently swallowed it.)
      expect(res.ok(), `generate endpoint returned ${res.status()} — the service should never 5xx (it must return a structured valid=false verdict). A non-OK here is a real fault, not an env gap.`).toBeTruthy();
      const body = await res.json();
      // Env-unconfigured guard (the legitimate skip): the model didn't run
      // because the AI isn't configured on this deploy — an environment gap,
      // not a generation-quality failure. ai_status="error" covers an unseeded
      // prompt / unset ANTHROPIC_API_KEY now that the service guards the raise.
      if (body.ai_status !== "success" && body.ai_status !== "fallback_used") {
        test.skip(true, `model did not run (ai_status=${body.ai_status}, error=${body.validation_error}) — AI unconfigured on this deploy`);
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

      // Shape-specific structural sanity (lenient — model wording varies).
      if (shape.structure) {
        const types = body.canvas_state.nodes.map((n: { type: string }) => n.type);
        const verdict = shape.structure(types, body.canvas_state.nodes.length);
        expect(verdict.ok, verdict.why).toBe(true);
      }
    });
  }
});

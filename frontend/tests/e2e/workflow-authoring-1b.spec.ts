/**
 * Builder AI Assistant Phase 1b — platform-realm generation (staging e2e).
 *
 * 1b's consumer (the Studio Workflow editor) runs in the PLATFORM-ADMIN realm,
 * not the tenant realm 1a's route serves. 1b added a thin platform route over
 * the realm-agnostic 1a service (company_id=None). This e2e authenticates
 * PLATFORM-admin (the CI bot platform user) and exercises that NEW platform
 * route — the realm the actual consumer runs in — proving real Sonnet emits a
 * validator-PASS canvas_state under platform auth.
 *
 * The 1a tenant route + its e2e (workflow-authoring.spec.ts) stay untouched;
 * this is the platform-realm counterpart. The rail / Proposed-preview /
 * accept-reject UI behaviors are covered by the jsdom suite
 * (useWorkflowCandidate, WorkflowAssistantRail, StudioAssistantSlotContext,
 * GraphCanvas.proposed) — this spec owns the realm + generation-quality proof.
 *
 * Precondition: staging has the authoring prompt + model routes seeded AND
 * ANTHROPIC_API_KEY configured. If the AI isn't configured, the generate test
 * skips gracefully (an env gap, not a generation failure) — the validator-PASS
 * assertion only fires when the model actually ran. The route NEVER 500s (1a
 * hotfixes) — a non-OK HTTP is a real fault, not masked as a skip.
 */
import { test, expect } from "@playwright/test"
import { STAGING_BACKEND, loginAsPlatformAdmin } from "./runtime-editor/_shared"

const PLATFORM_GENERATE =
  `${STAGING_BACKEND}/api/platform/admin/visual-editor/workflow-authoring/generate`

test.describe("Workflow Authoring 1b — platform-realm generation", () => {
  test("generate (platform admin) → canvas_state that PASSES the validator", async ({
    page,
  }) => {
    const token = await loginAsPlatformAdmin(page)

    const res = await page.request.post(PLATFORM_GENERATE, {
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      // generous timeout — a real Sonnet whole-config generation is slow.
      timeout: 90_000,
      data: {
        vertical: "funeral_home",
        workflow_type: "funeral_cascade_generated",
        nl:
          "When a funeral case is committed, generate the case file, then branch " +
          "on disposition: a burial path (order the vault, reserve the cemetery " +
          "plot) and a cremation path (send the cremation request, generate the " +
          "cremation certificate). Converge both paths, then generate the " +
          "obituary, schedule the service, and notify the family.",
      },
    })

    // The route NEVER 5xx (it guards the realm-agnostic service and returns a
    // structured verdict). A non-OK HTTP is a genuine fault — FAIL, don't mask
    // it as a skip. "AI unconfigured" surfaces as ai_status="error" in a 200.
    expect(
      res.ok(),
      `platform generate returned ${res.status()} — the route should never 5xx (structured valid=false verdict). A non-OK here is a real fault, not an env gap.`,
    ).toBeTruthy()

    const body = await res.json()
    // Env-unconfigured guard (the legitimate skip): the model didn't run on
    // this deploy (no key / prompt / route) — an environment gap, not a
    // generation-quality failure.
    if (body.ai_status !== "success" && body.ai_status !== "fallback_used") {
      test.skip(
        true,
        `model did not run (ai_status=${body.ai_status}, error=${body.validation_error}) — AI unconfigured on this deploy`,
      )
      return
    }

    // THE PROOF: real Sonnet emitted a canvas_state that passes the server-side
    // validator IN THE PLATFORM REALM (the realm the Studio editor runs in).
    expect(body.valid, `validation_error: ${body.validation_error}`).toBe(true)
    expect(body.validation_error).toBeFalsy()
    expect(body.canvas_state).toBeTruthy()
    expect(Array.isArray(body.canvas_state.nodes)).toBe(true)
    expect(body.canvas_state.nodes.length).toBeGreaterThan(3)
    const types = body.canvas_state.nodes.map((n: { type: string }) => n.type)
    expect(types.some((t: string) => t === "decision" || t === "branch")).toBe(true)
  })
})

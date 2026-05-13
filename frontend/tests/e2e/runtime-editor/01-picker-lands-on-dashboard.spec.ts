/**
 * Gate 1: Pick Hopkins FH + director in picker → land at runtime
 * editor with the impersonated tenant's dashboard rendered.
 *
 * R-1.6 behavioral: drives the full flow — platform admin login,
 * tenant lookup via picker, impersonation API call, redirect into
 * the editor shell with active impersonation session.
 */
import { test, expect } from "@playwright/test"
import {
  HOPKINS_FH_SLUG,
  loginAsPlatformAdmin,
  openEditorForHopkins,
} from "./_shared"


test.describe("Gate 1 — picker lands on dashboard", () => {
  test("picker → impersonate → editor shell mounts impersonated tenant", async ({
    page,
  }) => {
    // Drive the canonical flow end-to-end: platform admin auth,
    // tenant resolution, impersonation, shell mount.
    const sess = await openEditorForHopkins(page)

    // URL carries the canonical query params.
    expect(page.url()).toContain(`tenant=${HOPKINS_FH_SLUG}`)
    expect(page.url()).toContain(`user=${encodeURIComponent(sess.impersonatedUserId)}`)

    // Editor shell mounted (NOT missing-params, NOT unauth).
    await expect(page.getByTestId("runtime-editor-shell")).toBeVisible({
      timeout: 30_000,
    })
    // Studio shell migration (1a-i.A2, May 2026): the legacy yellow
    // admin ribbon (data-testid="runtime-editor-ribbon") is suppressed
    // inside Studio context because the Studio top bar takes the
    // ribbon's role. The shell records its Studio-vs-standalone state
    // on `data-studio-context`. Intent preserved: "shell mounts in
    // Studio context with the impersonated tenant context active."
    await expect(page.getByTestId("runtime-editor-shell")).toHaveAttribute(
      "data-studio-context",
      "true",
    )
    // Studio top bar replaces the ribbon and is visible above the
    // shell — verifies the chrome handoff completed.
    await expect(page.getByTestId("studio-top-bar")).toBeVisible()
    // Tenant slug remains observable via the URL (already asserted at
    // line 26 above). No replacement tenant-slug test-id exists in the
    // Studio top bar today; if a future Studio surface renders the
    // impersonated tenant inline, tighten this assertion to target it.
  })
})

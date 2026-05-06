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
    await expect(page.getByTestId("runtime-editor-ribbon")).toBeVisible()
    // Ribbon carries the tenant slug + impersonated user.
    await expect(page.getByTestId("runtime-editor-tenant")).toHaveText(
      HOPKINS_FH_SLUG,
    )
  })
})

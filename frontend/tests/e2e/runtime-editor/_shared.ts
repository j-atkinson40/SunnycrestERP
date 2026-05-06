/**
 * Phase R-1.5 — shared fixtures + helpers for the 13 runtime-editor
 * validation-gate specs.
 *
 * All specs run against the Railway staging backend + frontend after
 * R-1.5 deploy. Local dev runs aren't supported (the impersonation
 * flow + platform admin login + tenant route tree all live behind
 * staging deployment).
 *
 * Spec-Override Discipline note (CLAUDE.md §12): the R-1 prompt
 * specified `frontend/playwright/runtime-editor/` for the spec
 * directory. The project's canonical Playwright testDir is
 * `frontend/tests/e2e/` (see playwright.config.ts), so specs land
 * under `tests/e2e/runtime-editor/` to integrate with existing CI.
 */
import { Page } from "@playwright/test"


export const STAGING_BACKEND =
  process.env.BACKEND_URL ||
  "https://sunnycresterp-staging.up.railway.app"


export const STAGING_FRONTEND =
  process.env.FRONTEND_URL ||
  "https://determined-renewal-staging.up.railway.app"


export const PLATFORM_ADMIN_EMAIL =
  process.env.PLATFORM_ADMIN_EMAIL || "platform-admin@bridgeable.test"

export const PLATFORM_ADMIN_PASSWORD =
  process.env.PLATFORM_ADMIN_PASSWORD || "PlatformAdmin123!"


export const HOPKINS_FH_SLUG = "hopkins-fh"
export const HOPKINS_DIRECTOR_USERNAME = "director1@hopkinsfh.test"


/**
 * Stub: log in as platform admin and return once the admin token is
 * persisted in localStorage. Specs that depend on platform-admin
 * auth call this in their `beforeEach`. Implementation deferred to
 * the staging-integration phase — local R-1.5 specs use API-level
 * smoke checks where possible to avoid blocking on the auth flow.
 */
export async function loginAsPlatformAdmin(page: Page): Promise<void> {
  await page.goto("/bridgeable-admin/login")
  // Page may still be loading; tolerate the suspense state.
  // Real implementation depends on the AdminLogin form's stable
  // selectors — staged for the staging-integration follow-up.
  await page.waitForLoadState("networkidle")
}


/** Helper — read a CSS variable from documentElement at runtime. */
export async function readRootCssVariable(
  page: Page,
  name: string,
): Promise<string> {
  return await page.evaluate((n) => {
    return getComputedStyle(document.documentElement)
      .getPropertyValue(`--${n}`)
      .trim()
  }, name)
}

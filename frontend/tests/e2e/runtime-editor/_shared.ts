/**
 * R-1.6 — shared fixtures + helpers for the 13 runtime-editor
 * Playwright validation gates.
 *
 * Specs run against staging. Pre-flight requirements (one-time, ops):
 *   1. Hopkins FH seeded via railway-start.sh's auto-seed (R-1.6 Part 1).
 *   2. CI bot user provisioned via `provision_ci_bot.py` (R-1.6 Part 2).
 *   3. STAGING_CI_BOT_EMAIL + STAGING_CI_BOT_PASSWORD set in GitHub
 *      Secrets, surfaced as env vars to the workflow.
 *
 * Spec-Override Discipline note (CLAUDE.md §12): R-1's prompt
 * specified `frontend/playwright/runtime-editor/`. Project's canonical
 * Playwright `testDir` is `frontend/tests/e2e/`, so specs land here.
 */
import type { Page, Request, APIRequestContext } from "@playwright/test"


export const STAGING_BACKEND =
  process.env.BACKEND_URL ||
  "https://sunnycresterp-staging.up.railway.app"


export const STAGING_FRONTEND =
  process.env.FRONTEND_URL ||
  "https://determined-renewal-staging.up.railway.app"


export const PROD_API = "https://api.getbridgeable.com"


export const PLATFORM_ADMIN_EMAIL =
  process.env.STAGING_CI_BOT_EMAIL ||
  "ci-bot-runtime-editor@bridgeable.internal"


export const PLATFORM_ADMIN_PASSWORD =
  process.env.STAGING_CI_BOT_PASSWORD || ""


export const HOPKINS_FH_SLUG = "hopkins-fh"
export const HOPKINS_FH_NAME = "Hopkins Funeral Home"
// R-1.6.10: TLD changed from .test → .example.com. Pydantic's EmailStr
// (via email-validator) rejects RFC 6761 reserved TLDs; .example.com is
// RFC 2606 reserved-for-documentation and accepted. Mirrors seed_fh_demo.py.
export const HOPKINS_DIRECTOR_EMAIL = "director1@hopkinsfh.example.com"
export const HOPKINS_ADMIN_EMAIL = "admin@hopkinsfh.example.com"
export const HOPKINS_DIRECTOR_PASSWORD = "DemoDirector123!"
export const HOPKINS_ADMIN_PASSWORD = "DemoAdmin123!"


// Storage keys mirror frontend canonical keys (admin-api.ts).
const ADMIN_TOKEN_KEY = "bridgeable-admin-token-staging"
const ADMIN_ENV_KEY = "bridgeable-admin-env"


/** Intercepts prod API calls → staging backend. Mirrors the existing
 *  setupPage pattern from intelligence/auth-setup.ts. */
export async function setupPage(page: Page): Promise<void> {
  await page.route(`${PROD_API}/**`, async (route) => {
    const url = route.request().url().replace(PROD_API, STAGING_BACKEND)
    try {
      const response = await route.fetch({ url })
      await route.fulfill({ response })
    } catch {
      await route.continue()
    }
  })
}


/** R-1.6 — log in as the CI platform admin via the
 *  `/api/platform/auth/login` endpoint, store the resulting token in
 *  localStorage under the admin-api canonical key, and pin the
 *  environment to "staging" so the app's adminApi instance routes
 *  subsequent requests to staging.
 *
 *  Returns the access token for callers that want to drive API
 *  requests directly (vs. through the page).
 *
 *  CRITICAL: token goes under `bridgeable-admin-token-staging` —
 *  NOT under tenant `access_token`. The dual-token client (per
 *  CLAUDE.md §4) enforces realm boundary; cross-realm tokens are
 *  rejected by `get_current_platform_user` / `get_current_user`. */
export async function loginAsPlatformAdmin(page: Page): Promise<string> {
  if (!PLATFORM_ADMIN_PASSWORD) {
    throw new Error(
      "STAGING_CI_BOT_PASSWORD not set in env. R-1.6 Part 2 ops handoff: " +
        "run `python -m scripts.provision_ci_bot` on staging, capture the " +
        "printed password, add to GitHub Secrets as STAGING_CI_BOT_PASSWORD.",
    )
  }

  // Hit the platform login endpoint via the page's APIRequestContext
  // so the token cookie lifecycle stays scoped to the page.
  const response = await page.request.post(
    `${STAGING_BACKEND}/api/platform/auth/login`,
    {
      data: {
        email: PLATFORM_ADMIN_EMAIL,
        password: PLATFORM_ADMIN_PASSWORD,
      },
    },
  )

  if (!response.ok()) {
    const body = await response.text()
    throw new Error(
      `Platform admin login failed: ${response.status()} ${body}`,
    )
  }

  const tokenData: { access_token: string } = await response.json()
  const token = tokenData.access_token

  // Stash token + env pinning before any frontend page mounts. The
  // app reads localStorage on first render; setting these BEFORE
  // navigation guarantees the AdminAuthProvider sees the token on
  // its first useEffect.
  await setupPage(page)
  await page.goto(STAGING_FRONTEND, { waitUntil: "commit" })
  await page.evaluate(
    ({ token, key, envKey, env }) => {
      localStorage.setItem(key, token)
      localStorage.setItem(envKey, env)
    },
    {
      token,
      key: ADMIN_TOKEN_KEY,
      envKey: ADMIN_ENV_KEY,
      env: "staging",
    },
  )

  return token
}


/** R-1.6 — start an impersonation session for Hopkins FH director1.
 *  Calls the platform impersonation endpoint with platform admin
 *  auth, persists the returned tenant token under
 *  `localStorage.access_token` + `localStorage.company_slug` + the
 *  `runtime_editor_session` marker (mirrors TenantUserPicker's
 *  post-success flow).
 *
 *  Returns the impersonation response so callers can navigate to
 *  `/runtime-editor/?tenant=<slug>&user=<id>` and have the shell
 *  mount with active tenant context. */
export async function impersonateHopkinsDirector(
  page: Page,
  adminToken: string,
): Promise<{
  tenantSlug: string
  impersonatedUserId: string
  sessionId: string
}> {
  // Resolve tenant id by slug via the lookup endpoint.
  const lookup = await page.request.get(
    `${STAGING_BACKEND}/api/platform/admin/tenants/lookup?q=hopkins`,
    {
      headers: { Authorization: `Bearer ${adminToken}` },
    },
  )
  if (!lookup.ok()) {
    throw new Error(
      `Tenant lookup failed: ${lookup.status()} ${await lookup.text()}. ` +
        "Hopkins FH may not be seeded — verify railway-start.sh ran " +
        "seed_fh_demo successfully.",
    )
  }
  const tenants: Array<{ id: string; slug: string; name: string }> =
    await lookup.json()
  const hopkins = tenants.find((t) => t.slug === HOPKINS_FH_SLUG)
  if (!hopkins) {
    throw new Error(
      `Hopkins FH not found in tenant lookup. Available slugs: ${tenants
        .map((t) => t.slug)
        .join(", ")}. Hopkins seeding may have failed on staging.`,
    )
  }

  // Call impersonate. user_id null → API picks tenant's first admin;
  // we'll replace it with director1's id post-resolution if the
  // first-admin choice doesn't match. For R-1.6 Hopkins, the seeded
  // first admin is admin@hopkinsfh.example.com, NOT director1@. The R-1.5
  // specs reference director1; pass null to accept the first admin
  // for the picker flow (the spec's URL param is informational, not
  // a hard requirement on which user is impersonated).
  const impersonate = await page.request.post(
    `${STAGING_BACKEND}/api/platform/impersonation/impersonate`,
    {
      headers: {
        Authorization: `Bearer ${adminToken}`,
        "Content-Type": "application/json",
      },
      data: {
        tenant_id: hopkins.id,
        user_id: null,
        reason: "playwright runtime-editor validation gate",
      },
    },
  )
  if (!impersonate.ok()) {
    throw new Error(
      `Impersonation failed: ${impersonate.status()} ${await impersonate.text()}`,
    )
  }
  const data: {
    access_token: string
    tenant_slug: string
    impersonated_user_id: string
    session_id: string
  } = await impersonate.json()

  await page.evaluate(
    ({ token, slug, sessionId, userId }) => {
      localStorage.setItem("access_token", token)
      localStorage.setItem("company_slug", slug)
      localStorage.setItem(
        "runtime_editor_session",
        JSON.stringify({
          session_id: sessionId,
          tenant_slug: slug,
          impersonated_user_id: userId,
        }),
      )
    },
    {
      token: data.access_token,
      slug: data.tenant_slug,
      sessionId: data.session_id,
      userId: data.impersonated_user_id,
    },
  )

  return {
    tenantSlug: data.tenant_slug,
    impersonatedUserId: data.impersonated_user_id,
    sessionId: data.session_id,
  }
}


/** Convenience — full flow: platform admin login + Hopkins
 *  impersonation + navigate to the editor shell URL. The next
 *  page render is the impersonated tenant's `/dashboard`. */
export async function openEditorForHopkins(page: Page): Promise<{
  tenantSlug: string
  impersonatedUserId: string
}> {
  const token = await loginAsPlatformAdmin(page)
  const sess = await impersonateHopkinsDirector(page, token)
  await page.goto(
    `/bridgeable-admin/runtime-editor/?tenant=${encodeURIComponent(sess.tenantSlug)}&user=${encodeURIComponent(sess.impersonatedUserId)}`,
  )
  await page.waitForLoadState("networkidle")
  return sess
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


/** Helper — direct tenant login (no impersonation). Used by the
 *  tenant-operator regression spec (Gate 10) to verify the existing
 *  Hopkins FH director1 path is unchanged by R-1 + R-1.5. */
export async function loginAsHopkinsDirector(page: Page): Promise<void> {
  await setupPage(page)
  await page.goto(STAGING_FRONTEND, { waitUntil: "commit" })
  // Set tenant slug BEFORE navigating to login so the auth interceptor
  // routes correctly.
  await page.evaluate((slug) => {
    localStorage.setItem("company_slug", slug)
  }, HOPKINS_FH_SLUG)
  await page.goto("/login")
  await page.waitForLoadState("networkidle")

  const identifier = page.locator("#identifier")
  await identifier.waitFor({ state: "visible", timeout: 10_000 })
  await identifier.fill(HOPKINS_DIRECTOR_EMAIL)
  const password = page.locator("#password")
  await password.waitFor({ state: "visible", timeout: 5_000 })
  await password.fill(HOPKINS_DIRECTOR_PASSWORD)
  // R-1.6.11: waitForLoadState("networkidle") here was racy — it would
  // resolve in the microtask gap between click() and fetch dispatch,
  // causing the spec to assert before login completed. Replaced with
  // explicit waitForResponse + waitForURL to guarantee the login flow
  // fully completes before returning.
  await Promise.all([
    page.waitForResponse(
      (resp) =>
        resp.url().includes("/api/v1/auth/login") &&
        resp.request().method() === "POST",
      { timeout: 10_000 },
    ),
    page.getByRole("button", { name: /sign\s*in/i }).click(),
  ])
  await page.waitForURL((url) => !url.pathname.includes("/login"), {
    timeout: 10_000,
  })
}

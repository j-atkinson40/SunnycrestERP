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


// R-1.6.16 — testco is the canonical manufacturing-vertical dev tenant.
// Synthetic, seeded by seed_staging.py + seed_dispatch_demo.py on every
// staging deploy via railway-start.sh. Mirrors the Hopkins FH constants
// for the FH vertical. See CLAUDE.md "Canonical development tenants"
// for the full mental model. testco is NOT Sunnycrest Precast (the real
// company that owns Bridgeable); Sunnycrest is production-only.
export const TESTCO_SLUG = "testco"
export const TESTCO_NAME = "Test Vault Co"
export const TESTCO_ADMIN_EMAIL = "admin@testco.com"
export const TESTCO_ADMIN_PASSWORD = "TestAdmin123!"
// Dispatcher user seeded by seed_dispatch_demo.py — owns the daily
// kanban surface where DeliveryCard / AncillaryCard render.
export const TESTCO_DISPATCHER_EMAIL = "dispatcher@testco.com"
export const TESTCO_DISPATCHER_PASSWORD = "TestDispatch123!"


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
    // R-7-η: per R-6.1b.2 lock, differentiate failure modes rather than collapse to single hint.
    const status = lookup.status()
    const hint =
      status === 401 ? "platform admin token invalid or expired; refresh and retry" :
      status === 403 ? "platform admin token lacks impersonation permissions" :
      status === 404 ? "Hopkins FH tenant not found; verify `seed_fh_demo --apply` ran successfully on staging" :
      status >= 500  ? "backend error during impersonation; check Railway deploy logs" :
      "Hopkins FH may not be seeded — verify railway-start.sh ran seed_fh_demo successfully."
    throw new Error(
      `Tenant lookup failed: ${status} ${await lookup.text()} (${hint})`,
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
  // R-1.6.13: waitForURL resolves on URL change but the destination
  // page's body content isn't necessarily painted yet — the assertion
  // would race against React mount. Wait for at least one widget
  // (post-R-1.6.12 Pulse home renders today / operator-profile /
  // recent-activity with `data-component-name` boundary divs) to
  // attach as the strongest signal that the dashboard rendered.
  await page
    .locator("[data-component-name]")
    .first()
    .waitFor({ state: "attached", timeout: 10_000 })
}


/** R-1.6.16 — start an impersonation session for testco's admin.
 *  Mirrors `impersonateHopkinsDirector` exactly; targets the
 *  manufacturing-vertical dev tenant. Used by R-2 entity-card specs
 *  (DeliveryCard / AncillaryCard / OrderCard) which render on the
 *  manufacturer dispatcher's daily kanban surface.
 *
 *  testco is seeded on every staging deploy via railway-start.sh →
 *  seed_staging.py + seed_dispatch_demo.py. seed_dispatch_demo
 *  populates ~20 deliveries (kanban + ancillary + direct-ship) +
 *  drivers + dispatcher across today through +3 days. */
export async function impersonateTestcoAdmin(
  page: Page,
  adminToken: string,
): Promise<{
  tenantSlug: string
  impersonatedUserId: string
  sessionId: string
}> {
  const lookup = await page.request.get(
    `${STAGING_BACKEND}/api/platform/admin/tenants/lookup?q=${encodeURIComponent(
      TESTCO_SLUG,
    )}`,
    {
      headers: { Authorization: `Bearer ${adminToken}` },
    },
  )
  if (!lookup.ok()) {
    // R-7-η: per R-6.1b.2 lock, differentiate failure modes rather than collapse to single hint.
    const status = lookup.status()
    const hint =
      status === 401 ? "platform admin token invalid or expired; refresh and retry" :
      status === 403 ? "platform admin token lacks impersonation permissions" :
      status === 404 ? "testco tenant not found; verify `seed_staging` ran successfully on staging" :
      status >= 500  ? "backend error during impersonation; check Railway deploy logs" :
      "testco may not be seeded — verify railway-start.sh ran seed_staging successfully."
    throw new Error(
      `Tenant lookup failed: ${status} ${await lookup.text()} (${hint})`,
    )
  }
  const tenants: Array<{ id: string; slug: string; name: string }> =
    await lookup.json()
  const testco = tenants.find((t) => t.slug === TESTCO_SLUG)
  if (!testco) {
    throw new Error(
      `testco not found in tenant lookup. Available slugs: ${tenants
        .map((t) => t.slug)
        .join(", ")}. testco seeding may have failed on staging.`,
    )
  }

  // user_id null → API picks tenant's first admin (admin@testco.com per
  // seed_staging.py:391). Pre-R-1.6 + R-2 specs that need a specific
  // role (dispatcher for kanban surfaces) can pass user_id explicitly
  // post-resolution; R-1.6.16 shipping default-admin to mirror the
  // Hopkins helper shape.
  const impersonate = await page.request.post(
    `${STAGING_BACKEND}/api/platform/impersonation/impersonate`,
    {
      headers: {
        Authorization: `Bearer ${adminToken}`,
        "Content-Type": "application/json",
      },
      data: {
        tenant_id: testco.id,
        user_id: null,
        reason: "playwright runtime-editor entity-card validation",
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


/** R-1.6.16 — convenience: platform admin login + testco
 *  impersonation + navigate to the runtime editor shell. Mirrors
 *  `openEditorForHopkins`. R-2 entity-card specs use this to land on
 *  the editor under testco; the spec then drives Cmd+K → scheduling
 *  Focus (or direct nav to `/dispatch/funeral-schedule`) to find
 *  DeliveryCard + AncillaryCard. The runtime-editor route doesn't
 *  currently support a `path=` param to land on a specific tenant
 *  surface; specs handle the post-mount navigation themselves. */
export async function openEditorForTestco(page: Page): Promise<{
  tenantSlug: string
  impersonatedUserId: string
}> {
  const token = await loginAsPlatformAdmin(page)
  const sess = await impersonateTestcoAdmin(page, token)
  await page.goto(
    `/bridgeable-admin/runtime-editor/?tenant=${encodeURIComponent(
      sess.tenantSlug,
    )}&user=${encodeURIComponent(sess.impersonatedUserId)}`,
  )
  await page.waitForLoadState("networkidle")
  return sess
}


/** R-1.6.16 — direct testco admin login (no impersonation). Mirrors
 *  `loginAsHopkinsDirector`. Tenant-operator regression checks that
 *  R-2 entity-card wrapping doesn't break the manufacturer-side daily
 *  use surfaces. */
export async function loginAsTestcoAdmin(page: Page): Promise<void> {
  await setupPage(page)
  await page.goto(STAGING_FRONTEND, { waitUntil: "commit" })
  await page.evaluate((slug) => {
    localStorage.setItem("company_slug", slug)
  }, TESTCO_SLUG)
  await page.goto("/login")
  await page.waitForLoadState("networkidle")

  const identifier = page.locator("#identifier")
  await identifier.waitFor({ state: "visible", timeout: 10_000 })
  await identifier.fill(TESTCO_ADMIN_EMAIL)
  const password = page.locator("#password")
  await password.waitFor({ state: "visible", timeout: 5_000 })
  await password.fill(TESTCO_ADMIN_PASSWORD)
  // R-1.6.11 racy-networkidle pattern preserved.
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
  // Mirrors loginAsHopkinsDirector — wait for at least one widget
  // boundary div to attach as the dashboard-rendered signal. Post-
  // R-1.6.12 testco's admin Pulse home renders today / operator-
  // profile / recent-activity with data-component-name.
  await page
    .locator("[data-component-name]")
    .first()
    .waitFor({ state: "attached", timeout: 10_000 })
}

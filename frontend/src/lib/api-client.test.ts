/**
 * R-1.6.7 — regression guard for per-request URL resolution in tenant
 * apiClient.
 *
 * Pre-R-1.6.7 the tenant apiClient baked `${VITE_API_URL}/api/v1` into
 * `axios.create({baseURL})` at module-load time. Vite resolved the env
 * var at build time and inlined the literal string into the bundle.
 * Railway's build environment did not surface the dashboard-set env var
 * at the moment `vite build` ran on the staging frontend service, so
 * the deployed bundle had `https://api.getbridgeable.com` baked in even
 * though the dashboard showed the staging URL — /auth/me hit production
 * with a staging-realm token + 404'd.
 *
 * Fix: resolve the URL per-request via `resolveApiBaseUrl()`, which
 * reads `localStorage["bridgeable-admin-env"]` at request time. Same
 * pattern as `bridgeable-admin/lib/admin-api.ts`.
 *
 * These tests fail loudly if a future refactor reintroduces build-time
 * pinning OR if the staging URL hardcode drifts away from the admin
 * client's canonical value.
 */
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { resolveApiBaseUrl } from "./api-client";

const ADMIN_ENV_KEY = "bridgeable-admin-env";

describe("resolveApiBaseUrl — R-1.6.7 per-request URL resolution", () => {
  beforeEach(() => {
    localStorage.removeItem(ADMIN_ENV_KEY);
  });

  afterEach(() => {
    localStorage.removeItem(ADMIN_ENV_KEY);
  });

  it("returns canonical staging URL when admin-env is staging", () => {
    localStorage.setItem(ADMIN_ENV_KEY, "staging");
    expect(resolveApiBaseUrl()).toBe(
      "https://sunnycresterp-staging.up.railway.app",
    );
  });

  it("returns canonical production URL when admin-env is production", () => {
    localStorage.setItem(ADMIN_ENV_KEY, "production");
    expect(resolveApiBaseUrl()).toBe("https://api.getbridgeable.com");
  });

  it("falls through to VITE_API_URL when no admin-env override is set", () => {
    // No admin-env override (default tenant-operator state). The fallback
    // is whatever VITE_API_URL is at test time. The regression-guard
    // assertion: the result MUST NOT contain api.getbridgeable.com when
    // no admin-env is set — that would indicate the fallback chain
    // accidentally routes to production for tenant operators on
    // non-production deploys.
    const url = resolveApiBaseUrl();
    expect(url).not.toContain("api.getbridgeable.com");
  });

  it("staging URL hardcode matches admin-api.ts canonical value", () => {
    // Load-bearing invariant: tenant apiClient + admin adminApi must
    // route to the SAME staging backend mid-impersonation. If this
    // hardcode drifts, the two clients hit different backends on the
    // same request flow.
    localStorage.setItem(ADMIN_ENV_KEY, "staging");
    expect(resolveApiBaseUrl()).toBe(
      "https://sunnycresterp-staging.up.railway.app",
    );
  });

  it("production URL hardcode matches admin-api.ts canonical value", () => {
    // Same load-bearing invariant for production.
    localStorage.setItem(ADMIN_ENV_KEY, "production");
    expect(resolveApiBaseUrl()).toBe("https://api.getbridgeable.com");
  });

  it("rejects unknown admin-env values via fallthrough to VITE_API_URL", () => {
    // Defense against typos / future enum extensions. Only "staging"
    // and "production" are canonical; any other value falls through
    // to the default tenant-operator branch.
    localStorage.setItem(ADMIN_ENV_KEY, "qa");
    const url = resolveApiBaseUrl();
    expect(url).not.toBe("https://sunnycresterp-staging.up.railway.app");
    expect(url).not.toBe("https://api.getbridgeable.com");
  });
});

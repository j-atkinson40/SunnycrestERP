/**
 * R-1.6.8 — regression guard for getCompanySlug() hostname parsing.
 *
 * Pre-R-1.6.8, with `VITE_APP_DOMAIN=up.railway.app` set on the staging
 * frontend service, `sunnycresterp-staging.up.railway.app` incorrectly
 * extracted `"sunnycresterp-staging"` as a tenant slug — surfaced as
 * a 404 from `/api/v1/auth/me` with body
 *   "Company 'sunnycresterp-staging' not found or is inactive."
 *
 * Fix rejects Railway hostnames + admin hostnames before the
 * VITE_APP_DOMAIN suffix-strip path, and routes the empty-slug
 * fallthroughs to localStorage so the impersonation flow's
 * `localStorage.company_slug` write is honored on admin/staging
 * hostnames.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getCompanySlug } from "./tenant";

function setHostname(host: string) {
  // jsdom's window.location is read-only, but we can replace the
  // hostname property via Object.defineProperty.
  Object.defineProperty(window, "location", {
    writable: true,
    value: { ...window.location, hostname: host },
  });
}

function setViteAppDomain(value: string | undefined) {
  if (value === undefined) {
    vi.stubEnv("VITE_APP_DOMAIN", "");
  } else {
    vi.stubEnv("VITE_APP_DOMAIN", value);
  }
}

describe("getCompanySlug — R-1.6.8 hostname parsing", () => {
  beforeEach(() => {
    localStorage.removeItem("company_slug");
    vi.unstubAllEnvs();
  });

  afterEach(() => {
    localStorage.removeItem("company_slug");
    vi.unstubAllEnvs();
  });

  it("extracts slug from a real tenant subdomain when VITE_APP_DOMAIN matches", () => {
    setHostname("hopkins-fh.getbridgeable.com");
    setViteAppDomain("getbridgeable.com");
    expect(getCompanySlug()).toBe("hopkins-fh");
  });

  it("rejects admin.getbridgeable.com — falls through to localStorage", () => {
    setHostname("admin.getbridgeable.com");
    setViteAppDomain("getbridgeable.com");
    localStorage.setItem("company_slug", "hopkins-fh");
    expect(getCompanySlug()).toBe("hopkins-fh");
  });

  it("rejects admin.staging.getbridgeable.com — falls through to localStorage", () => {
    setHostname("admin.staging.getbridgeable.com");
    setViteAppDomain("getbridgeable.com");
    localStorage.setItem("company_slug", "hopkins-fh");
    expect(getCompanySlug()).toBe("hopkins-fh");
  });

  it("R-1.6.8 regression guard — rejects Railway hostnames even with VITE_APP_DOMAIN=up.railway.app", () => {
    // This is the exact bug. VITE_APP_DOMAIN was set to "up.railway.app"
    // on the staging frontend service; pre-R-1.6.8 the suffix-strip
    // returned "sunnycresterp-staging" as a tenant slug. Post-fix, the
    // Railway-hostname rejection fires first and returns localStorage.
    setHostname("sunnycresterp-staging.up.railway.app");
    setViteAppDomain("up.railway.app");
    localStorage.setItem("company_slug", "hopkins-fh");
    expect(getCompanySlug()).toBe("hopkins-fh");
    expect(getCompanySlug()).not.toBe("sunnycresterp-staging");
  });

  it("rejects determined-renewal-staging.up.railway.app (frontend Railway URL)", () => {
    setHostname("determined-renewal-staging.up.railway.app");
    setViteAppDomain("up.railway.app");
    localStorage.setItem("company_slug", "hopkins-fh");
    expect(getCompanySlug()).toBe("hopkins-fh");
  });

  it("rejects Railway hostnames even when localStorage is empty", () => {
    setHostname("sunnycresterp-staging.up.railway.app");
    setViteAppDomain("up.railway.app");
    expect(getCompanySlug()).toBe("");
  });

  it("returns localStorage on bare localhost", () => {
    setHostname("localhost");
    localStorage.setItem("company_slug", "testco");
    expect(getCompanySlug()).toBe("testco");
  });

  it("returns localStorage on 127.0.0.1", () => {
    setHostname("127.0.0.1");
    localStorage.setItem("company_slug", "testco");
    expect(getCompanySlug()).toBe("testco");
  });

  it("extracts subdomain from acme.localhost (dev pattern)", () => {
    setHostname("acme.localhost");
    expect(getCompanySlug()).toBe("acme");
  });

  it("rejects admin.localhost — falls through to localStorage", () => {
    setHostname("admin.localhost");
    localStorage.setItem("company_slug", "testco");
    expect(getCompanySlug()).toBe("testco");
  });

  it("rejects www.getbridgeable.com — reserved subdomain", () => {
    setHostname("www.getbridgeable.com");
    setViteAppDomain("getbridgeable.com");
    localStorage.setItem("company_slug", "hopkins-fh");
    expect(getCompanySlug()).toBe("hopkins-fh");
  });

  it("rejects api.getbridgeable.com — reserved subdomain", () => {
    setHostname("api.getbridgeable.com");
    setViteAppDomain("getbridgeable.com");
    localStorage.setItem("company_slug", "hopkins-fh");
    expect(getCompanySlug()).toBe("hopkins-fh");
  });

  it("returns empty string when no slug source is available", () => {
    setHostname("admin.staging.getbridgeable.com");
    setViteAppDomain("getbridgeable.com");
    // No localStorage value.
    expect(getCompanySlug()).toBe("");
  });

  it("R-1.6.8 invariant — admin hostname check fires regardless of VITE_APP_DOMAIN", () => {
    // Even if VITE_APP_DOMAIN is unset / empty / weird, an "admin." prefix
    // is always rejected. Defense against future env var drift.
    setHostname("admin.something.unknown");
    setViteAppDomain(undefined);
    localStorage.setItem("company_slug", "hopkins-fh");
    expect(getCompanySlug()).toBe("hopkins-fh");
  });
});

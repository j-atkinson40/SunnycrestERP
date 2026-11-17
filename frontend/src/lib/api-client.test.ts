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

import apiClient, { resolveApiBaseUrl } from "./api-client";

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


/**
 * ⚠️ **THE UPLOAD GUARD. This is the test whose absence cost a production
 * payroll turn-on on 2026-11-17.**
 *
 * The register upload answered **422 in 41 ms having received 1,156 bytes** of
 * a 1,708,810-byte PDF. Nothing crashed; the file simply never left the
 * browser. `apiClient` is created with `Content-Type: application/json`, and
 * axios's `transformRequest` JSON-stringifies a FormData body when the content
 * type says JSON — a `File` becomes `{}`.
 *
 * ⚠️ **ASSERTED AGAINST THE REAL CLIENT THROUGH AXIOS'S REAL TRANSFORMS, via a
 * stub adapter that captures what axios was about to send.** A test that
 * mocked `apiClient` would be a fixture modelled on the implementation
 * (CLAUDE.md §11) and would have passed throughout the defect — which is
 * exactly what the Payroll 5a walk-through did: it mocked `uploadRegister`, so
 * the walk went green while the upload could not work.
 */
describe("apiClient — a FormData body survives as FormData", () => {
  /** Captures the final config after interceptors AND transformRequest. */
  function captureAdapter() {
    const seen: { data?: unknown; contentType?: unknown } = {};
    return {
      seen,
      adapter: (config: {
        data?: unknown;
        headers: { get?: (n: string) => unknown; [k: string]: unknown };
      }) => {
        seen.data = config.data;
        seen.contentType =
          typeof config.headers?.get === "function"
            ? config.headers.get("Content-Type")
            : config.headers?.["Content-Type"];
        return Promise.resolve({
          data: {}, status: 200, statusText: "OK",
          headers: {}, config: config as never,
        });
      },
    };
  }

  it("⚠️ does NOT arrive as a JSON string — the defect that shipped", async () => {
    const { seen, adapter } = captureAdapter();
    const fd = new FormData();
    fd.append("file", new File(["%PDF-1.4 pretend bytes"], "register.pdf",
      { type: "application/pdf" }));

    await apiClient.post("/payroll-reports/register/upload", fd, {
      adapter: adapter as never,
    });

    // The whole bug in one assertion. Pre-fix this was the string '{"file":{}}'.
    expect(typeof seen.data).not.toBe("string");
    expect(seen.data).toBeInstanceOf(FormData);
  });

  it("⚠️ carries no JSON content-type, so the browser can set the boundary", async () => {
    const { seen, adapter } = captureAdapter();
    const fd = new FormData();
    fd.append("file", new File(["x"], "r.pdf", { type: "application/pdf" }));

    await apiClient.post("/payroll-reports/register/upload", fd, {
      adapter: adapter as never,
    });

    // A multipart body with `application/json` on it, or with
    // `multipart/form-data` and NO boundary, is unparseable by the server.
    // Absent is the only correct answer: the browser then supplies the real
    // header with its boundary.
    const ct = String(seen.contentType ?? "");
    expect(ct).not.toContain("application/json");
  });

  it("a JSON body still gets the JSON content-type", async () => {
    // ⚠️ **THIS IS NOT THE CONTROL IT WAS FIRST LABELLED, AND THE LABEL WAS
    // THE DEFECT.** It was written as "proof the fix is narrow" — and when the
    // fix was deliberately widened to strip the header from EVERY request,
    // this test stayed GREEN. Axios re-adds `application/json` for a plain
    // object body, so the assertion cannot fail and could never have
    // discriminated a blanket strip from a narrow one. CLAUDE.md §11 shape 6:
    // passing for a reason unrelated to what it claims.
    //
    // Kept, because the behaviour is worth pinning. Re-labelled, because a
    // check that cannot fail is documentation and must say so. The test below
    // is the one that actually discriminates.
    const { seen, adapter } = captureAdapter();
    await apiClient.post("/anything", { hello: "world" },
      { adapter: adapter as never });
    expect(String(seen.contentType ?? "")).toContain("application/json");
    expect(typeof seen.data).toBe("string");
  });

  it("⚠️ does not eat a caller's deliberate content-type — the fix IS narrow", async () => {
    // The real control. A blanket strip removes this too, and axios infers
    // nothing for a string body — so the caller's declared type vanishes.
    // Break-tested: widening the guard to `if (true)` reddens exactly this.
    const { seen, adapter } = captureAdapter();
    await apiClient.post("/anything", "a,b,c\n1,2,3", {
      headers: { "Content-Type": "text/csv" },
      adapter: adapter as never,
    });
    expect(String(seen.contentType ?? "")).toContain("text/csv");
  });
});

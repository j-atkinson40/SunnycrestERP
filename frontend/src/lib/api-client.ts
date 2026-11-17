import axios from "axios";

import { getCompanySlug } from "./tenant";

// R-1.6.7: Per-request URL resolution. Removes build-time pinning of
// VITE_API_URL, which was the root cause of the R-1.6.7 fix — Vite
// inlines `import.meta.env.VITE_API_URL` at build time as a string
// literal in the bundle, and Railway's build environment did not
// reliably surface the dashboard-set env var at the moment `vite build`
// ran. The deployed staging bundle had `https://api.getbridgeable.com`
// baked into the tenant apiClient even though the dashboard showed the
// staging URL.
//
// Fix: resolve the URL per-request from localStorage["bridgeable-admin-env"],
// matching the pattern already in use in `bridgeable-admin/lib/admin-api.ts`.
// Both clients now read the same localStorage key + use the same staging
// URL hardcode + same production URL hardcode. Mid-impersonation routing
// is consistent across both clients.
//
// Other tenant-tree clients (platform-api-client, portal-service,
// company-service, calendar-actions-service, personalization-studio-service,
// email-inbox-service, AdminCommandBar) still use build-time-baked URLs
// and will need the same pattern when exercised under impersonation.
// Adopt incrementally as new endpoints surface.
//
// Exported for vitest regression test in __tests__/api-client.test.ts —
// future refactors that reintroduce build-time pinning fail the test
// immediately.
export function resolveApiBaseUrl(): string {
  const adminEnv =
    typeof localStorage !== "undefined"
      ? localStorage.getItem("bridgeable-admin-env")
      : null;

  if (adminEnv === "staging") {
    return (
      import.meta.env.VITE_STAGING_API_URL ||
      "https://sunnycresterp-staging.up.railway.app"
    );
  }
  if (adminEnv === "production") {
    return (
      import.meta.env.VITE_PRODUCTION_API_URL ||
      "https://api.getbridgeable.com"
    );
  }

  // Default: tenant operator (no admin override). Fall back to localhost
  // for dev when VITE_API_URL is unset.
  return import.meta.env.VITE_API_URL || "http://localhost:8000";
}

const apiClient = axios.create({
  // No baseURL — interceptor sets per-request below so the URL is
  // resolved at request time rather than baked at module-load time.
  // Mirrors the pattern in `bridgeable-admin/lib/admin-api.ts`.
  headers: { "Content-Type": "application/json" },
});

// Attach access token and company slug to every request, AND set the
// per-request baseURL.
apiClient.interceptors.request.use((config) => {
  config.baseURL = `${resolveApiBaseUrl()}/api/v1`;

  const token = localStorage.getItem("access_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }

  const slug = getCompanySlug();
  if (slug) {
    config.headers["X-Company-Slug"] = slug;
  }

  // ⚠️ **A FormData PAYLOAD MUST NOT CARRY THE JSON CONTENT-TYPE ABOVE, AND
  // THIS IS NOT COSMETIC — IT DECIDES WHETHER THE FILE IS SENT AT ALL.**
  //
  // axios 1.13.6, `transformRequest` (dist/.../axios.cjs:1714):
  //
  //     const isFormData = utils.isFormData(data);
  //     if (isFormData) {
  //       return hasJSONContentType ? JSON.stringify(formDataToJSON(data)) : data;
  //     }
  //
  // With the instance default `Content-Type: application/json` set above,
  // `hasJSONContentType` is true for EVERY request through this client — so a
  // FormData body is JSON-stringified, and a `File` serialises to `{}`. A
  // 1.7 MB PDF leaves the browser as about thirteen bytes of `{"file":{}}`.
  // Axios would have cleared the header later (axios.cjs:4067) so the browser
  // could set `multipart/form-data; boundary=...`, but by then `data` is a
  // string and `isFormData(data)` is false, so the JSON type stands.
  //
  // Measured on production 2026-11-17: the payroll register upload answered
  // **422 in 41 ms having received 1,156 bytes** of a 1,708,810-byte file. The
  // page reported "the request did not go through"; the request went through
  // perfectly and carried nothing.
  //
  // ⚠️ **21 of the 22 FormData callers in this app pass
  // `headers: {"Content-Type": "multipart/form-data"}` and that is WHY they
  // work — but not for the reason it looks like.** That header is never sent.
  // Its entire function is to make `hasJSONContentType` false so the branch
  // above is skipped. The two callers that did not pass it — `payroll/focus-api`
  // and `onboarding/unified-import` — could never upload anything.
  //
  // So the fix belongs HERE rather than in a 23rd caller remembering a magic
  // header: with the default removed for FormData, a caller can no longer get
  // this wrong. CLAUDE.md §11 "removal before recognition".
  if (typeof FormData !== "undefined" && config.data instanceof FormData) {
    const h = config.headers as unknown as {
      delete?: (name: string) => void;
      "Content-Type"?: unknown;
    };
    // AxiosHeaders in an interceptor; fall back to a plain-object delete.
    if (typeof h.delete === "function") h.delete("Content-Type");
    else delete h["Content-Type"];
  }

  return config;
});

// Handle 401 responses by refreshing the token
let isRefreshing = false;
let failedQueue: Array<{
  resolve: (token: string) => void;
  reject: (error: unknown) => void;
}> = [];

const processQueue = (error: unknown, token: string | null) => {
  failedQueue.forEach((prom) => {
    if (token) prom.resolve(token);
    else prom.reject(error);
  });
  failedQueue = [];
};

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    if (error.response?.status === 401 && !originalRequest._retry) {
      if (isRefreshing) {
        return new Promise<string>((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        }).then((token) => {
          originalRequest.headers.Authorization = `Bearer ${token}`;
          return apiClient(originalRequest);
        });
      }

      originalRequest._retry = true;
      isRefreshing = true;

      try {
        const refreshToken = localStorage.getItem("refresh_token");
        if (!refreshToken) throw new Error("No refresh token");

        const slug = getCompanySlug();
        const headers: Record<string, string> = {};
        if (slug) {
          headers["X-Company-Slug"] = slug;
        }

        // R-1.6.7: resolve per-request to honor localStorage admin-env
        // toggle, matching the request interceptor above. Stale module-
        // level constant would re-introduce the build-time-baked URL
        // bug that R-1.6.7 fixes.
        const { data } = await axios.post(
          `${resolveApiBaseUrl()}/api/v1/auth/refresh`,
          { refresh_token: refreshToken },
          { headers }
        );
        localStorage.setItem("access_token", data.access_token);
        localStorage.setItem("refresh_token", data.refresh_token);
        processQueue(null, data.access_token);
        originalRequest.headers.Authorization = `Bearer ${data.access_token}`;
        return apiClient(originalRequest);
      } catch (refreshError) {
        processQueue(refreshError, null);
        localStorage.removeItem("access_token");
        localStorage.removeItem("refresh_token");
        window.location.href = "/login";
        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
      }
    }
    return Promise.reject(error);
  }
);

export default apiClient;

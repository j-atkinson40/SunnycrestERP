/**
 * Phase R-0 — Dual-token API client for the Runtime-Aware Editor.
 *
 * The runtime-aware editor needs to hold TWO tokens simultaneously:
 *   1. PlatformUser token (`platform` realm) — used for writes to
 *      platform_themes, component_configurations, dashboard_layouts,
 *      etc. via `/api/platform/*` endpoints.
 *   2. Impersonation token (`tenant` realm with `impersonation: True`
 *      flag) — used for reads against tenant data endpoints
 *      (`/api/v1/*`) so the editor can render the tenant's
 *      perspective.
 *
 * Both coexist in one browser session. Routing is by URL path:
 *   - `/api/platform/*` → PlatformUser token from getAdminToken().
 *     Read AND write are allowed (the admin owns this realm).
 *   - `/api/v1/*` → impersonation token from localStorage.access_token.
 *     Read ONLY. Write attempts (POST/PUT/PATCH/DELETE) THROW
 *     immediately — the runtime editor never mutates tenant data
 *     under the impersonation token. Tenant-state mutations belong
 *     to the impersonated user's actual session, not the editor's.
 *
 * Cross-realm boundary is enforced TWICE:
 *   - Frontend: this client refuses tenant writes pre-flight.
 *   - Backend: get_current_platform_user / get_current_user reject
 *     cross-realm tokens at the dependency layer (CLAUDE.md §4
 *     "load-bearing security boundary").
 *
 * The strict no-fallback rule: requests to URLs NOT prefixed with
 * `/api/platform/` or `/api/v1/` throw with a clear error so future
 * additions either route explicitly or land in a new branch with
 * intent visible. No silent best-guess routing.
 *
 * Token lifecycle:
 *   - PlatformUser token managed by admin-api.ts (existing).
 *   - Impersonation token managed by impersonation-banner.tsx +
 *     impersonation_service backend (existing). 30-min TTL; banner
 *     surfaces countdown.
 *
 * This client is consumed by the Runtime-Aware Editor only. Other
 * admin tree code keeps using `adminApi` (admin-api.ts); other tenant
 * tree code keeps using `apiClient` (api-client.ts).
 */

import axios, {
  type AxiosInstance,
  type AxiosResponse,
  type InternalAxiosRequestConfig,
} from "axios"

import {
  getAdminBaseUrl,
  getAdminToken,
} from "@/bridgeable-admin/lib/admin-api"


export type DualTokenError = Error & {
  code:
    | "platform_token_missing"
    | "impersonation_token_missing"
    | "tenant_write_forbidden"
    | "unsupported_path"
}


function makeError(
  message: string,
  code: DualTokenError["code"],
): DualTokenError {
  const err = new Error(message) as DualTokenError
  err.code = code
  return err
}


const PLATFORM_PREFIX = "/api/platform/"
const TENANT_PREFIX = "/api/v1/"
const TENANT_READ_METHODS = new Set(["GET", "HEAD", "OPTIONS"])


function classifyPath(path: string): "platform" | "tenant" | "unknown" {
  if (path.startsWith(PLATFORM_PREFIX)) return "platform"
  if (path.startsWith(TENANT_PREFIX)) return "tenant"
  return "unknown"
}


/** Read the active impersonation token. Set when an impersonation
 *  session is started by the platform admin (see
 *  `impersonation-banner.tsx`). When no session is active this returns
 *  null and tenant reads will fail with a clear error. */
export function getImpersonationToken(): string | null {
  if (typeof localStorage === "undefined") return null
  return localStorage.getItem("access_token")
}


/** Build a configured Axios instance for runtime-host sessions.
 *
 *  Each request:
 *    1. Prefixes the URL with the admin base URL.
 *    2. Routes by path prefix to the correct token.
 *    3. Refuses tenant writes (always — the runtime editor must NEVER
 *       issue tenant-data mutations under the impersonation token).
 *    4. Throws on unsupported paths so unintended endpoints don't
 *       silently succeed under the wrong token.
 */
export function makeDualTokenClient(): AxiosInstance {
  const instance = axios.create({
    headers: { "Content-Type": "application/json" },
  })

  instance.interceptors.request.use(
    (config: InternalAxiosRequestConfig) => {
      const path = config.url ?? ""
      const cls = classifyPath(path)

      if (cls === "unknown") {
        throw makeError(
          `dual-token-client: unsupported path '${path}'. Requests must ` +
            `target /api/platform/* (PlatformUser token) or /api/v1/* ` +
            `(impersonation token, read-only).`,
          "unsupported_path",
        )
      }

      const method = (config.method ?? "get").toUpperCase()

      if (cls === "tenant" && !TENANT_READ_METHODS.has(method)) {
        // Strict no-fallback: tenant writes are forbidden through this
        // client. Runtime editor mutations belong on platform endpoints.
        throw makeError(
          `dual-token-client: tenant writes are forbidden through the ` +
            `runtime-host client. Use the platform-token endpoint at ` +
            `/api/platform/* for any state-changing operation.`,
          "tenant_write_forbidden",
        )
      }

      // Set base URL from admin-api environment helper (production /
      // staging toggle).
      config.baseURL = getAdminBaseUrl()

      const token =
        cls === "platform" ? getAdminToken() : getImpersonationToken()

      if (!token) {
        throw makeError(
          cls === "platform"
            ? "dual-token-client: platform token missing — admin not " +
                "logged in via /bridgeable-admin/login."
            : "dual-token-client: impersonation token missing — start " +
                "an impersonation session before issuing tenant reads.",
          cls === "platform"
            ? "platform_token_missing"
            : "impersonation_token_missing",
        )
      }

      config.headers = config.headers ?? {}
      config.headers.Authorization = `Bearer ${token}`
      return config
    },
  )

  return instance
}


export const dualTokenClient = makeDualTokenClient()


// ─── Explicit-routing helpers ───────────────────────────────────────
// Hooks + components consume these helpers so the call site declares
// intent (platform vs tenant) at the API boundary. The interceptor
// still validates the path; the helpers exist so downstream code
// reads as `platformPost(...)` rather than `client.post(...)` with
// an opaque URL prefix.


export interface DualTokenHelpers {
  /** Issue a GET against `/api/platform/...`. PlatformUser token. */
  platformGet<T>(path: string): Promise<AxiosResponse<T>>
  /** Issue a POST against `/api/platform/...`. PlatformUser token. */
  platformPost<T>(path: string, body?: unknown): Promise<AxiosResponse<T>>
  /** Issue a PATCH against `/api/platform/...`. PlatformUser token. */
  platformPatch<T>(path: string, body?: unknown): Promise<AxiosResponse<T>>
  /** Issue a PUT against `/api/platform/...`. PlatformUser token. */
  platformPut<T>(path: string, body?: unknown): Promise<AxiosResponse<T>>
  /** Issue a DELETE against `/api/platform/...`. PlatformUser token. */
  platformDelete<T>(path: string): Promise<AxiosResponse<T>>
  /** Issue a GET against `/api/v1/...`. Impersonation token, read-only. */
  tenantGet<T>(path: string): Promise<AxiosResponse<T>>
}


function ensurePrefix(path: string, expected: typeof PLATFORM_PREFIX | typeof TENANT_PREFIX) {
  if (!path.startsWith(expected)) {
    throw makeError(
      `dual-token-client: helper expected path prefix '${expected}', ` +
        `got '${path}'`,
      "unsupported_path",
    )
  }
}


export function makeDualTokenHelpers(
  client: AxiosInstance = dualTokenClient,
): DualTokenHelpers {
  return {
    platformGet<T>(path: string) {
      ensurePrefix(path, PLATFORM_PREFIX)
      return client.get<T>(path)
    },
    platformPost<T>(path: string, body?: unknown) {
      ensurePrefix(path, PLATFORM_PREFIX)
      return client.post<T>(path, body)
    },
    platformPatch<T>(path: string, body?: unknown) {
      ensurePrefix(path, PLATFORM_PREFIX)
      return client.patch<T>(path, body)
    },
    platformPut<T>(path: string, body?: unknown) {
      ensurePrefix(path, PLATFORM_PREFIX)
      return client.put<T>(path, body)
    },
    platformDelete<T>(path: string) {
      ensurePrefix(path, PLATFORM_PREFIX)
      return client.delete<T>(path)
    },
    tenantGet<T>(path: string) {
      ensurePrefix(path, TENANT_PREFIX)
      return client.get<T>(path)
    },
  }
}


/** React hook returning the dual-token helpers. Stateless — the
 *  underlying client + helpers are module-level singletons. The hook
 *  shape exists so callers can swap implementations (e.g. test
 *  doubles) via React context in subsequent phases without changing
 *  call-site shape. */
export function useRuntimeHostClient(): DualTokenHelpers {
  return _defaultHelpers
}


const _defaultHelpers = makeDualTokenHelpers()


// Internals exposed for unit tests; not part of the public runtime-host API.
export const __dual_token_internals = {
  classifyPath,
  PLATFORM_PREFIX,
  TENANT_PREFIX,
  TENANT_READ_METHODS,
  makeDualTokenClient,
}

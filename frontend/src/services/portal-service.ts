/**
 * Portal API client — Workflow Arc Phase 8e.2.
 *
 * Uses raw axios (not the shared apiClient) so portal requests
 * don't auto-inject tenant JWT tokens or subdomain headers.
 * Portal auth is identity-separate — the tenant apiClient's auth
 * interceptor would confuse the two realms.
 */

import axios, { type AxiosInstance } from "axios";

import type {
  MileageSubmitBody,
  PortalBranding,
  PortalDriverSummary,
  PortalLoginBody,
  PortalMe,
  PortalRoute,
  PortalRouteStop,
  PortalTokenPair,
  StopExceptionBody,
  StopStatusBody,
} from "@/types/portal";

// Base URL matches the shared apiClient — same backend, same
// `/api/v1` prefix, but we mount our own axios so the request
// interceptors don't leak across realms.
const API_BASE =
  (import.meta as unknown as { env: Record<string, string> }).env
    .VITE_API_URL || "http://localhost:8000";

const PORTAL_TOKEN_KEY = "portal_access_token";
const PORTAL_REFRESH_KEY = "portal_refresh_token";
const PORTAL_SPACE_KEY = "portal_space_id";

function _portalAxios(): AxiosInstance {
  const instance = axios.create({
    baseURL: `${API_BASE}/api/v1`,
  });
  // Attach the portal access token if present. NOT the tenant token —
  // realm-separation invariant.
  instance.interceptors.request.use((config) => {
    const token = window.localStorage.getItem(PORTAL_TOKEN_KEY);
    if (token) {
      config.headers = config.headers ?? {};
      (config.headers as Record<string, string>).Authorization =
        `Bearer ${token}`;
    }
    return config;
  });
  return instance;
}

// ── Public (no auth) ─────────────────────────────────────────────

export async function fetchPortalBranding(
  slug: string,
): Promise<PortalBranding> {
  const r = await _portalAxios().get<PortalBranding>(
    `/portal/${encodeURIComponent(slug)}/branding`,
  );
  return r.data;
}

export async function portalLogin(
  slug: string,
  body: PortalLoginBody,
): Promise<PortalTokenPair> {
  const r = await _portalAxios().post<PortalTokenPair>(
    `/portal/${encodeURIComponent(slug)}/login`,
    body,
  );
  // Persist tokens in localStorage — consistent with tenant auth.
  window.localStorage.setItem(PORTAL_TOKEN_KEY, r.data.access_token);
  window.localStorage.setItem(PORTAL_REFRESH_KEY, r.data.refresh_token);
  window.localStorage.setItem(PORTAL_SPACE_KEY, r.data.space_id);
  return r.data;
}

export async function portalRefresh(
  slug: string,
): Promise<PortalTokenPair> {
  const refresh = window.localStorage.getItem(PORTAL_REFRESH_KEY);
  if (!refresh) {
    throw new Error("no portal refresh token");
  }
  const r = await _portalAxios().post<PortalTokenPair>(
    `/portal/${encodeURIComponent(slug)}/refresh`,
    { refresh_token: refresh },
  );
  window.localStorage.setItem(PORTAL_TOKEN_KEY, r.data.access_token);
  window.localStorage.setItem(PORTAL_REFRESH_KEY, r.data.refresh_token);
  return r.data;
}

export function portalLogout(): void {
  window.localStorage.removeItem(PORTAL_TOKEN_KEY);
  window.localStorage.removeItem(PORTAL_REFRESH_KEY);
  window.localStorage.removeItem(PORTAL_SPACE_KEY);
}

export async function requestPasswordRecovery(
  slug: string,
  email: string,
): Promise<void> {
  await _portalAxios().post(
    `/portal/${encodeURIComponent(slug)}/password/recover/request`,
    { email },
  );
}

export async function confirmPasswordRecovery(
  slug: string,
  body: { token: string; new_password: string },
): Promise<void> {
  await _portalAxios().post(
    `/portal/${encodeURIComponent(slug)}/password/recover/confirm`,
    body,
  );
}

// ── Portal-authed ────────────────────────────────────────────────

export async function fetchPortalMe(): Promise<PortalMe> {
  const r = await _portalAxios().get<PortalMe>("/portal/me");
  return r.data;
}

export async function fetchPortalDriverSummary(): Promise<PortalDriverSummary> {
  const r = await _portalAxios().get<PortalDriverSummary>(
    "/portal/drivers/me/summary",
  );
  return r.data;
}

// ── Phase 8e.2.1 — portal driver data mirrors ──────────────────

export async function fetchTodayRoute(): Promise<PortalRoute> {
  const r = await _portalAxios().get<PortalRoute>(
    "/portal/drivers/me/route",
  );
  return r.data;
}

export async function fetchStop(stopId: string): Promise<PortalRouteStop> {
  const r = await _portalAxios().get<PortalRouteStop>(
    `/portal/drivers/me/stops/${encodeURIComponent(stopId)}`,
  );
  return r.data;
}

export async function markStopException(
  stopId: string,
  body: StopExceptionBody,
): Promise<void> {
  await _portalAxios().post(
    `/portal/drivers/me/stops/${encodeURIComponent(stopId)}/exception`,
    body,
  );
}

export async function updateStopStatus(
  stopId: string,
  body: StopStatusBody,
): Promise<PortalRouteStop> {
  const r = await _portalAxios().patch<PortalRouteStop>(
    `/portal/drivers/me/stops/${encodeURIComponent(stopId)}/status`,
    body,
  );
  return r.data;
}

export async function submitMileage(body: MileageSubmitBody): Promise<void> {
  await _portalAxios().post("/portal/drivers/me/mileage", body);
}

// ── Storage keys (exported for testing + PortalAuthContext) ──────

export const PORTAL_STORAGE_KEYS = {
  token: PORTAL_TOKEN_KEY,
  refresh: PORTAL_REFRESH_KEY,
  space: PORTAL_SPACE_KEY,
} as const;

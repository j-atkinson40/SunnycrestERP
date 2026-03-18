/**
 * Platform admin API service.
 */

import platformClient from "@/lib/platform-api-client";
import type {
  FeatureFlagMatrix,
  ImpersonateResponse,
  PlatformUser,
  SystemHealth,
  TenantDetail,
  TenantOverview,
  ImpersonationSession,
  ModuleDefinition,
  VerticalPreset,
  TenantModuleConfig,
  OnboardTenantRequest,
  OnboardTenantResponse,
} from "@/types/platform";

// ---- Auth ----

export async function platformLogin(email: string, password: string) {
  const { data } = await platformClient.post<{
    access_token: string;
    refresh_token: string;
  }>("/auth/login", { email, password });
  return data;
}

export async function platformGetMe() {
  const { data } = await platformClient.get<PlatformUser>("/auth/me");
  return data;
}

// ---- Tenants ----

export async function listTenants(params?: {
  search?: string;
  is_active?: boolean;
  limit?: number;
  offset?: number;
}) {
  const { data } = await platformClient.get<{
    items: TenantOverview[];
    total: number;
  }>("/tenants/", { params });
  return data;
}

export async function getTenant(tenantId: string) {
  const { data } = await platformClient.get<TenantDetail>(
    `/tenants/${tenantId}`
  );
  return data;
}

export async function updateTenant(tenantId: string, payload: Record<string, unknown>) {
  const { data } = await platformClient.patch(`/tenants/${tenantId}`, payload);
  return data;
}

export async function deleteTenant(tenantId: string) {
  const { data } = await platformClient.delete(`/tenants/${tenantId}`);
  return data;
}

export async function getPlatformDashboard() {
  const { data } = await platformClient.get("/tenants/dashboard");
  return data;
}

// ---- System Health ----

export async function getSystemHealth() {
  const { data } = await platformClient.get<SystemHealth>("/system/health");
  return data;
}

export async function getRecentJobs(params?: {
  status?: string;
  limit?: number;
}) {
  const { data } = await platformClient.get("/system/jobs", { params });
  return data;
}

export async function getRecentSyncs(params?: {
  tenant_id?: string;
  limit?: number;
}) {
  const { data } = await platformClient.get("/system/syncs", { params });
  return data;
}

// ---- Feature Flags ----

export async function createFeatureFlag(payload: {
  key: string;
  name: string;
  description?: string;
  category?: string;
  default_enabled?: boolean;
  is_global?: boolean;
}) {
  const { data } = await platformClient.post("/feature-flags/", payload);
  return data;
}

export async function deleteFeatureFlag(flagId: string) {
  const { data } = await platformClient.delete(`/feature-flags/${flagId}`);
  return data;
}

export async function listFeatureFlags() {
  const { data } = await platformClient.get<FeatureFlagMatrix[]>(
    "/feature-flags/"
  );
  return data;
}

export async function setTenantFlag(
  flagId: string,
  tenantId: string,
  enabled: boolean
) {
  const { data } = await platformClient.put(
    `/feature-flags/${flagId}/tenants/${tenantId}`,
    { enabled }
  );
  return data;
}

export async function removeTenantFlagOverride(
  flagId: string,
  tenantId: string
) {
  const { data } = await platformClient.delete(
    `/feature-flags/${flagId}/tenants/${tenantId}`
  );
  return data;
}

// ---- Impersonation ----

export async function impersonateTenant(
  tenantId: string,
  userId?: string,
  reason?: string
) {
  const { data } = await platformClient.post<ImpersonateResponse>(
    "/impersonation/impersonate",
    { tenant_id: tenantId, user_id: userId, reason }
  );
  return data;
}

export async function endImpersonation(sessionId: string) {
  const { data } = await platformClient.post("/impersonation/end-impersonation", {
    session_id: sessionId,
  });
  return data;
}

export async function listImpersonationSessions(params?: {
  tenant_id?: string;
  active_only?: boolean;
  limit?: number;
  offset?: number;
}) {
  const { data } = await platformClient.get<ImpersonationSession[]>(
    "/impersonation/sessions",
    { params }
  );
  return data;
}

// ---- Platform Users ----

export async function listPlatformUsers() {
  const { data } = await platformClient.get<PlatformUser[]>("/users/");
  return data;
}

export async function createPlatformUser(payload: {
  email: string;
  password: string;
  first_name: string;
  last_name: string;
  role: string;
}) {
  const { data } = await platformClient.post<PlatformUser>("/users/", payload);
  return data;
}

export async function updatePlatformUser(
  userId: string,
  payload: Record<string, unknown>
) {
  const { data } = await platformClient.patch<PlatformUser>(
    `/users/${userId}`,
    payload
  );
  return data;
}

// ---- Module Management ----

export async function listModuleDefinitions() {
  const { data } = await platformClient.get<Record<string, ModuleDefinition[]>>(
    "/modules/definitions"
  );
  return data;
}

export async function listModuleDefinitionsFlat() {
  const { data } = await platformClient.get<ModuleDefinition[]>(
    "/modules/definitions/flat"
  );
  return data;
}

export async function listVerticalPresets() {
  const { data } = await platformClient.get<VerticalPreset[]>(
    "/modules/presets"
  );
  return data;
}

export async function getVerticalPreset(presetKey: string) {
  const { data } = await platformClient.get<VerticalPreset>(
    `/modules/presets/${presetKey}`
  );
  return data;
}

export async function getTenantModules(tenantId: string) {
  const { data } = await platformClient.get<TenantModuleConfig[]>(
    `/modules/tenants/${tenantId}`
  );
  return data;
}

export async function setTenantModule(
  tenantId: string,
  moduleKey: string,
  enabled: boolean
) {
  const { data } = await platformClient.put(
    `/modules/tenants/${tenantId}/${moduleKey}`,
    { enabled }
  );
  return data;
}

export async function applyPresetToTenant(
  tenantId: string,
  presetKey: string
) {
  const { data } = await platformClient.post(
    `/modules/tenants/${tenantId}/preset`,
    { preset_key: presetKey }
  );
  return data;
}

export async function bulkSetTenantModules(
  tenantId: string,
  moduleKeys: string[]
) {
  const { data } = await platformClient.post(
    `/modules/tenants/${tenantId}/bulk`,
    { module_keys: moduleKeys }
  );
  return data;
}

export async function onboardTenant(payload: OnboardTenantRequest) {
  const { data } = await platformClient.post<OnboardTenantResponse>(
    "/modules/onboard",
    payload
  );
  return data;
}

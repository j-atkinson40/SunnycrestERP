import apiClient from "@/lib/api-client";
import type {
  CemeteryDirectoryEntry,
  CemeteryPlatformMatch,
  CemeterySelectionItem,
  CemeteryManualEntry,
} from "@/types/cemetery-directory";

const BASE = "/onboarding/cemeteries";

export async function getCemeteryDirectory(
  radiusMiles: number = 50,
): Promise<CemeteryDirectoryEntry[]> {
  const { data } = await apiClient.get(`${BASE}/cemetery-directory`, {
    params: { radius_miles: radiusMiles },
  });
  return data.entries as CemeteryDirectoryEntry[];
}

export async function recordSelections(
  selections: CemeterySelectionItem[],
  manualEntries: CemeteryManualEntry[],
): Promise<{ created: number; skipped: number; errors: number }> {
  const { data } = await apiClient.post(`${BASE}/cemetery-directory/selections`, {
    selections,
    manual_entries: manualEntries,
  });
  return data;
}

export async function refreshCemeteryDirectory(
  radiusMiles: number = 50,
): Promise<CemeteryDirectoryEntry[]> {
  const { data } = await apiClient.post(`${BASE}/cemetery-directory/refresh`, {
    radius_miles: radiusMiles,
  });
  return data.entries as CemeteryDirectoryEntry[];
}

export async function getPlatformMatches(
  radiusMiles: number = 100,
): Promise<CemeteryPlatformMatch[]> {
  const { data } = await apiClient.get(`${BASE}/cemetery-directory/platform-matches`, {
    params: { radius_miles: radiusMiles },
  });
  return data.matches as CemeteryPlatformMatch[];
}

export async function connectPlatformCemetery(
  cemeteryTenantId: string,
): Promise<{ connected: boolean; cemetery_id: string | null }> {
  const { data } = await apiClient.post(`${BASE}/cemetery-directory/platform-connect`, {
    cemetery_tenant_id: cemeteryTenantId,
  });
  return data;
}

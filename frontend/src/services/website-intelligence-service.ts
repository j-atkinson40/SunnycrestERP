import apiClient from "@/lib/api-client";
import type {
  WebsiteIntelligence,
  WebsiteSuggestion,
} from "@/types/website-intelligence";

export async function getIntelligence(): Promise<WebsiteIntelligence | null> {
  try {
    const { data } = await apiClient.get<WebsiteIntelligence>(
      "/website-intelligence",
    );
    return data;
  } catch {
    return null;
  }
}

export async function updateSuggestion(
  id: string,
  status: "accepted" | "dismissed",
): Promise<void> {
  await apiClient.patch(`/website-intelligence/suggestions/${id}`, { status });
}

export async function markApplied(): Promise<void> {
  await apiClient.post("/website-intelligence/mark-applied");
}

export async function getSuggestionsForExtension(
  extensionKey: string,
): Promise<WebsiteSuggestion[]> {
  const { data } = await apiClient.get<WebsiteSuggestion[]>(
    `/website-intelligence/suggestions/extension/${extensionKey}`,
  );
  return data;
}

// Admin endpoints

export async function getAdminIntelligence(
  tenantId: string,
): Promise<WebsiteIntelligence | null> {
  try {
    const { data } = await apiClient.get<WebsiteIntelligence>(
      `/admin/website-intelligence/${tenantId}`,
    );
    return data;
  } catch {
    return null;
  }
}

export async function rescrape(tenantId: string): Promise<void> {
  await apiClient.post(
    `/admin/website-intelligence/${tenantId}/rescrape`,
  );
}

export async function clearSuggestions(tenantId: string): Promise<void> {
  await apiClient.post(
    `/admin/website-intelligence/${tenantId}/clear`,
  );
}

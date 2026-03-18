import apiClient from "@/lib/api-client";
import type { UrnProduct, UrnCatalogStats } from "@/types/urn-catalog";

export async function listUrns(activeOnly = true): Promise<UrnProduct[]> {
  const { data } = await apiClient.get("/products/urns", { params: { active_only: activeOnly } });
  return data;
}

export async function getStats(): Promise<UrnCatalogStats> {
  const { data } = await apiClient.get("/products/urns/stats");
  return data;
}

export async function bulkImportUrns(
  urns: Array<{
    wilbert_sku: string;
    name: string;
    wholesale_cost: number;
    selling_price: number | null;
    category: string | null;
  }>,
  markupPercent?: number,
  rounding?: string,
): Promise<{ created: number; updated: number; total: number; errors: unknown[] }> {
  const { data } = await apiClient.post("/products/urns/import", {
    urns,
    markup_percent: markupPercent,
    rounding: rounding || "1.00",
  });
  return data;
}

export async function deactivateUrn(productId: string): Promise<void> {
  await apiClient.post(`/products/urns/${productId}/deactivate`);
}

export async function activateUrn(productId: string): Promise<void> {
  await apiClient.post(`/products/urns/${productId}/activate`);
}

export async function createUrn(urn: { name: string; price?: number; category?: string }): Promise<UrnProduct> {
  const { data } = await apiClient.post("/products/urns", urn);
  return data;
}

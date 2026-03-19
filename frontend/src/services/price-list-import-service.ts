import apiClient from "@/lib/api-client";
import type { PriceListImport, ReviewData } from "@/types/price-list-import";

export async function uploadPriceList(
  file: File,
): Promise<PriceListImport> {
  const formData = new FormData();
  formData.append("file", file);
  const { data } = await apiClient.post(
    "/catalog/price-list-import",
    formData,
    {
      headers: { "Content-Type": "multipart/form-data" },
      timeout: 60000,
    },
  );
  return data;
}

export async function getImportStatus(
  importId: string,
): Promise<PriceListImport> {
  const { data } = await apiClient.get(
    `/catalog/price-list-import/${importId}/status`,
  );
  return data;
}

export async function getReviewData(
  importId: string,
): Promise<ReviewData> {
  const { data } = await apiClient.get(
    `/catalog/price-list-import/${importId}/review`,
  );
  // Normalize: backend returns {import, items: {high_confidence, ...}}
  // Frontend expects import_info, high_confidence, low_confidence, unmatched at top level
  return {
    ...data,
    import_info: data.import ?? data.import_info,
    high_confidence: data.items?.high_confidence ?? data.high_confidence ?? [],
    low_confidence: data.items?.low_confidence ?? data.low_confidence ?? [],
    unmatched: data.items?.unmatched ?? data.unmatched ?? [],
  };
}

export async function updateItem(
  importId: string,
  itemId: string,
  update: {
    action?: string;
    final_product_name?: string;
    final_price?: number;
    matched_template_id?: string;
  },
): Promise<void> {
  await apiClient.patch(
    `/catalog/price-list-import/${importId}/items/${itemId}`,
    update,
  );
}

export async function acceptAll(importId: string): Promise<void> {
  await apiClient.post(
    `/catalog/price-list-import/${importId}/accept-all`,
  );
}

export async function confirmImport(
  importId: string,
): Promise<{ products_created: number }> {
  const { data } = await apiClient.post(
    `/catalog/price-list-import/${importId}/confirm`,
  );
  return data;
}

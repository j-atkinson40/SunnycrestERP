import apiClient from "@/lib/api-client";
import type { ProductBundle, BundleCreate, BundleUpdate } from "@/types/bundle";

export async function listBundles(activeOnly = true): Promise<ProductBundle[]> {
  const { data } = await apiClient.get("/products/bundles", {
    params: { active_only: activeOnly },
  });
  return data;
}

export async function getBundle(id: string): Promise<ProductBundle> {
  const { data } = await apiClient.get(`/products/bundles/${id}`);
  return data;
}

export async function createBundle(bundle: BundleCreate): Promise<ProductBundle> {
  const { data } = await apiClient.post("/products/bundles", bundle);
  return data;
}

export async function updateBundle(id: string, bundle: BundleUpdate): Promise<ProductBundle> {
  const { data } = await apiClient.patch(`/products/bundles/${id}`, bundle);
  return data;
}

export async function deleteBundle(id: string): Promise<void> {
  await apiClient.delete(`/products/bundles/${id}`);
}

export interface TenantEquipmentItem {
  id: string;
  name: string;
  pricing_type: string;
}

export async function listEquipmentItems(): Promise<TenantEquipmentItem[]> {
  const { data } = await apiClient.get("/products/equipment-items");
  return data;
}

export async function createEquipmentItem(name: string, pricingType = "rental"): Promise<TenantEquipmentItem> {
  const { data } = await apiClient.post("/products/equipment-items", { name, pricing_type: pricingType });
  return data;
}

// ---------------------------------------------------------------------------
// Bundle price resolution
// ---------------------------------------------------------------------------

export interface ResolvePriceLineItem {
  product_id?: string;
  product_name?: string;
  bundle_id?: string;
}

export interface ResolvedBundlePrice {
  bundle_id: string;
  bundle_name: string;
  price: number;
  tier: "with_vault" | "standalone";
  qualifying_product: string | null;
  with_vault_price: number | null;
  standalone_price: number | null;
  has_conditional_pricing: boolean;
}

/**
 * Resolve conditional bundle prices based on order line item composition.
 * Pass all line items from the current order/template and get back resolved
 * prices for any bundles found.
 */
export async function resolveBundlePrices(
  lineItems: ResolvePriceLineItem[],
): Promise<ResolvedBundlePrice[]> {
  const { data } = await apiClient.post("/products/bundles/resolve-prices", {
    line_items: lineItems,
  });
  return data;
}

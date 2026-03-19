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

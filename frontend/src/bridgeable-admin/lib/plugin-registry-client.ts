/**
 * R-8.y.d — Plugin Registry browser service client.
 *
 * Wraps the two canonical endpoints:
 *   GET /api/platform/admin/plugin-registry/categories
 *   GET /api/platform/admin/plugin-registry/categories/{key}/registrations
 *
 * Routes through adminApi (PlatformUser auth realm). Cross-realm
 * boundary enforced server-side (`get_current_platform_user`).
 *
 * Discriminated-union response shape per B-BROWSER-2 — same shape
 * across all 24 categories whether introspectable or not. UI
 * branches on `registry_introspectable`.
 */

import { adminApi } from "@/bridgeable-admin/lib/admin-api"


export interface CategorySummary {
  category_key: string
  registry_introspectable: boolean
  expected_implementations_count: number
  tier_hint: string
}

export interface CategoriesListResponse {
  categories: CategorySummary[]
  total: number
}

export interface RegistrationEntry {
  key: string
  metadata: Record<string, unknown>
}

export interface CategoryRegistrationsResponse {
  category_key: string
  registry_introspectable: boolean
  registrations: RegistrationEntry[]
  registry_size: number
  reason: string
  expected_implementations_count: number
  tier_hint: string
}

export class PluginRegistryError extends Error {
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = "PluginRegistryError"
    this.status = status
  }
}


export async function listCategories(): Promise<CategoriesListResponse> {
  try {
    const { data } = await adminApi.get<CategoriesListResponse>(
      "/api/platform/admin/plugin-registry/categories",
    )
    return data
  } catch (err) {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const e = err as any
    const status = e?.response?.status ?? 0
    const detail = e?.response?.data?.detail ?? e?.message ?? "Network error"
    throw new PluginRegistryError(detail, status)
  }
}


export async function getCategoryRegistrations(
  categoryKey: string,
): Promise<CategoryRegistrationsResponse> {
  try {
    const { data } = await adminApi.get<CategoryRegistrationsResponse>(
      `/api/platform/admin/plugin-registry/categories/${encodeURIComponent(
        categoryKey,
      )}/registrations`,
    )
    return data
  } catch (err) {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const e = err as any
    const status = e?.response?.status ?? 0
    const detail = e?.response?.data?.detail ?? e?.message ?? "Network error"
    throw new PluginRegistryError(detail, status)
  }
}

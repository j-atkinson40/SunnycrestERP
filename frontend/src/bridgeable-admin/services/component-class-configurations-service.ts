/**
 * Component class configurations service client (May 2026 class layer).
 *
 * Wraps `/api/platform/admin/visual-editor/classes/*` endpoints.
 * Mirrors the shape of `component-configurations-service.ts` but
 * operates on class-scoped configs instead of per-component.
 */
import { adminApi } from "@/bridgeable-admin/lib/admin-api"


export interface ClassConfigurationRecord {
  id: string
  component_class: string
  prop_overrides: Record<string, unknown>
  version: number
  is_active: boolean
  created_at: string
  updated_at: string
  created_by: string | null
  updated_by: string | null
}


export interface ResolvedClassConfiguration {
  component_class: string
  props: Record<string, unknown>
  source: {
    scope: "class_default"
    id: string | null
    version: number | null
    applied_keys: string[]
  } | null
  orphaned_keys: string[]
}


export interface ClassRegistrySnapshot {
  classes: Record<string, Record<string, Record<string, unknown>>>
}


export const componentClassConfigurationsService = {
  async list(params: {
    component_class?: string
    include_inactive?: boolean
  } = {}): Promise<ClassConfigurationRecord[]> {
    const response = await adminApi.get<ClassConfigurationRecord[]>(
      "/api/platform/admin/visual-editor/classes/",
      { params },
    )
    return response.data
  },

  async get(id: string): Promise<ClassConfigurationRecord> {
    const response = await adminApi.get<ClassConfigurationRecord>(
      `/api/platform/admin/visual-editor/classes/${id}`,
    )
    return response.data
  },

  async resolve(component_class: string): Promise<ResolvedClassConfiguration> {
    const response = await adminApi.get<ResolvedClassConfiguration>(
      "/api/platform/admin/visual-editor/classes/resolve",
      { params: { component_class } },
    )
    return response.data
  },

  async registry(): Promise<ClassRegistrySnapshot> {
    const response = await adminApi.get<ClassRegistrySnapshot>(
      "/api/platform/admin/visual-editor/classes/registry",
    )
    return response.data
  },

  async create(input: {
    component_class: string
    prop_overrides: Record<string, unknown>
  }): Promise<ClassConfigurationRecord> {
    const response = await adminApi.post<ClassConfigurationRecord>(
      "/api/platform/admin/visual-editor/classes/",
      input,
    )
    return response.data
  },

  async update(
    id: string,
    prop_overrides: Record<string, unknown>,
  ): Promise<ClassConfigurationRecord> {
    const response = await adminApi.patch<ClassConfigurationRecord>(
      `/api/platform/admin/visual-editor/classes/${id}`,
      { prop_overrides },
    )
    return response.data
  },
}

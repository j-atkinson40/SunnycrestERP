/**
 * Component Configurations API client — Phase 3 of the Admin
 * Visual Editor.
 *
 * Wraps `/api/v1/api/platform/admin/visual-editor/components/*`. Mirrors the
 * shape of `themes-service` (Phase 2).
 */

import { adminApi } from "@/bridgeable-admin/lib/admin-api"


export type ConfigScope =
  | "platform_default"
  | "vertical_default"
  | "tenant_override"


export type ComponentKind =
  | "widget"
  | "focus"
  | "focus-template"
  | "document-block"
  | "pulse-widget"
  | "workflow-node"
  | "layout"
  | "composite"
  // Class-configuration phase additions (May 2026):
  | "entity-card"
  | "button"
  | "form-input"
  | "surface-card"
  // R-2.1 — entity-card sub-section additions (May 2026):
  | "entity-card-section"


export interface ComponentConfigurationRecord {
  id: string
  scope: ConfigScope
  vertical: string | null
  tenant_id: string | null
  component_kind: ComponentKind
  component_name: string
  prop_overrides: Record<string, unknown>
  version: number
  is_active: boolean
  created_at: string
  updated_at: string
  created_by: string | null
  updated_by: string | null
}


export interface ResolvedConfiguration {
  component_kind: ComponentKind
  component_name: string
  vertical: string | null
  tenant_id: string | null
  props: Record<string, unknown>
  sources: Array<{
    scope: ConfigScope
    id: string
    version: number
    applied_keys: string[]
    vertical?: string
    tenant_id?: string
  }>
  orphaned_keys: string[]
}


export interface RegistrySnapshotEntry {
  component_kind: ComponentKind
  component_name: string
  props: Record<string, Record<string, unknown>>
}


export interface ListConfigurationsParams {
  scope?: ConfigScope
  vertical?: string
  tenant_id?: string
  component_kind?: ComponentKind
  component_name?: string
  include_inactive?: boolean
}


export const componentConfigurationsService = {
  async list(
    params: ListConfigurationsParams = {},
  ): Promise<ComponentConfigurationRecord[]> {
    const response = await adminApi.get<ComponentConfigurationRecord[]>(
      "/api/platform/admin/visual-editor/components/",
      { params },
    )
    return response.data
  },

  async get(id: string): Promise<ComponentConfigurationRecord> {
    const response = await adminApi.get<ComponentConfigurationRecord>(
      `/api/platform/admin/visual-editor/components/${id}`,
    )
    return response.data
  },

  async getRegistrySnapshot(): Promise<RegistrySnapshotEntry[]> {
    const response = await adminApi.get<{
      components: RegistrySnapshotEntry[]
    }>("/api/platform/admin/visual-editor/components/registry")
    return response.data.components
  },

  async create(input: {
    scope: ConfigScope
    vertical?: string | null
    tenant_id?: string | null
    component_kind: ComponentKind
    component_name: string
    prop_overrides: Record<string, unknown>
  }): Promise<ComponentConfigurationRecord> {
    const response = await adminApi.post<ComponentConfigurationRecord>(
      "/api/platform/admin/visual-editor/components/",
      input,
    )
    return response.data
  },

  async update(
    id: string,
    prop_overrides: Record<string, unknown>,
  ): Promise<ComponentConfigurationRecord> {
    const response = await adminApi.patch<ComponentConfigurationRecord>(
      `/api/platform/admin/visual-editor/components/${id}`,
      { prop_overrides },
    )
    return response.data
  },

  async resolve(params: {
    component_kind: ComponentKind
    component_name: string
    vertical?: string | null
    tenant_id?: string | null
  }): Promise<ResolvedConfiguration> {
    const response = await adminApi.get<ResolvedConfiguration>(
      "/api/platform/admin/visual-editor/components/resolve",
      { params },
    )
    return response.data
  },
}

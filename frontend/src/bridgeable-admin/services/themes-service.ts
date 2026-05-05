/**
 * Themes API client — Phase 2 of the Admin Visual Editor.
 *
 * Wraps the admin endpoints at /api/v1/api/platform/admin/visual-editor/themes/*. Uses the
 * existing apiClient (axios with token-refresh interceptor).
 */

import { adminApi } from "@/bridgeable-admin/lib/admin-api"


export type ThemeScope =
  | "platform_default"
  | "vertical_default"
  | "tenant_override"

export type ThemeMode = "light" | "dark"


export interface ThemeRecord {
  id: string
  scope: ThemeScope
  vertical: string | null
  tenant_id: string | null
  mode: ThemeMode
  token_overrides: Record<string, unknown>
  version: number
  is_active: boolean
  created_at: string
  updated_at: string
  created_by: string | null
  updated_by: string | null
}


export interface ResolvedTheme {
  mode: ThemeMode
  vertical: string | null
  tenant_id: string | null
  tokens: Record<string, unknown>
  sources: Array<{
    scope: ThemeScope
    id: string
    version: number
    applied_keys: string[]
    vertical?: string
    tenant_id?: string
  }>
}


export interface ListThemesParams {
  scope?: ThemeScope
  vertical?: string
  tenant_id?: string
  mode?: ThemeMode
  include_inactive?: boolean
}


export const themesService = {
  async list(params: ListThemesParams = {}): Promise<ThemeRecord[]> {
    const response = await adminApi.get<ThemeRecord[]>("/api/platform/admin/visual-editor/themes/", {
      params,
    })
    return response.data
  },

  async get(id: string): Promise<ThemeRecord> {
    const response = await adminApi.get<ThemeRecord>(`/api/platform/admin/visual-editor/themes/${id}`)
    return response.data
  },

  async create(input: {
    scope: ThemeScope
    vertical?: string | null
    tenant_id?: string | null
    mode: ThemeMode
    token_overrides: Record<string, unknown>
  }): Promise<ThemeRecord> {
    const response = await adminApi.post<ThemeRecord>("/api/platform/admin/visual-editor/themes/", input)
    return response.data
  },

  async update(
    id: string,
    token_overrides: Record<string, unknown>,
  ): Promise<ThemeRecord> {
    const response = await adminApi.patch<ThemeRecord>(
      `/api/platform/admin/visual-editor/themes/${id}`,
      { token_overrides },
    )
    return response.data
  },

  async resolve(params: {
    mode: ThemeMode
    vertical?: string | null
    tenant_id?: string | null
  }): Promise<ResolvedTheme> {
    const response = await adminApi.get<ResolvedTheme>(
      "/api/platform/admin/visual-editor/themes/resolve",
      { params },
    )
    return response.data
  },
}

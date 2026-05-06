/**
 * Phase R-0 — Dashboard Layouts admin service client.
 *
 * Talks to the new `/api/platform/admin/visual-editor/dashboard-layouts/*`
 * endpoints introduced in r87. Mirrors the shape of the existing
 * `focus-compositions-service` + `themes-service` so the Widget
 * Editor's "Dashboard Layouts" tab consumes the same patterns the
 * other Visual Editor surfaces use.
 *
 * Auth: PlatformUser token via `adminApi` (admin-api.ts). The new
 * dual-token client is consumed by the runtime-aware editor proper
 * in R-1; the existing visual editor surfaces (this service among
 * them) keep using `adminApi` for now.
 */
import { adminApi } from "@/bridgeable-admin/lib/admin-api"


export type DashboardLayoutScope =
  | "platform_default"
  | "vertical_default"
  | "tenant_default"


export interface DashboardLayoutEntry {
  widget_id: string
  enabled: boolean
  position: number
  size: string
  config?: Record<string, unknown>
}


export interface DashboardLayoutRecord {
  id: string
  scope: DashboardLayoutScope
  vertical: string | null
  tenant_id: string | null
  page_context: string
  layout_config: DashboardLayoutEntry[]
  version: number
  is_active: boolean
  created_at: string
  updated_at: string
}


export interface ResolvedDashboardLayout {
  layout_config: DashboardLayoutEntry[]
  source: DashboardLayoutScope | null
  source_id: string | null
  source_version: number | null
  sources: Array<{
    scope: DashboardLayoutScope
    id: string
    version: number
    page_context: string
    vertical: string | null
    tenant_id: string | null
  }>
  page_context: string
  vertical: string | null
  tenant_id: string | null
}


const BASE = "/api/platform/admin/visual-editor/dashboard-layouts"


export const dashboardLayoutsService = {
  async list(filters?: {
    scope?: DashboardLayoutScope
    vertical?: string | null
    tenant_id?: string | null
    page_context?: string | null
    include_inactive?: boolean
  }): Promise<DashboardLayoutRecord[]> {
    const params = new URLSearchParams()
    if (filters?.scope) params.set("scope", filters.scope)
    if (filters?.vertical) params.set("vertical", filters.vertical)
    if (filters?.tenant_id) params.set("tenant_id", filters.tenant_id)
    if (filters?.page_context)
      params.set("page_context", filters.page_context)
    if (filters?.include_inactive)
      params.set("include_inactive", "true")
    const qs = params.toString()
    const url = qs ? `${BASE}/?${qs}` : `${BASE}/`
    const { data } = await adminApi.get<DashboardLayoutRecord[]>(url)
    return data
  },

  async get(layoutId: string): Promise<DashboardLayoutRecord> {
    const { data } = await adminApi.get<DashboardLayoutRecord>(
      `${BASE}/${layoutId}`,
    )
    return data
  },

  async resolve(params: {
    page_context: string
    vertical?: string | null
    tenant_id?: string | null
  }): Promise<ResolvedDashboardLayout> {
    const usp = new URLSearchParams()
    usp.set("page_context", params.page_context)
    if (params.vertical) usp.set("vertical", params.vertical)
    if (params.tenant_id) usp.set("tenant_id", params.tenant_id)
    const { data } = await adminApi.get<ResolvedDashboardLayout>(
      `${BASE}/resolve?${usp.toString()}`,
    )
    return data
  },

  async create(payload: {
    scope: DashboardLayoutScope
    vertical?: string | null
    tenant_id?: string | null
    page_context: string
    layout_config: DashboardLayoutEntry[]
  }): Promise<DashboardLayoutRecord> {
    const { data } = await adminApi.post<DashboardLayoutRecord>(
      `${BASE}/`,
      payload,
    )
    return data
  },

  async update(
    layoutId: string,
    payload: { layout_config: DashboardLayoutEntry[] },
  ): Promise<DashboardLayoutRecord> {
    const { data } = await adminApi.patch<DashboardLayoutRecord>(
      `${BASE}/${layoutId}`,
      payload,
    )
    return data
  },
}

/**
 * Focus templates service client (sub-arc C-2.2a).
 *
 * Wraps the /api/platform/admin/focus-template-inheritance/templates
 * endpoints declared in backend/app/api/routes/admin/
 * focus_template_inheritance.py. Mirrors the backend
 * TemplateCreateRequest / TemplateUpdateRequest / TemplateResponse
 * shapes (sub-arc B-1 + B-4 substrate + B-5 typography + C-2.1.2
 * edit-session semantics).
 *
 * Pattern mirrors focus-cores-service.ts. C-2.2a is the READ-ONLY
 * editor — create() + update() ship here so C-2.2b's draft hook +
 * C-2.2c's create modal can wire onto a single canonical service.
 */
import { adminApi } from "@/bridgeable-admin/lib/admin-api"

export type TemplateScope = "platform_default" | "vertical_default"

export interface TemplateRecord {
  id: string
  scope: TemplateScope
  vertical: string | null
  template_slug: string
  display_name: string
  description: string | null
  inherits_from_core_id: string
  inherits_from_core_version: number
  rows: Array<Record<string, unknown>>
  canvas_config: Record<string, unknown>
  /** Chrome overrides cascaded on top of the inherited core's chrome. */
  chrome_overrides: Record<string, unknown>
  /** B-4 page-background substrate (Tier 2 default; Tier 1 has none). */
  substrate: Record<string, unknown>
  /** B-5 typography defaults (Tier 2 default; Tier 1 has none). */
  typography: Record<string, unknown>
  version: number
  is_active: boolean
  created_at: string
  updated_at: string
  // Sub-arc C-2.1.2 edit-session metadata (informational; the
  // frontend tracks its own session token in useFocusTemplateDraft
  // when that hook lands in C-2.2b).
  last_edit_session_id?: string | null
  last_edit_session_at?: string | null
}

export interface TemplateCreatePayload {
  scope: TemplateScope
  vertical?: string | null
  template_slug: string
  display_name: string
  description?: string | null
  inherits_from_core_id: string
  rows?: Array<Record<string, unknown>>
  canvas_config?: Record<string, unknown>
  chrome_overrides?: Record<string, unknown>
  substrate?: Record<string, unknown>
  typography?: Record<string, unknown>
}

export interface TemplateUpdatePayload {
  display_name?: string
  description?: string | null
  rows?: Array<Record<string, unknown>>
  canvas_config?: Record<string, unknown>
  chrome_overrides?: Record<string, unknown>
  substrate?: Record<string, unknown>
  typography?: Record<string, unknown>
  /** C-2.1.2 edit-session token (UUID v4). Opt into in-place mutate. */
  edit_session_id?: string
}

export interface TemplateListParams {
  scope?: TemplateScope
  vertical?: string
  include_inactive?: boolean
}

export interface TemplateUsageResponse {
  compositions_count: number
}

const BASE = "/api/platform/admin/focus-template-inheritance/templates"

export const focusTemplatesService = {
  async list(params: TemplateListParams = {}): Promise<TemplateRecord[]> {
    const res = await adminApi.get<TemplateRecord[]>(BASE, { params })
    return res.data
  },

  async get(id: string): Promise<TemplateRecord> {
    const res = await adminApi.get<TemplateRecord>(`${BASE}/${id}`)
    return res.data
  },

  async create(payload: TemplateCreatePayload): Promise<TemplateRecord> {
    const res = await adminApi.post<TemplateRecord>(BASE, payload)
    return res.data
  },

  async update(
    id: string,
    payload: TemplateUpdatePayload,
  ): Promise<TemplateRecord> {
    const res = await adminApi.put<TemplateRecord>(`${BASE}/${id}`, payload)
    return res.data
  },

  async usage(id: string): Promise<TemplateUsageResponse> {
    const res = await adminApi.get<TemplateUsageResponse>(`${BASE}/${id}/usage`)
    return res.data
  },
}

export default focusTemplatesService

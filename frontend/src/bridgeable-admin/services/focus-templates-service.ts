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

/**
 * Sub-arc C-2.3 — per-field provenance dicts surfaced by the resolver.
 * Each maps field name → "tier1" | "tier2" | "tier3" | null.
 *  - chrome: parent can be tier1 (inherited core). Tier 2 editor uses
 *    "tier1" as the inherited-from-parent signal.
 *  - substrate / typography: cores are substrate/typography-free by
 *    design; only "tier2" / "tier3" / null appear.
 */
export interface ResolveSources {
  template: Record<string, unknown>
  core: Record<string, unknown>
  tenant: Record<string, unknown> | null
  chrome_sources: Record<string, string | null>
  substrate_sources: Record<string, string | null>
  typography_sources: Record<string, string | null>
}

export interface ResolveResponse {
  template_id: string
  template_slug: string
  template_version: number
  template_scope: string
  template_vertical: string | null
  core_id: string
  core_slug: string
  core_version: number
  core_registered_component: Record<string, string>
  rows: Array<Record<string, unknown>>
  canvas_config: Record<string, unknown>
  resolved_chrome: Record<string, unknown> | null
  resolved_substrate: Record<string, unknown> | null
  resolved_typography: Record<string, unknown> | null
  sources: ResolveSources
}

export interface ResolveParams {
  template_slug: string
  vertical?: string | null
  tenant_id?: string | null
}

const BASE = "/api/platform/admin/focus-template-inheritance/templates"
const RESOLVE_PATH = "/api/platform/admin/focus-template-inheritance/resolve"

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

  /**
   * Sub-arc C-2.3 — fetch the resolved Focus with per-field provenance
   * for the inheritance-indicator chrome in the Tier 2 inspector.
   * Backend route: GET /resolve?template_slug=&vertical=&tenant_id=.
   */
  async resolve(params: ResolveParams): Promise<ResolveResponse> {
    const query: Record<string, string> = { template_slug: params.template_slug }
    if (params.vertical) query.vertical = params.vertical
    if (params.tenant_id) query.tenant_id = params.tenant_id
    const res = await adminApi.get<ResolveResponse>(RESOLVE_PATH, { params: query })
    return res.data
  },
}

export default focusTemplatesService

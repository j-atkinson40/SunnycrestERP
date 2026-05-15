/**
 * Focus cores service client (sub-arc C-2.1).
 *
 * Wraps the /api/platform/admin/focus-template-inheritance/cores
 * endpoints declared in backend/app/api/routes/admin/
 * focus_template_inheritance.py. Mirrors the backend
 * CoreCreateRequest / CoreUpdateRequest / CoreResponse shapes.
 */
import { adminApi } from "@/bridgeable-admin/lib/admin-api"

export interface CoreRecord {
  id: string
  core_slug: string
  display_name: string
  description: string | null
  registered_component_kind: string
  registered_component_name: string
  default_starting_column: number
  default_column_span: number
  default_row_index: number
  min_column_span: number
  max_column_span: number
  canvas_config: Record<string, unknown>
  chrome: Record<string, unknown>
  version: number
  is_active: boolean
  created_at: string
  updated_at: string
  // Sub-arc C-2.1.1: edit-session metadata (informational; the
  // frontend tracks its own session token in useFocusCoreDraft).
  last_edit_session_id?: string | null
  last_edit_session_at?: string | null
}

/**
 * Sub-arc C-2.1.1: shape of the 410 Gone response body the backend
 * returns when the caller targets an inactive core_id. The frontend
 * uses `active_core_id` to update its local id + retry within the
 * same edit session.
 */
export interface StaleCoreErrorBody {
  message: string
  inactive_core_id: string
  active_core_id: string | null
  slug: string
}

export interface CoreCreatePayload {
  core_slug: string
  display_name: string
  description?: string | null
  registered_component_kind: string
  registered_component_name: string
  default_starting_column?: number
  default_column_span?: number
  default_row_index?: number
  min_column_span?: number
  max_column_span?: number
  canvas_config?: Record<string, unknown>
  chrome?: Record<string, unknown>
}

export interface CoreUpdatePayload {
  display_name?: string
  description?: string | null
  registered_component_kind?: string
  registered_component_name?: string
  default_starting_column?: number
  default_column_span?: number
  default_row_index?: number
  min_column_span?: number
  max_column_span?: number
  canvas_config?: Record<string, unknown>
  chrome?: Record<string, unknown>
  // Sub-arc C-2.1.1: edit-session token. Including this opts updates
  // into in-place-mutate semantics within a 5-minute window; omit to
  // version-bump per B-1 behavior.
  edit_session_id?: string
}

const BASE = "/api/platform/admin/focus-template-inheritance/cores"

export const focusCoresService = {
  async list(): Promise<CoreRecord[]> {
    const res = await adminApi.get<CoreRecord[]>(BASE)
    return res.data
  },

  async get(id: string): Promise<CoreRecord> {
    const res = await adminApi.get<CoreRecord>(`${BASE}/${id}`)
    return res.data
  },

  async create(payload: CoreCreatePayload): Promise<CoreRecord> {
    const res = await adminApi.post<CoreRecord>(BASE, payload)
    return res.data
  },

  async update(id: string, payload: CoreUpdatePayload): Promise<CoreRecord> {
    const res = await adminApi.put<CoreRecord>(`${BASE}/${id}`, payload)
    return res.data
  },
}

export default focusCoresService

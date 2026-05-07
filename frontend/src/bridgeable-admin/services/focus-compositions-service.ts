/**
 * Focus compositions service client.
 *
 * R-3.0 — payloads now carry `rows` instead of `placements`. The
 * backend rejects pre-R-3.0 flat-placements payloads with HTTP 400.
 */
import { adminApi } from "@/bridgeable-admin/lib/admin-api"
import type {
  CompositionRecord,
  ResolvedComposition,
} from "@/lib/visual-editor/compositions/types"


export const focusCompositionsService = {
  async list(params: {
    scope?: string
    vertical?: string
    tenant_id?: string
    focus_type?: string
    include_inactive?: boolean
  } = {}): Promise<CompositionRecord[]> {
    const response = await adminApi.get<CompositionRecord[]>(
      "/api/platform/admin/visual-editor/compositions/",
      { params },
    )
    return response.data
  },

  async get(id: string): Promise<CompositionRecord> {
    const response = await adminApi.get<CompositionRecord>(
      `/api/platform/admin/visual-editor/compositions/${id}`,
    )
    return response.data
  },

  async resolve(params: {
    focus_type: string
    vertical?: string | null
    tenant_id?: string | null
  }): Promise<ResolvedComposition> {
    const response = await adminApi.get<ResolvedComposition>(
      "/api/platform/admin/visual-editor/compositions/resolve",
      { params },
    )
    return response.data
  },

  async create(input: {
    scope: string
    focus_type: string
    vertical?: string | null
    tenant_id?: string | null
    rows: CompositionRecord["rows"]
    canvas_config: CompositionRecord["canvas_config"]
  }): Promise<CompositionRecord> {
    const response = await adminApi.post<CompositionRecord>(
      "/api/platform/admin/visual-editor/compositions/",
      input,
    )
    return response.data
  },

  async update(
    id: string,
    patch: {
      rows?: CompositionRecord["rows"]
      canvas_config?: CompositionRecord["canvas_config"]
    },
  ): Promise<CompositionRecord> {
    const response = await adminApi.patch<CompositionRecord>(
      `/api/platform/admin/visual-editor/compositions/${id}`,
      patch,
    )
    return response.data
  },
}

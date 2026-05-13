/**
 * Verticals admin API client — Verticals-lite precursor arc.
 *
 * Wraps the admin-only endpoints at /api/platform/admin/verticals/*.
 * Uses the existing adminApi (platform-realm JWT, environment toggle).
 *
 * Slug is immutable (primary key on the `verticals` table). The
 * VerticalUpdate shape mirrors backend Pydantic's `VerticalUpdate`
 * (extra='forbid' — a body containing `slug` would 422 server-side).
 */

import { adminApi } from "@/bridgeable-admin/lib/admin-api"


export type VerticalStatus = "draft" | "published" | "archived"


export interface Vertical {
  slug: string
  display_name: string
  description: string | null
  status: VerticalStatus
  icon: string | null
  sort_order: number
  created_at: string
  updated_at: string
}


export interface VerticalUpdate {
  display_name?: string
  description?: string | null
  status?: VerticalStatus
  icon?: string | null
  sort_order?: number
}


export const verticalsService = {
  async list(params: { include_archived?: boolean } = {}): Promise<Vertical[]> {
    const response = await adminApi.get<Vertical[]>(
      "/api/platform/admin/verticals/",
      { params },
    )
    return response.data
  },

  async get(slug: string): Promise<Vertical> {
    const response = await adminApi.get<Vertical>(
      `/api/platform/admin/verticals/${slug}`,
    )
    return response.data
  },

  async update(slug: string, payload: VerticalUpdate): Promise<Vertical> {
    const response = await adminApi.patch<Vertical>(
      `/api/platform/admin/verticals/${slug}`,
      payload,
    )
    return response.data
  },
}

/**
 * widget-builder-service — frontend API client for the WB-4a Widget
 * Builder endpoints at `/api/v1/widget-definitions/*`.
 *
 * Thin axios wrapper. No caching, no optimistic state — the hooks own
 * those concerns. Shapes mirror the canonical response from
 * `backend/app/services/widget_definitions/publish.py::serialize_widget`.
 */
import apiClient from "@/lib/api-client"
import type { CompositionBlob } from "@/lib/widget-builder/types/composition-blob"


/** Canonical Widget Builder record shape returned by every WB-4a
 *  endpoint (GET, POST create, PUT draft, POST publish). */
export interface WidgetBuilderRecord {
  widget_id: string
  title: string
  description: string | null
  icon: string | null
  category: string | null
  composition_blob: CompositionBlob | null
  composition_version: number | null
  published_composition_blob: CompositionBlob | null
  tier_scope: "platform" | "vertical" | null
  supported_surfaces: string[]
  default_size: string
  supported_sizes: string[]
  last_edit_session_id: string | null
  last_edit_session_at: string | null
}


export interface CreateWidgetPayload {
  title?: string
  slug?: string
  tier_scope?: "platform" | "vertical"
  category?: string
}


export interface SaveDraftPayload {
  composition_blob: CompositionBlob
  edit_session_id: string | null
  title?: string
}


export interface PublishValidationError {
  code: "composition_invalid" | "no_draft"
  errors?: string[]
  message?: string
}


export class WidgetBuilderApiError extends Error {
  readonly status: number
  readonly detail: unknown
  constructor(message: string, status: number, detail: unknown) {
    super(message)
    this.name = "WidgetBuilderApiError"
    this.status = status
    this.detail = detail
  }
}


function extractDetail(err: unknown): { status: number; detail: unknown } {
  const e = err as {
    response?: { status?: number; data?: { detail?: unknown } }
  }
  const status = e.response?.status ?? 0
  const detail = e.response?.data?.detail ?? null
  return { status, detail }
}


export const widgetBuilderService = {
  async create(payload: CreateWidgetPayload): Promise<WidgetBuilderRecord> {
    try {
      const r = await apiClient.post<WidgetBuilderRecord>(
        "/widget-definitions",
        payload,
      )
      return r.data
    } catch (err) {
      const { status, detail } = extractDetail(err)
      throw new WidgetBuilderApiError(
        `Create failed (${status})`,
        status,
        detail,
      )
    }
  },

  async get(slug: string): Promise<WidgetBuilderRecord> {
    try {
      const r = await apiClient.get<WidgetBuilderRecord>(
        `/widget-definitions/${encodeURIComponent(slug)}`,
      )
      return r.data
    } catch (err) {
      const { status, detail } = extractDetail(err)
      throw new WidgetBuilderApiError(
        `Get failed (${status})`,
        status,
        detail,
      )
    }
  },

  async saveDraft(
    slug: string,
    payload: SaveDraftPayload,
  ): Promise<WidgetBuilderRecord> {
    try {
      const r = await apiClient.put<WidgetBuilderRecord>(
        `/widget-definitions/${encodeURIComponent(slug)}/draft`,
        payload,
      )
      return r.data
    } catch (err) {
      const { status, detail } = extractDetail(err)
      throw new WidgetBuilderApiError(
        `Draft save failed (${status})`,
        status,
        detail,
      )
    }
  },

  async publish(slug: string): Promise<WidgetBuilderRecord> {
    try {
      const r = await apiClient.post<WidgetBuilderRecord>(
        `/widget-definitions/${encodeURIComponent(slug)}/publish`,
      )
      return r.data
    } catch (err) {
      const { status, detail } = extractDetail(err)
      throw new WidgetBuilderApiError(
        `Publish failed (${status})`,
        status,
        detail,
      )
    }
  },
}

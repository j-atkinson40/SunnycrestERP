/**
 * visual-editor-widgets-service — WB-cycle-followup-2.
 *
 * Frontend API client for the platform-realm Widget Builder endpoints
 * at `/api/platform/admin/visual-editor/widgets/*`.
 *
 * Consumes `adminApi` (NOT tenant `apiClient`) so calls carry the
 * platform JWT (`localStorage["bridgeable-admin-token-{env}"]`)
 * resolved against the operator-selected staging/production base URL.
 *
 * Closes the 403 gap from WB-cycle-followup-1: the admin Widget Builder
 * shell previously called `/api/v1/widget-definitions/*` via the tenant
 * apiClient, which on the admin subdomain had no tenant token → 403.
 *
 * Per investigation 2026-05-26 Area 5 lock: backend service layer at
 * `app.services.widget_definitions` is realm-agnostic; only the auth
 * surface + URL prefix differ between this service and the legacy
 * tenant service it supersedes.
 *
 * Per Q-B1 lock: the tenant `registerComposedWidgets.ts` runtime bridge
 * is UNCHANGED. The bridge runs on tenant boot and fetches the tenant
 * `/api/v1/widgets/composed-definitions` endpoint — that's the
 * production render path. This service's `listComposedDefinitions()`
 * method exists for future admin-side palette consumers + structural
 * parity with the tenant service.
 */
import { adminApi } from "@/bridgeable-admin/lib/admin-api"
import type { CompositionBlob } from "@/lib/widget-builder/types/composition-blob"


/** Canonical Widget Builder record shape — identical to the legacy
 *  tenant service. Backend `serialize_widget` returns this shape from
 *  every endpoint (create, list, get, draft, publish). */
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


/** Composed-definitions palette payload — slim DTO consumed by the
 *  visual-editor metadata registry bridge. Identical shape to the
 *  tenant `/widgets/composed-definitions` endpoint. */
export interface ComposedWidgetDefinitionDTO {
  widget_id: string
  title: string
  description: string | null
  icon: string | null
  category: string | null
  composition_blob: unknown
  composition_version: number | null
  tier_scope: "platform" | "vertical" | null
  supported_surfaces: string[]
  default_size: string
  supported_sizes: string[]
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


const BASE = "/api/platform/admin/visual-editor/widgets"


export const visualEditorWidgetsService = {
  /** List composed widget definitions. Returns the canonical
   *  `{ widgets: WidgetBuilderRecord[] }` shape. */
  async list(): Promise<{ widgets: WidgetBuilderRecord[] }> {
    try {
      const r = await adminApi.get<
        { widgets: WidgetBuilderRecord[] } | WidgetBuilderRecord[]
      >(BASE)
      // Accept either {widgets: [...]} or raw array for forward-compat.
      const data = r.data as unknown
      const widgets = Array.isArray(data)
        ? (data as WidgetBuilderRecord[])
        : ((data as { widgets?: WidgetBuilderRecord[] })?.widgets ?? [])
      return { widgets }
    } catch (err) {
      const { status, detail } = extractDetail(err)
      throw new WidgetBuilderApiError(
        `List failed (${status})`,
        status,
        detail,
      )
    }
  },

  /** Fetch the composed-definitions palette payload. */
  async listComposedDefinitions(): Promise<ComposedWidgetDefinitionDTO[]> {
    try {
      const r = await adminApi.get<ComposedWidgetDefinitionDTO[]>(
        `${BASE}/composed-definitions`,
      )
      return r.data
    } catch (err) {
      const { status, detail } = extractDetail(err)
      throw new WidgetBuilderApiError(
        `Composed-definitions fetch failed (${status})`,
        status,
        detail,
      )
    }
  },

  async create(payload: CreateWidgetPayload): Promise<WidgetBuilderRecord> {
    try {
      const r = await adminApi.post<WidgetBuilderRecord>(BASE, payload)
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
      const r = await adminApi.get<WidgetBuilderRecord>(
        `${BASE}/${encodeURIComponent(slug)}`,
      )
      return r.data
    } catch (err) {
      const { status, detail } = extractDetail(err)
      throw new WidgetBuilderApiError(`Get failed (${status})`, status, detail)
    }
  },

  async saveDraft(
    slug: string,
    payload: SaveDraftPayload,
  ): Promise<WidgetBuilderRecord> {
    try {
      const r = await adminApi.put<WidgetBuilderRecord>(
        `${BASE}/${encodeURIComponent(slug)}/draft`,
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
      const r = await adminApi.post<WidgetBuilderRecord>(
        `${BASE}/${encodeURIComponent(slug)}/publish`,
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

/**
 * Maps of Content service client (MoC Phase 1).
 *
 * Wraps /api/platform/admin/moc/* (backend app/api/routes/admin/moc.py),
 * the admin realm layer over the realm-agnostic maps_of_content service.
 * Mirrors the backend response shapes.
 */
import { adminApi } from "@/bridgeable-admin/lib/admin-api"

export type MoCScope =
  | "platform_default"
  | "vertical_default"
  | "tenant_override"

/** The per-row reference resolution the backend resolver returns. */
export interface MoCRowResolution {
  exists: boolean
  available: boolean
  label: string
  routing: {
    workflow_type?: string | null
    scope?: string | null
    vertical?: string | null
    template_slug?: string | null
    widget_id?: string | null
    template_key?: string | null
  }
}

/** A row as authored, plus the resolver's `resolution` block (read paths). */
export interface MoCResolvedRow {
  row_id: string
  builder: string
  artifact_id: string
  label: string
  icon?: string | null
  order?: number
  resolution: MoCRowResolution
}

export interface MoCResolvedSection {
  section_id: string
  title: string
  description?: string | null
  order?: number
  rows: MoCResolvedRow[]
}

/** A page with references resolved for rendering (the /read shapes). */
export interface MoCResolvedPage {
  id: string
  scope: MoCScope
  vertical: string | null
  tenant_id: string | null
  slug: string
  title: string
  description: string | null
  sections: MoCResolvedSection[]
}

/** A raw page row (list + authoring editor; sections unresolved). */
export interface MoCPageRecord {
  id: string
  scope: MoCScope
  vertical: string | null
  tenant_id: string | null
  slug: string
  title: string
  description: string | null
  sections: Array<Record<string, unknown>>
}

const BASE = "/api/platform/admin/moc"

export async function listPages(params?: {
  scope?: MoCScope
  vertical?: string
  tenant_id?: string
  include_inactive?: boolean
}): Promise<MoCPageRecord[]> {
  const { data } = await adminApi.get<MoCPageRecord[]>(`${BASE}/`, {
    params,
  })
  return data
}

export async function readForContext(params: {
  vertical?: string
  tenant_id?: string
}): Promise<MoCResolvedPage> {
  const { data } = await adminApi.get<MoCResolvedPage>(`${BASE}/read`, {
    params,
  })
  return data
}

export async function readPage(pageId: string): Promise<MoCResolvedPage> {
  const { data } = await adminApi.get<MoCResolvedPage>(
    `${BASE}/${pageId}/read`,
  )
  return data
}

export async function getPage(pageId: string): Promise<MoCPageRecord> {
  const { data } = await adminApi.get<MoCPageRecord>(`${BASE}/${pageId}`)
  return data
}

export interface CreatePageInput {
  scope?: MoCScope
  vertical?: string | null
  tenant_id?: string | null
  slug: string
  title: string
  description?: string | null
  sections?: Array<Record<string, unknown>>
}

export async function createPage(
  input: CreatePageInput,
): Promise<MoCPageRecord> {
  const { data } = await adminApi.post<MoCPageRecord>(`${BASE}/`, input)
  return data
}

export interface UpdatePageInput {
  title?: string
  description?: string | null
  slug?: string
  sections?: Array<Record<string, unknown>>
}

export async function updatePage(
  pageId: string,
  input: UpdatePageInput,
): Promise<MoCPageRecord> {
  const { data } = await adminApi.patch<MoCPageRecord>(
    `${BASE}/${pageId}`,
    input,
  )
  return data
}

export async function deletePage(pageId: string): Promise<void> {
  await adminApi.delete(`${BASE}/${pageId}`)
}

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

/** A resolved workflow/focus reference on a task (MoC-2b): the resolver's
 * {exists, available, label, routing} + the artifact_id mocDeepLink needs to
 * build the href (the focus route keys on artifact_id). */
export interface MoCResolvedArtifact extends MoCRowResolution {
  artifact_id: string
}

/** A task-catalog row — descriptive cells + resolved relational cells. The
 * workflow may be null and focuses may be empty (orphan-tolerant: the
 * referenced template isn't seeded yet). */
export interface MoCTask {
  id: string
  name: string
  icon?: string | null
  frequency?: string | null
  task_type?: string | null
  description?: string | null
  display_order: number
  workflow: MoCResolvedArtifact | null
  focuses: MoCResolvedArtifact[]
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

/** A vertical's task catalog (MoC-2b), each task's workflow + focuses resolved
 * through the cards' resolver. Empty array when no tasks are seeded. */
export async function readTaskCatalog(params: {
  vertical: string
  tenant_id?: string
}): Promise<MoCTask[]> {
  const { data } = await adminApi.get<MoCTask[]>(`${BASE}/tasks`, { params })
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

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

/** A DESCRIPTIVE trigger (MoC Triggers T-1b) — legible metadata, does NOT fire.
 * `config` is kind-specific; `summary` is the backend-computed chip label
 * (reuses the shipped humanize helper — no frontend re-implementation). */
export type MoCTriggerKind = "schedule" | "event" | "manual"

export interface MoCTrigger {
  id: string
  task_catalog_id?: string
  kind: MoCTriggerKind
  config: Record<string, unknown>
  label?: string | null
  display_order: number
  is_active?: boolean
  /** Present on the task-read shape; the chip label. */
  summary?: string
}

/** A field a condition can reference, carried on the catalog event (drives the
 * condition builder). `values` present for enum fields (e.g. order_type). */
export interface MoCFilterableField {
  field: string
  type: string
  values?: string[]
}

/** A curated catalog event for the event-trigger picker. */
export interface MoCTriggerEvent {
  id: string
  event_key: string
  label: string
  entity?: string | null
  filterable_fields: MoCFilterableField[]
  scope?: string
  vertical?: string | null
  is_active?: boolean
  display_order?: number
}

/** A task-catalog row — descriptive cells + resolved relational cells + the
 * DESCRIPTIVE triggers (T-1b). The workflow may be null and focuses may be empty
 * (orphan-tolerant). `derived_frequency` is the first schedule-trigger's
 * humanized summary (null → the manual `frequency` stands — non-destructive). */
export interface MoCTask {
  id: string
  name: string
  icon?: string | null
  frequency?: string | null
  derived_frequency?: string | null
  task_type?: string | null
  description?: string | null
  display_order: number
  workflow: MoCResolvedArtifact | null
  focuses: MoCResolvedArtifact[]
  triggers?: MoCTrigger[]
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

// ── Task Editing (2a write API + 2b picker sources) ────────────────────

export interface MoCVocabValue {
  id: string
  kind: "frequency" | "type"
  value: string
  scope: string
  vertical: string | null
  display_order: number
  is_active: boolean
}

/** The constrained-editable vocabulary for the picker (platform + vertical). */
export async function listVocabulary(params?: {
  kind?: "frequency" | "type"
  vertical?: string
}): Promise<MoCVocabValue[]> {
  const { data } = await adminApi.get<MoCVocabValue[]>(`${BASE}/vocabulary`, {
    params,
  })
  return data
}

/** Add a value (the +Add-value-in-the-picker payoff). Platform-scope by default. */
export async function addVocabularyValue(input: {
  kind: "frequency" | "type"
  value: string
  scope?: MoCScope
  vertical?: string | null
}): Promise<MoCVocabValue> {
  const { data } = await adminApi.post<MoCVocabValue>(`${BASE}/vocabulary`, input)
  return data
}

/** The raw write payload from create/patch (ids, not resolved pills — re-read
 * /tasks for the resolved view). */
export interface MoCTaskWrite {
  id: string
  vertical: string
  scope: string
  name: string
  icon: string | null
  frequency: string | null
  task_type: string | null
  description: string | null
  workflow_template_id: string | null
  focus_template_ids: string[]
  display_order: number
}

export interface CreateTaskInput {
  vertical: string
  name: string
  scope?: MoCScope
  icon?: string | null
  frequency?: string | null
  task_type?: string | null
  description?: string | null
  workflow_template_id?: string | null
  focus_template_ids?: string[]
  display_order?: number
}

export async function createTask(input: CreateTaskInput): Promise<MoCTaskWrite> {
  const { data } = await adminApi.post<MoCTaskWrite>(`${BASE}/tasks`, input)
  return data
}

/** PATCH — only the keys present are applied; a sent null clears a field. */
export type PatchTaskInput = Partial<{
  name: string
  icon: string | null
  frequency: string | null
  task_type: string | null
  description: string | null
  workflow_template_id: string | null
  focus_template_ids: string[]
  display_order: number
}>

export async function patchTask(
  taskId: string,
  input: PatchTaskInput,
): Promise<MoCTaskWrite> {
  const { data } = await adminApi.patch<MoCTaskWrite>(
    `${BASE}/tasks/${taskId}`,
    input,
  )
  return data
}

export async function deleteTask(taskId: string): Promise<void> {
  await adminApi.delete(`${BASE}/tasks/${taskId}`)
}

/** A real template option for the relationship pickers (the artifacts the
 * resolver deep-links — incl. the 18 workflow mirrors). */
export interface MoCArtifactOption {
  id: string
  display_name: string
  scope?: string
  vertical?: string | null
}

export async function listWorkflowTemplateOptions(): Promise<MoCArtifactOption[]> {
  const { data } = await adminApi.get<MoCArtifactOption[]>(
    "/api/platform/admin/visual-editor/workflows/",
  )
  return data
}

export async function listFocusTemplateOptions(): Promise<MoCArtifactOption[]> {
  const { data } = await adminApi.get<MoCArtifactOption[]>(
    "/api/platform/admin/focus-template-inheritance/templates",
  )
  return data
}

// ── Task triggers (MoC Triggers T-1b) — descriptive, does NOT fire ─────

/** The curated event catalog for the event-trigger picker. Each event carries
 * its filterable_fields (the condition builder's field vocabulary). */
export async function listTriggerEvents(
  vertical?: string,
): Promise<MoCTriggerEvent[]> {
  const { data } = await adminApi.get<MoCTriggerEvent[]>(
    `${BASE}/trigger-events`,
    { params: vertical ? { vertical } : undefined },
  )
  return data
}

export interface AddTriggerInput {
  kind: MoCTriggerKind
  config: Record<string, unknown>
  label?: string | null
  display_order?: number
}

/** Attach a trigger. The event condition is a structured LIST-OF-ONE in config
 * — never flattened to a string (the expansion-ready shape). A rejected shape
 * throws (the validator's reason surfaces; the caller shows it). */
export async function addTaskTrigger(
  taskId: string,
  input: AddTriggerInput,
): Promise<MoCTrigger> {
  const { data } = await adminApi.post<MoCTrigger>(
    `${BASE}/tasks/${taskId}/triggers`,
    input,
  )
  return data
}

export type PatchTriggerInput = Partial<{
  kind: MoCTriggerKind
  config: Record<string, unknown>
  label: string | null
  display_order: number
  is_active: boolean
}>

export async function patchTrigger(
  triggerId: string,
  input: PatchTriggerInput,
): Promise<MoCTrigger> {
  const { data } = await adminApi.patch<MoCTrigger>(
    `${BASE}/triggers/${triggerId}`,
    input,
  )
  return data
}

export async function deleteTrigger(triggerId: string): Promise<void> {
  await adminApi.delete(`${BASE}/triggers/${triggerId}`)
}

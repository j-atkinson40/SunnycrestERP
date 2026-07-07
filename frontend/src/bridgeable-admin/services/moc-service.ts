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
  /** The ref-decay rebind: when the stored ref's row id went inactive under
   * a version bump, the resolver re-binds to the lineage's ACTIVE row and
   * returns its id here — deep-links must prefer this over the stored id. */
  artifact_id?: string
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
 * build the href (the focus route keys on artifact_id). `is_mirror` (T-2.1c,
 * workflow refs only): the §6 compiled-vs-mirror discriminator — a mirror
 * task's Live toggle must be DISABLED (the sweep forces dry-run for mirrors). */
export interface MoCResolvedArtifact extends MoCRowResolution {
  artifact_id: string
  is_mirror?: boolean
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
  /** Live-promotion state (T-2.1b r117; surfaced T-2.1c). True = the sweep
   * fires this trigger with REAL effects (when the task is compiled — a mirror
   * fires dry-run regardless, the §6 guard). Drives the Live/Dry-run badge. */
  is_live?: boolean
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
  /** Scope identity (MoC Tenant View): the merged tenant view labels
   * tenant_override rows so they're never confused with the defaults. */
  scope?: MoCScope
  tenant_id?: string | null
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
 * through the cards' resolver. Empty array when no tasks are seeded.
 * H-2: `scope="platform_default"` (vertical omitted) reads the platform's
 * vertical-less tasks — the platform page's table. */
export async function readTaskCatalog(params: {
  vertical?: string
  tenant_id?: string
  scope?: MoCScope
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
  /** Omit/null for a platform_default (vertical-less) task — H-2. */
  vertical?: string | null
  name: string
  scope?: MoCScope
  /** Tenant View: an Add-task while a tenant is selected creates that tenant's
   * override (scope="tenant_override" + tenant_id) — never silently a
   * vertical-wide default. */
  tenant_id?: string | null
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
  /** T-2.1c live promotion — true = the sweep fires REAL effects (compiled
   * tasks only; mirrors stay dry-run per the §6 guard). */
  is_live: boolean
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

// ── Schedule-run previews (T-2.1a log; T-2.1c per-trigger latest) ──────

/** One MoC schedule fire from the run log — the "would do X" records are the
 * engine's own dry-run preview (the honest effect content the go-live confirm
 * shows). */
export interface MoCScheduleRun {
  run_id: string
  task_name: string | null
  moc_task_trigger_id: string | null
  company_id: string
  status: string
  is_dry_run: boolean
  intended_fire: string | null
  started_at: string | null
  would_do: string[]
  /** T-2.2b — the unified fires log: which path fired it + event provenance. */
  source?: "schedule" | "event"
  event_key?: string | null
  event_id?: string | null
}

/** MoC fires (schedule + event), optionally scoped to one tenant — the tenant
 * MoC's fires card (H-1). */
export async function listMoCFires(params?: {
  limit?: number
  company_id?: string
}): Promise<MoCScheduleRun[]> {
  const { data } = await adminApi.get<MoCScheduleRun[]>(`${BASE}/schedule-runs`, {
    params,
  })
  return data
}

/** The LATEST schedule-run for a trigger (or null if it has never fired) —
 * feeds the go-live confirm's evidence. A dry-run preview is the honest
 * content; no run yet → the confirm shows the no-preview fallback (never a
 * fabricated effect description). */
export async function getLatestScheduleRun(
  triggerId: string,
): Promise<MoCScheduleRun | null> {
  const { data } = await adminApi.get<MoCScheduleRun[]>(`${BASE}/schedule-runs`, {
    params: { trigger_id: triggerId, limit: 1 },
  })
  return data[0] ?? null
}

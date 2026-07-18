/**
 * The Bridgeable Map — tenant MoC service (Tenant Ponder-Editor P2).
 *
 * The tenant implementations of the PonderService contract (apiClient →
 * /api/v1/moc/*, company-scoped server-side) + the map's own reads (the
 * merged task view) + the prompted fork. Types are shared with the admin
 * service module — the shapes are realm-agnostic; only the transport and
 * scoping differ.
 */
import apiClient from "@/lib/api-client"
import type { PonderService } from "@/bridgeable-admin/components/moc/ponder-service-context"
import type {
  MoCTrigger,
  MoCTriggerEvent,
  PonderScript,
  PonderUserHit,
  TaskOffer,
} from "@/bridgeable-admin/services/moc-service"

/** One merged-view task row (the backend's resolve_task shape, lean view). */
export interface MapTask {
  id: string
  name: string
  icon?: string | null
  frequency?: string | null
  derived_frequency?: string | null
  task_type?: string | null
  description?: string | null
  display_order: number
  scope: "platform_default" | "vertical_default" | "tenant_override"
  tenant_id?: string | null
  forked_from_task_id?: string | null
  workflow?: { exists: boolean; available: boolean; label: string; is_mirror?: boolean } | null
  triggers: MoCTrigger[]
  /** P3 offer-reach: the live offer on THEIR forked row (pending → badge;
   * declined → the recallable gap chip). */
  offer_state?: { offer_id: string; offer_status: "pending" | "declined" }
  /** T-0 authority: who makes this task fire + the truth sentence when
   * the standard scheduler does. */
  schedule_authority?: "runtime_scheduler" | "moc"
  runtime_schedule_summary?: string | null
}

// ── JOBS (displayed Tasks) — the map's leading unit (Reframe R-2) ────────

export interface MapJobRef {
  kind: "automation" | "triage_queue" | "focus"
  key: string
  label: string
  ref_id: string
  href?: string
  automation?: MapTask
}

export interface MapJob {
  id: string
  name: string
  icon?: string | null
  description?: string | null
  task_type?: string | null
  display_order: number
  refs: MapJobRef[]
  dead_refs: Array<{ id: string; kind: string; key: string }>
  glance: {
    automation_count: number
    live_count: number
    /** Permission-aware — null renders as honest absence, never zero. */
    queue_pending: number | null
  }
}

export async function getMapJobs(): Promise<{ vertical: string | null; jobs: MapJob[] }> {
  const { data } = await apiClient.get("/moc/jobs")
  return data
}

// ── Offer-reach (P3) — the standard's improvements reach their version ──

export async function getTaskOffer(offerId: string): Promise<TaskOffer> {
  const { data } = await apiClient.get(`/moc/offers/${offerId}`)
  return data
}

export async function acceptTaskOffer(
  offerId: string, choices: Record<string, "keep" | "take">,
): Promise<{ task_id: string; applied: string[]; kept: string[] }> {
  const { data } = await apiClient.post(`/moc/offers/${offerId}/accept`, { choices })
  return data
}

export async function declineTaskOffer(offerId: string): Promise<{ status: string }> {
  const { data } = await apiClient.post(`/moc/offers/${offerId}/decline`)
  return data
}

export async function getMapTasks(): Promise<{ vertical: string | null; tasks: MapTask[] }> {
  const { data } = await apiClient.get("/moc/tasks")
  return data
}

/** THE PROMPTED FORK — make the shared task theirs (idempotent). */
export async function forkTask(taskId: string): Promise<MapTask> {
  const { data } = await apiClient.post(`/moc/tasks/${taskId}/fork`)
  return data
}

/** TENANT ADD (The Sunnycrest Workshop) — scope is the SERVER's decision
 * (forced tenant_override; the coherence guard). Born bare. */
export async function createMapTask(input: {
  name: string
  description?: string | null
  task_type?: string | null
  frequency?: string | null
}): Promise<MapTask> {
  const { data } = await apiClient.post("/moc/tasks", input)
  return data
}

/** The vocabulary visible to this tenant's vertical (the add dialog's
 * section options). */
export async function getMapVocabulary(
  kind?: "type" | "frequency",
): Promise<Array<{ id: string; kind: string; value: string; vertical: string | null }>> {
  const { data } = await apiClient.get("/moc/vocabulary", { params: { kind } })
  return data
}

export const tenantPonderService: PonderService = {
  getPonderScript: async (taskId: string): Promise<PonderScript> => {
    // Map Home — the composition ponders ride the same overlay via key
    // prefixes: "area:<Area>" and "onboarding:<key>" route to their own
    // derivers; plain ids stay the task ponder.
    if (taskId.startsWith("area:")) {
      const { data } = await apiClient.get(
        `/moc/area-ponder/${encodeURIComponent(taskId.slice(5))}`,
      )
      return data
    }
    if (taskId.startsWith("onboarding:")) {
      const { data } = await apiClient.get(
        `/moc/onboarding/${encodeURIComponent(taskId.slice(11))}`,
      )
      return data
    }
    if (taskId.startsWith("integration:")) {
      const { data } = await apiClient.get(
        `/moc/integration-ponder/${encodeURIComponent(taskId.slice(12))}`,
      )
      return data
    }
    if (taskId.startsWith("job:")) {
      const { data } = await apiClient.get(
        `/moc/job-ponder/${encodeURIComponent(taskId.slice(4))}`,
      )
      return data
    }
    const { data } = await apiClient.get(`/moc/ponder/${taskId}`)
    return data
  },
  savePonderCaption: async (taskId, beatKey, text) => {
    if (
      taskId.startsWith("area:") || taskId.startsWith("onboarding:") ||
      taskId.startsWith("job:") || taskId.startsWith("integration:")
    ) {
      // Platform pedagogy — tenants VIEW, never author (the overlay's
      // canEdit is false for these; this is defense in depth).
      throw new Error("Platform pedagogy is authored platform-side")
    }
    const { data } = await apiClient.patch(`/moc/ponder/${taskId}/captions`, {
      beat_key: beatKey, text,
    })
    return data.captions
  },
  getPonderDocumentPreview: async (templateKey) => {
    const { data } = await apiClient.get("/moc/ponder/document-preview", {
      params: { template_key: templateKey },
    })
    return data
  },
  addTaskTrigger: async (taskId, input): Promise<MoCTrigger> => {
    const { data } = await apiClient.post(`/moc/tasks/${taskId}/triggers`, input)
    return data
  },
  patchTrigger: async (triggerId, input): Promise<MoCTrigger> => {
    const { data } = await apiClient.patch(`/moc/triggers/${triggerId}`, input)
    return data
  },
  deleteTrigger: async (triggerId) => {
    await apiClient.delete(`/moc/triggers/${triggerId}`)
  },
  listTriggerEvents: async (): Promise<MoCTriggerEvent[]> => {
    // The backend scopes to the tenant's vertical — no param needed.
    const { data } = await apiClient.get("/moc/trigger-events")
    return data
  },
  setPonderWorkflowParam: async (workflowId, stepKey, paramKey, value) => {
    // The TENANT param write — the existing Phase 8a route: writes THEIR
    // override row (field-granular overlay under the shared workflow).
    const { data } = await apiClient.put(
      `/workflows/${workflowId}/params/${stepKey}/${paramKey}`,
      { current_value: value },
    )
    return data
  },
  searchPonderUsers: async (q): Promise<PonderUserHit[]> => {
    const { data } = await apiClient.get("/moc/ponder/users", { params: { q } })
    return data
  },
  studioLinks: false, // Studio is a platform door — tenant exhibits don't link out
}

// ── The Map Home campaign — engagement + suggestions ────────────────────

export interface MapSuggestion {
  id: string
  rule: "onboarding" | "role_area" | "recency" | "job_recency" | "setup"
  title: string
  /** LOAD-BEARING: the honest reason this card exists. Always present. */
  why: string
  ponder_key: string
  /** B-3 — the NAV-CAPABLE variant: present = the card navigates instead
   * of opening a ponder (the setup suggestion). */
  href?: string
}

export async function getSuggestions(): Promise<MapSuggestion[]> {
  const { data } = await apiClient.get("/moc/suggestions")
  return data
}

/** THE QUIET WRITE — fire-and-forget; the UI never waits on it. */
export function recordEngagement(
  ponderKey: string, event: "viewed" | "completed" | "dismissed",
): void {
  void apiClient
    .post("/moc/engagement", { ponder_key: ponderKey, event })
    .catch(() => {})
}

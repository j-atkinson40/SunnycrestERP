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

export const tenantPonderService: PonderService = {
  getPonderScript: async (taskId: string): Promise<PonderScript> => {
    const { data } = await apiClient.get(`/moc/ponder/${taskId}`)
    return data
  },
  savePonderCaption: async (taskId, beatKey, text) => {
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

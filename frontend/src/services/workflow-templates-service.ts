/**
 * Workflow Templates API client — Phase 4 of the Admin Visual
 * Editor.
 *
 * Wraps `/api/v1/admin/workflow-templates/*`. Mirrors
 * `themes-service` (Phase 2) + `component-configurations-service`
 * (Phase 3) typing patterns.
 */

import apiClient from "@/lib/api-client"


export type WorkflowScope = "platform_default" | "vertical_default"


// ─── Canvas state shape ─────────────────────────────────────────


export interface CanvasNode {
  id: string
  type: string
  label?: string
  position: { x: number; y: number }
  config: Record<string, unknown>
}


export interface CanvasEdge {
  id: string
  source: string
  target: string
  label?: string
  condition?: string
  is_iteration?: boolean
}


export interface CanvasTrigger {
  trigger_type:
    | "manual"
    | "event"
    | "scheduled"
    | "time_after_event"
    | "time_of_day"
  trigger_config: Record<string, unknown>
}


export interface CanvasState {
  version: number
  trigger?: CanvasTrigger
  nodes: CanvasNode[]
  edges: CanvasEdge[]
}


export const EMPTY_CANVAS: CanvasState = {
  version: 1,
  nodes: [],
  edges: [],
}


// ─── API records ────────────────────────────────────────────────


export interface WorkflowTemplateMetadata {
  id: string
  scope: WorkflowScope
  vertical: string | null
  workflow_type: string
  display_name: string
  description: string | null
  version: number
  is_active: boolean
  created_at: string
  updated_at: string
  created_by: string | null
  updated_by: string | null
}


export interface WorkflowTemplateFull extends WorkflowTemplateMetadata {
  canvas_state: Partial<CanvasState>
}


export interface TenantWorkflowFork {
  id: string
  tenant_id: string
  workflow_type: string
  forked_from_template_id: string | null
  forked_from_version: number
  canvas_state: Partial<CanvasState>
  pending_merge_available: boolean
  pending_merge_template_id: string | null
  version: number
  is_active: boolean
  created_at: string
  updated_at: string
}


export interface ResolvedWorkflow {
  workflow_type: string
  vertical: string | null
  tenant_id: string | null
  source: "tenant_fork" | "vertical_default" | "platform_default" | null
  source_id: string | null
  source_version: number | null
  canvas_state: Partial<CanvasState>
  pending_merge_available: boolean
}


export interface ListTemplatesParams {
  scope?: WorkflowScope
  vertical?: string
  workflow_type?: string
  include_inactive?: boolean
}


export const workflowTemplatesService = {
  async list(
    params: ListTemplatesParams = {},
  ): Promise<WorkflowTemplateMetadata[]> {
    const response = await apiClient.get<WorkflowTemplateMetadata[]>(
      "/admin/workflow-templates/",
      { params },
    )
    return response.data
  },

  async get(id: string): Promise<WorkflowTemplateFull> {
    const response = await apiClient.get<WorkflowTemplateFull>(
      `/admin/workflow-templates/${id}`,
    )
    return response.data
  },

  async getDependentForks(
    template_id: string,
  ): Promise<TenantWorkflowFork[]> {
    const response = await apiClient.get<TenantWorkflowFork[]>(
      `/admin/workflow-templates/${template_id}/dependent-forks`,
    )
    return response.data
  },

  async create(input: {
    scope: WorkflowScope
    vertical?: string | null
    workflow_type: string
    display_name: string
    description?: string | null
    canvas_state: Partial<CanvasState>
    notify_forks?: boolean
  }): Promise<WorkflowTemplateFull> {
    const response = await apiClient.post<WorkflowTemplateFull>(
      "/admin/workflow-templates/",
      input,
    )
    return response.data
  },

  async update(
    id: string,
    patch: {
      display_name?: string
      description?: string | null
      canvas_state?: Partial<CanvasState>
      notify_forks?: boolean
    },
  ): Promise<WorkflowTemplateFull> {
    const response = await apiClient.patch<WorkflowTemplateFull>(
      `/admin/workflow-templates/${id}`,
      patch,
    )
    return response.data
  },

  async forkForTenant(
    template_id: string,
    tenant_id: string,
  ): Promise<TenantWorkflowFork> {
    const response = await apiClient.post<TenantWorkflowFork>(
      `/admin/workflow-templates/${template_id}/fork`,
      { tenant_id },
    )
    return response.data
  },

  async listForks(params: {
    tenant_id?: string
    workflow_type?: string
    include_inactive?: boolean
  } = {}): Promise<TenantWorkflowFork[]> {
    const response = await apiClient.get<TenantWorkflowFork[]>(
      "/admin/workflow-templates/forks/",
      { params },
    )
    return response.data
  },

  async acceptMerge(fork_id: string): Promise<TenantWorkflowFork> {
    const response = await apiClient.post<TenantWorkflowFork>(
      `/admin/workflow-templates/forks/${fork_id}/accept-merge`,
    )
    return response.data
  },

  async rejectMerge(fork_id: string): Promise<TenantWorkflowFork> {
    const response = await apiClient.post<TenantWorkflowFork>(
      `/admin/workflow-templates/forks/${fork_id}/reject-merge`,
    )
    return response.data
  },

  async resolve(params: {
    workflow_type: string
    vertical?: string | null
    tenant_id?: string | null
  }): Promise<ResolvedWorkflow> {
    const response = await apiClient.get<ResolvedWorkflow>(
      "/admin/workflow-templates/resolve",
      { params },
    )
    return response.data
  },
}

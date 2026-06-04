/**
 * Workflow Templates API client — Phase 4 of the Admin Visual
 * Editor.
 *
 * Wraps `/api/v1/api/platform/admin/visual-editor/workflows/*`. Mirrors
 * `themes-service` (Phase 2) + `component-configurations-service`
 * (Phase 3) typing patterns.
 */

import { adminApi } from "@/bridgeable-admin/lib/admin-api"


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


// ─── Container overlay (visual-containers arc) ───────────────────
//
// Container-arc Phase 1 (2026-06-04) — visual grouping overlay on the
// flat graph. Containers do NOT change nodes/edges (they stay the truth);
// a container is additive metadata enclosing a set of members.
//
// The member shape is a DISCRIMINATED union — nesting-READY from Phase 1.
// Phases 1/2 produce ONLY `kind:"node"` members (FLAT behavior); the
// `kind:"container"` case is type-allowed but UNPRODUCED until Phase 3
// (nested containers) — so Phase 3 adds nesting with no schema change /
// migration. See DECISIONS.md 2026-06-04 + docs/investigations/
// workflow_containers_investigation.md §2.
export interface ContainerMember {
  kind: "node" | "container"
  id: string
}


export interface WorkflowContainer {
  id: string
  label?: string
  members: ContainerMember[]
  // Expanded (false) vs collapsed (true). Phase 1 ships the field but
  // does NOT read it (containers render as expanded labeled regions);
  // Phase 2 adds collapse/edge-rerouting behavior — schema already here.
  collapsed: boolean
}


export interface CanvasState {
  version: number
  trigger?: CanvasTrigger
  nodes: CanvasNode[]
  edges: CanvasEdge[]
  // Optional overlay — omitted on every pre-container draft (back-compat).
  containers?: WorkflowContainer[]
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
    const response = await adminApi.get<WorkflowTemplateMetadata[]>(
      "/api/platform/admin/visual-editor/workflows/",
      { params },
    )
    return response.data
  },

  async get(id: string): Promise<WorkflowTemplateFull> {
    const response = await adminApi.get<WorkflowTemplateFull>(
      `/api/platform/admin/visual-editor/workflows/${id}`,
    )
    return response.data
  },

  async getDependentForks(
    template_id: string,
  ): Promise<TenantWorkflowFork[]> {
    const response = await adminApi.get<TenantWorkflowFork[]>(
      `/api/platform/admin/visual-editor/workflows/${template_id}/dependent-forks`,
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
    const response = await adminApi.post<WorkflowTemplateFull>(
      "/api/platform/admin/visual-editor/workflows/",
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
    const response = await adminApi.patch<WorkflowTemplateFull>(
      `/api/platform/admin/visual-editor/workflows/${id}`,
      patch,
    )
    return response.data
  },

  async forkForTenant(
    template_id: string,
    tenant_id: string,
  ): Promise<TenantWorkflowFork> {
    const response = await adminApi.post<TenantWorkflowFork>(
      `/api/platform/admin/visual-editor/workflows/${template_id}/fork`,
      { tenant_id },
    )
    return response.data
  },

  async listForks(params: {
    tenant_id?: string
    workflow_type?: string
    include_inactive?: boolean
  } = {}): Promise<TenantWorkflowFork[]> {
    const response = await adminApi.get<TenantWorkflowFork[]>(
      "/api/platform/admin/visual-editor/workflows/forks/",
      { params },
    )
    return response.data
  },

  async acceptMerge(fork_id: string): Promise<TenantWorkflowFork> {
    const response = await adminApi.post<TenantWorkflowFork>(
      `/api/platform/admin/visual-editor/workflows/forks/${fork_id}/accept-merge`,
    )
    return response.data
  },

  async rejectMerge(fork_id: string): Promise<TenantWorkflowFork> {
    const response = await adminApi.post<TenantWorkflowFork>(
      `/api/platform/admin/visual-editor/workflows/forks/${fork_id}/reject-merge`,
    )
    return response.data
  },

  async resolve(params: {
    workflow_type: string
    vertical?: string | null
    tenant_id?: string | null
  }): Promise<ResolvedWorkflow> {
    const response = await adminApi.get<ResolvedWorkflow>(
      "/api/platform/admin/visual-editor/workflows/resolve",
      { params },
    )
    return response.data
  },
}

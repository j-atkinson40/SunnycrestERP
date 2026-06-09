/**
 * Workflow authoring service — Builder AI Assistant Phase 1b (frontend client).
 *
 * Calls the PLATFORM-realm generation route added in 1b
 * (`/api/platform/admin/visual-editor/workflow-authoring/generate`) via
 * `adminApi` — the Studio Workflow editor runs in the platform-admin realm.
 * The route is a thin wrapper over the realm-agnostic 1a service
 * (`company_id=None`); generation is grounded server-side by vertical +
 * workflow_type. The proven-green 1a generation path (validator-pass across
 * flat / branching / parallel shapes).
 *
 * NOTE the realm: this uses `adminApi` (platform), NOT `apiClient` (tenant) —
 * the tenant route at /api/v1/workflow-authoring/* exists too but isn't
 * reachable from the platform-authed Studio session.
 */
import { adminApi } from "@/bridgeable-admin/lib/admin-api"
import type { CanvasState } from "@/bridgeable-admin/services/workflow-templates-service"

export interface GenerateWorkflowRequest {
  nl: string
  vertical: string
  workflow_type: string
  /** Omit to generate fresh (1b scope = from-scratch). */
  current_canvas_state?: CanvasState | null
}

/**
 * The service response shape — mirrors the platform route's GenerateResponse.
 * The service NEVER 500s (1a hotfix #2): a failed/unconfigured generation
 * surfaces as `valid=false` + `ai_status="error"` + a `validation_error`
 * string, which the rail renders as a friendly message — never a crash.
 */
export interface GenerateWorkflowResponse {
  canvas_state: CanvasState | null
  valid: boolean
  validation_error: string | null
  ai_status: string
  ai_execution_id: string | null
  ai_latency_ms: number | null
  model_used: string | null
}

export const workflowAuthoringService = {
  /**
   * NL → a validated candidate canvas_state. The promise resolves with the
   * structured verdict even when generation failed (valid=false) — the caller
   * decides how to surface it. It rejects only on a transport/HTTP error.
   */
  async generate(
    req: GenerateWorkflowRequest,
  ): Promise<GenerateWorkflowResponse> {
    const response = await adminApi.post<GenerateWorkflowResponse>(
      "/api/platform/admin/visual-editor/workflow-authoring/generate",
      {
        nl: req.nl,
        vertical: req.vertical,
        workflow_type: req.workflow_type,
        current_canvas_state: req.current_canvas_state ?? null,
      },
    )
    return response.data
  },
}

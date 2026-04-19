import apiClient from "@/lib/api-client";
import type {
  ActivateRequest,
  AuditLogEntry,
  CallerModuleOption,
  DraftCreateRequest,
  DraftUpdateRequest,
  EditPermissionResponse,
  ExecutionListItem,
  ExecutionResponse,
  ExperimentCreateRequest,
  ExperimentListItem,
  ExperimentPromoteRequest,
  ExperimentResponse,
  ExperimentResultsResponse,
  ExperimentStopRequest,
  ListExecutionsParams,
  ListExperimentsParams,
  ListPromptsParams,
  ModelRouteResponse,
  OverallStatsResponse,
  PromptDetailResponse,
  PromptListItem,
  PromptStatsResponse,
  PromptVersionResponse,
  RollbackRequest,
  TestRunRequest,
} from "@/types/intelligence";

/**
 * Client for /api/v1/intelligence/* admin endpoints.
 *
 * Note: Phase 3a spec proposed /api/v1/admin/intelligence/* but we extend
 * the existing /api/v1/intelligence/* prefix ("Extend where needed; don't
 * duplicate"). All endpoints are admin-only at the backend via
 * `require_admin`; the frontend enforces access via `ProtectedRoute adminOnly`.
 */
export const intelligenceService = {
  // ─── Prompts ────────────────────────────────────────────────────────────

  async listPrompts(params: ListPromptsParams = {}): Promise<PromptListItem[]> {
    const qs = new URLSearchParams();
    if (params.domain) qs.set("domain", params.domain);
    if (params.search) qs.set("search", params.search);
    if (params.caller_module) qs.set("caller_module", params.caller_module);
    if (params.model_preference) qs.set("model_preference", params.model_preference);
    if (params.is_active !== undefined) qs.set("is_active", String(params.is_active));
    qs.set("limit", String(params.limit ?? 200));
    qs.set("offset", String(params.offset ?? 0));
    const res = await apiClient.get<PromptListItem[]>(
      `/intelligence/prompts?${qs.toString()}`
    );
    return res.data;
  },

  async getPrompt(promptId: string): Promise<PromptDetailResponse> {
    const res = await apiClient.get<PromptDetailResponse>(
      `/intelligence/prompts/${promptId}`
    );
    return res.data;
  },

  async getPromptVersion(
    promptId: string,
    versionId: string
  ): Promise<PromptVersionResponse> {
    const res = await apiClient.get<PromptVersionResponse>(
      `/intelligence/prompts/${promptId}/versions/${versionId}`
    );
    return res.data;
  },

  async getPromptStats(promptId: string, days = 30): Promise<PromptStatsResponse> {
    const res = await apiClient.get<PromptStatsResponse>(
      `/intelligence/stats/prompt/${promptId}?days=${days}`
    );
    return res.data;
  },

  // ─── Executions ─────────────────────────────────────────────────────────

  async listExecutions(
    params: ListExecutionsParams = {}
  ): Promise<ExecutionListItem[]> {
    const qs = new URLSearchParams();
    if (params.prompt_key) qs.set("prompt_key", params.prompt_key);
    if (params.caller_module) qs.set("caller_module", params.caller_module);
    if (params.caller_entity_type) qs.set("caller_entity_type", params.caller_entity_type);
    if (params.caller_entity_id) qs.set("caller_entity_id", params.caller_entity_id);
    if (params.status) qs.set("status", params.status);
    if (params.company_id) qs.set("company_id", params.company_id);
    if (params.since_days !== undefined) qs.set("since_days", String(params.since_days));
    if (params.start_date) qs.set("start_date", params.start_date);
    if (params.end_date) qs.set("end_date", params.end_date);
    if (params.sort) qs.set("sort", params.sort);
    qs.set("limit", String(params.limit ?? 100));
    qs.set("offset", String(params.offset ?? 0));
    const res = await apiClient.get<ExecutionListItem[]>(
      `/intelligence/executions?${qs.toString()}`
    );
    return res.data;
  },

  async getExecution(executionId: string): Promise<ExecutionResponse> {
    const res = await apiClient.get<ExecutionResponse>(
      `/intelligence/executions/${executionId}`
    );
    return res.data;
  },

  // ─── Model Routes ───────────────────────────────────────────────────────

  async listModelRoutes(): Promise<ModelRouteResponse[]> {
    const res = await apiClient.get<ModelRouteResponse[]>("/intelligence/models");
    return res.data;
  },

  // ─── Stats ──────────────────────────────────────────────────────────────

  async getOverallStats(days = 30): Promise<OverallStatsResponse> {
    const res = await apiClient.get<OverallStatsResponse>(
      `/intelligence/stats/overall?days=${days}`
    );
    return res.data;
  },

  async listCallerModules(sinceDays = 30): Promise<CallerModuleOption[]> {
    const res = await apiClient.get<CallerModuleOption[]>(
      `/intelligence/caller-modules?since_days=${sinceDays}`
    );
    return res.data;
  },

  // ─── Phase 3b — Editing ─────────────────────────────────────────────────

  async getEditPermission(promptId: string): Promise<EditPermissionResponse> {
    const res = await apiClient.get<EditPermissionResponse>(
      `/intelligence/prompts/${promptId}/edit-permission`
    );
    return res.data;
  },

  async createDraft(
    promptId: string,
    body: DraftCreateRequest = {}
  ): Promise<PromptVersionResponse> {
    const res = await apiClient.post<PromptVersionResponse>(
      `/intelligence/prompts/${promptId}/versions/draft`,
      body
    );
    return res.data;
  },

  async updateDraft(
    promptId: string,
    versionId: string,
    body: DraftUpdateRequest
  ): Promise<PromptVersionResponse> {
    const res = await apiClient.patch<PromptVersionResponse>(
      `/intelligence/prompts/${promptId}/versions/${versionId}`,
      body
    );
    return res.data;
  },

  async deleteDraft(promptId: string, versionId: string): Promise<void> {
    await apiClient.delete(
      `/intelligence/prompts/${promptId}/versions/${versionId}`
    );
  },

  async activateDraft(
    promptId: string,
    versionId: string,
    body: ActivateRequest
  ): Promise<PromptVersionResponse> {
    const res = await apiClient.post<PromptVersionResponse>(
      `/intelligence/prompts/${promptId}/versions/${versionId}/activate-edit`,
      body
    );
    return res.data;
  },

  async rollback(
    promptId: string,
    versionId: string,
    body: RollbackRequest
  ): Promise<PromptVersionResponse> {
    const res = await apiClient.post<PromptVersionResponse>(
      `/intelligence/prompts/${promptId}/versions/${versionId}/rollback`,
      body
    );
    return res.data;
  },

  async testRun(
    promptId: string,
    versionId: string,
    body: TestRunRequest
  ): Promise<ExecutionResponse> {
    const res = await apiClient.post<ExecutionResponse>(
      `/intelligence/prompts/${promptId}/versions/${versionId}/test-run`,
      body
    );
    return res.data;
  },

  async listAuditLog(
    promptId: string,
    limit = 50,
    offset = 0
  ): Promise<AuditLogEntry[]> {
    const res = await apiClient.get<AuditLogEntry[]>(
      `/intelligence/prompts/${promptId}/audit?limit=${limit}&offset=${offset}`
    );
    return res.data;
  },

  // ─── Phase 3c — Experiments ─────────────────────────────────────────────

  async listExperiments(
    params: ListExperimentsParams = {}
  ): Promise<ExperimentListItem[]> {
    const qs = new URLSearchParams();
    if (params.status) qs.set("status", params.status);
    if (params.prompt_id) qs.set("prompt_id", params.prompt_id);
    qs.set("limit", String(params.limit ?? 100));
    qs.set("offset", String(params.offset ?? 0));
    const res = await apiClient.get<ExperimentListItem[]>(
      `/intelligence/experiments?${qs.toString()}`
    );
    return res.data;
  },

  async getExperiment(experimentId: string): Promise<ExperimentResponse> {
    const res = await apiClient.get<ExperimentResponse>(
      `/intelligence/experiments/${experimentId}`
    );
    return res.data;
  },

  async getExperimentResults(
    experimentId: string
  ): Promise<ExperimentResultsResponse> {
    const res = await apiClient.get<ExperimentResultsResponse>(
      `/intelligence/experiments/${experimentId}/results`
    );
    return res.data;
  },

  async createExperiment(
    body: ExperimentCreateRequest
  ): Promise<ExperimentResponse> {
    const res = await apiClient.post<ExperimentResponse>(
      `/intelligence/experiments`,
      body
    );
    return res.data;
  },

  async startExperiment(experimentId: string): Promise<ExperimentResponse> {
    const res = await apiClient.post<ExperimentResponse>(
      `/intelligence/experiments/${experimentId}/start`
    );
    return res.data;
  },

  async stopExperiment(
    experimentId: string,
    body: ExperimentStopRequest
  ): Promise<ExperimentResponse> {
    const res = await apiClient.post<ExperimentResponse>(
      `/intelligence/experiments/${experimentId}/stop`,
      body
    );
    return res.data;
  },

  async promoteExperiment(
    experimentId: string,
    body: ExperimentPromoteRequest
  ): Promise<ExperimentResponse> {
    const res = await apiClient.post<ExperimentResponse>(
      `/intelligence/experiments/${experimentId}/promote`,
      body
    );
    return res.data;
  },
};

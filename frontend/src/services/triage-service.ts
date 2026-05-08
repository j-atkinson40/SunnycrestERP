/**
 * Triage service — thin axios client for `/api/v1/triage/*`.
 *
 * Nine endpoints from `backend/app/api/routes/triage.py`. Each
 * function returns the backend response body unwrapped (axios
 * `response.data`). All errors surface as axios errors — callers
 * translate 204 (no pending items) on `next_item` specifically.
 */

import apiClient from "@/lib/api-client";
import type {
  TriageActionResult,
  TriageItem,
  TriageQueueConfig,
  TriageQuestionAnswer,
  TriageRateLimitedBody,
  TriageSessionSummary,
} from "@/types/triage";

export interface TriageQueueSummary {
  queue_id: string;
  queue_name: string;
  description: string;
  item_entity_type: string;
  display_order: number;
  schema_version: string;
}

export interface TriageQueueConfigResponse {
  queue_id: string;
  queue_name: string;
  config: TriageQueueConfig;
}

export interface ApplyActionPayload {
  action_id: string;
  reason?: string | null;
  reason_code?: string | null;
  note?: string | null;
  payload?: Record<string, unknown> | null;
}

export interface SnoozePayload {
  wake_at?: string | null;      // ISO datetime
  offset_hours?: number | null; // 1-720
  reason?: string | null;
}

export async function listQueues(): Promise<TriageQueueSummary[]> {
  const { data } = await apiClient.get<TriageQueueSummary[]>("/triage/queues");
  return data;
}

export async function getQueueConfig(
  queueId: string,
): Promise<TriageQueueConfigResponse> {
  const { data } = await apiClient.get<TriageQueueConfigResponse>(
    `/triage/queues/${encodeURIComponent(queueId)}`,
  );
  return data;
}

export async function getQueueCount(
  queueId: string,
): Promise<{ queue_id: string; count: number }> {
  const { data } = await apiClient.get<{ queue_id: string; count: number }>(
    `/triage/queues/${encodeURIComponent(queueId)}/count`,
  );
  return data;
}

export async function startSession(
  queueId: string,
): Promise<TriageSessionSummary> {
  const { data } = await apiClient.post<TriageSessionSummary>(
    `/triage/queues/${encodeURIComponent(queueId)}/sessions`,
  );
  return data;
}

export async function getSession(
  sessionId: string,
): Promise<TriageSessionSummary> {
  const { data } = await apiClient.get<TriageSessionSummary>(
    `/triage/sessions/${encodeURIComponent(sessionId)}`,
  );
  return data;
}

/**
 * Returns the next item in the session. Resolves with `null` when
 * the backend returns 204 (queue exhausted).
 */
export async function fetchNextItem(
  sessionId: string,
): Promise<TriageItem | null> {
  const response = await apiClient.post<TriageItem>(
    `/triage/sessions/${encodeURIComponent(sessionId)}/next`,
    undefined,
    { validateStatus: (s) => s === 200 || s === 204 },
  );
  if (response.status === 204) return null;
  return response.data;
}

export async function applyAction(
  sessionId: string,
  itemId: string,
  payload: ApplyActionPayload,
): Promise<TriageActionResult> {
  const { data } = await apiClient.post<TriageActionResult>(
    `/triage/sessions/${encodeURIComponent(sessionId)}/items/${encodeURIComponent(itemId)}/action`,
    payload,
  );
  return data;
}

export async function snoozeItem(
  sessionId: string,
  itemId: string,
  payload: SnoozePayload,
): Promise<TriageActionResult> {
  const { data } = await apiClient.post<TriageActionResult>(
    `/triage/sessions/${encodeURIComponent(sessionId)}/items/${encodeURIComponent(itemId)}/snooze`,
    payload,
  );
  return data;
}

export async function endSession(
  sessionId: string,
): Promise<TriageSessionSummary> {
  const { data } = await apiClient.post<TriageSessionSummary>(
    `/triage/sessions/${encodeURIComponent(sessionId)}/end`,
  );
  return data;
}

// ── Follow-up 4 — Related entities for context panel ──────────────

export interface TriageRelatedEntity {
  entity_type: string;
  entity_id: string;
  context: string;
  display_label: string;
  // Pass-through bag from the per-queue builder (status, priority,
  // due_date, etc.). Renderer picks up what it needs.
  extras: Record<string, unknown>;
}

export async function fetchRelatedEntities(
  sessionId: string,
  itemId: string,
): Promise<TriageRelatedEntity[]> {
  const { data } = await apiClient.get<TriageRelatedEntity[]>(
    `/triage/sessions/${encodeURIComponent(sessionId)}/items/${encodeURIComponent(itemId)}/related`,
  );
  return data;
}


// ── Follow-up 2 — AI Question panel ────────────────────────────────

export class TriageRateLimitedError extends Error {
  readonly retryAfterSeconds: number;
  readonly friendlyMessage: string;
  constructor(body: TriageRateLimitedBody) {
    super(body.message);
    this.retryAfterSeconds = body.retry_after_seconds;
    this.friendlyMessage = body.message;
    this.name = "TriageRateLimitedError";
  }
}

/**
 * Ask a natural-language question about the current triage item.
 *
 * On 429 rate-limit responses the backend returns a structured body
 * `{code: "rate_limited", retry_after_seconds, message}`. This
 * function translates that into a typed `TriageRateLimitedError` so
 * the panel can render a friendly toast — callers should catch
 * specifically and display `err.friendlyMessage`.
 */
// ── Phase R-6.0 — workflow review decision ─────────────────────────


export type WorkflowReviewDecision = "approve" | "reject" | "edit_and_approve"


export interface WorkflowReviewDecideResponse {
  item_id: string
  decision: string
  review_focus_id: string
  run_id: string
}


export type CommitWorkflowReviewDecisionResult =
  | { ok: true; data: WorkflowReviewDecideResponse }
  | { ok: false; error: string; status?: number }


/**
 * Commit a decision on a `WorkflowReviewItem`. Routes through the
 * canonical R-6.0a `/api/v1/triage/workflow-review/{item_id}/decide`
 * endpoint, which calls `workflow_review_adapter.commit_decision`
 * and resumes the workflow run via `workflow_engine.advance_run`.
 *
 * Returns a discriminated-union result so callers can render
 * inline error chrome (toast, modal-retain) without throwing.
 */
export async function commitWorkflowReviewDecision(
  itemId: string,
  decision: WorkflowReviewDecision,
  editedData?: Record<string, unknown> | null,
  decisionNotes?: string | null,
): Promise<CommitWorkflowReviewDecisionResult> {
  try {
    const { data } = await apiClient.post<WorkflowReviewDecideResponse>(
      `/triage/workflow-review/${encodeURIComponent(itemId)}/decide`,
      {
        decision,
        edited_data: editedData ?? null,
        decision_notes: decisionNotes ?? null,
      },
    )
    return { ok: true, data }
  } catch (err) {
    const axiosErr = err as {
      response?: { status?: number; data?: { detail?: string } }
      message?: string
    }
    const detail = axiosErr?.response?.data?.detail
    const status = axiosErr?.response?.status
    const message =
      (typeof detail === "string" && detail) ||
      axiosErr?.message ||
      "Decision failed"
    return { ok: false, error: message, status }
  }
}


export async function askQuestion(
  sessionId: string,
  itemId: string,
  question: string,
): Promise<TriageQuestionAnswer> {
  try {
    const { data } = await apiClient.post<TriageQuestionAnswer>(
      `/triage/sessions/${encodeURIComponent(sessionId)}/items/${encodeURIComponent(itemId)}/ask`,
      { question },
    );
    return data;
  } catch (err) {
    const axiosErr = err as {
      response?: { status?: number; data?: { detail?: TriageRateLimitedBody } };
    };
    const detail = axiosErr?.response?.data?.detail;
    if (
      axiosErr?.response?.status === 429 &&
      detail &&
      typeof detail === "object" &&
      detail.code === "rate_limited"
    ) {
      throw new TriageRateLimitedError(detail);
    }
    throw err;
  }
}

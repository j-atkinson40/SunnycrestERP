/**
 * Email classification service — thin axios client for
 * `/api/v1/email-classification/*` (R-6.1a + R-6.1a.1 admin surface).
 *
 * Routes through the canonical tenant-realm `apiClient` (sets the
 * `Authorization` + `X-Company-Slug` headers automatically). Every
 * function returns the backend response body unwrapped (axios
 * `response.data`).
 *
 * ── UI vocabulary vs API vocabulary ────────────────────────────────
 *
 * The backend's URL surface uses `/taxonomy/nodes/*` for what the UI
 * calls "categories". Same entity (`tenant_workflow_email_categories`);
 * different naming to keep the API surface consistent with the
 * underlying schema while user-facing copy reads naturally.
 *
 * This service exposes user-facing names — `listCategories()`,
 * `createCategory()`, `updateCategory()`, `deleteCategory()` — that
 * internally hit `/taxonomy/nodes/*`. The mapping is explicit per
 * function so future maintainers reading the route file can find
 * the matching client method.
 *
 * ── Endpoint inventory (17 total) ──────────────────────────────────
 *
 *   Tier 1 rules (5)         GET POST PATCH DELETE /rules*  + /rules/reorder
 *   Tier 2 categories (4)    GET /taxonomy
 *                            POST PATCH DELETE /taxonomy/nodes*
 *   Tier 3 enrollment (1)    PATCH /workflows/{id}/tier3-enrollment
 *   Audit + replay (4)       GET /classifications + /classifications/{id}
 *                            POST /messages/{id}/replay-classification
 *                            POST /classifications/{id}/route-to-workflow
 *   R-6.1a.1 floors + sup (3) GET PUT /confidence-floors
 *                             POST /classifications/{id}/suppress
 *
 * Update method is PATCH for both rules + taxonomy (matches R-6.1a
 * canonical contract). The user's earlier hand-validation curl with PUT
 * would have 405'd; canonical is PATCH.
 */

import apiClient from "@/lib/api-client";
import type {
  CategoryCreatePayload,
  CategoryUpdatePayload,
  ConfidenceFloors,
  ManualRoutePayload,
  ManualRouteResponse,
  ReplayResponse,
  RuleCreatePayload,
  RuleUpdatePayload,
  SuppressPayload,
  TenantWorkflowEmailCategory,
  TenantWorkflowEmailRule,
  Tier3EnrollmentResponse,
  WorkflowEmailClassification,
} from "@/types/email-classification";

// ── Tier 1 Rules CRUD ───────────────────────────────────────────────

export interface ListRulesParams {
  /** Optional filter to rules whose fire_action.workflow_id matches. */
  workflow_id?: string | null;
}

export async function listRules(
  params: ListRulesParams = {},
): Promise<TenantWorkflowEmailRule[]> {
  const { data } = await apiClient.get<{ rules: TenantWorkflowEmailRule[] }>(
    "/email-classification/rules",
    { params: params.workflow_id ? { workflow_id: params.workflow_id } : undefined },
  );
  return data.rules;
}

export async function createRule(
  payload: RuleCreatePayload,
): Promise<TenantWorkflowEmailRule> {
  const { data } = await apiClient.post<TenantWorkflowEmailRule>(
    "/email-classification/rules",
    payload,
  );
  return data;
}

export async function updateRule(
  ruleId: string,
  payload: RuleUpdatePayload,
): Promise<TenantWorkflowEmailRule> {
  const { data } = await apiClient.patch<TenantWorkflowEmailRule>(
    `/email-classification/rules/${encodeURIComponent(ruleId)}`,
    payload,
  );
  return data;
}

/**
 * Soft-delete (flips `is_active=false`). The R-6.1a backend route
 * preserves the row for audit-trail reasons; the table re-renders
 * with the row collapsed under "Show inactive".
 */
export async function deleteRule(
  ruleId: string,
): Promise<{ deleted: boolean; rule_id: string }> {
  const { data } = await apiClient.delete<{
    deleted: boolean;
    rule_id: string;
  }>(`/email-classification/rules/${encodeURIComponent(ruleId)}`);
  return data;
}

export async function reorderRules(
  ruleIds: string[],
): Promise<{ reordered: boolean; count: number }> {
  const { data } = await apiClient.post<{
    reordered: boolean;
    count: number;
  }>("/email-classification/rules/reorder", { rule_ids: ruleIds });
  return data;
}

// ── Tier 2 Categories CRUD (UI vocab → /taxonomy/nodes/* on API) ────

export async function listCategories(): Promise<
  TenantWorkflowEmailCategory[]
> {
  const { data } = await apiClient.get<{
    categories: TenantWorkflowEmailCategory[];
  }>("/email-classification/taxonomy");
  return data.categories;
}

export async function createCategory(
  payload: CategoryCreatePayload,
): Promise<TenantWorkflowEmailCategory> {
  const { data } = await apiClient.post<TenantWorkflowEmailCategory>(
    "/email-classification/taxonomy/nodes",
    payload,
  );
  return data;
}

export async function updateCategory(
  categoryId: string,
  payload: CategoryUpdatePayload,
): Promise<TenantWorkflowEmailCategory> {
  const { data } = await apiClient.patch<TenantWorkflowEmailCategory>(
    `/email-classification/taxonomy/nodes/${encodeURIComponent(categoryId)}`,
    payload,
  );
  return data;
}

/**
 * Soft-cascade delete: descendants flip inactive too (per R-6.1a
 * `delete_category` route). Returns the deleted node id + the
 * cascaded descendant count.
 */
export async function deleteCategory(
  categoryId: string,
): Promise<{ deleted: boolean; node_id: string; descendants: number }> {
  const { data } = await apiClient.delete<{
    deleted: boolean;
    node_id: string;
    descendants: number;
  }>(
    `/email-classification/taxonomy/nodes/${encodeURIComponent(categoryId)}`,
  );
  return data;
}

// ── Tier 3 enrollment ───────────────────────────────────────────────

/**
 * Toggle a workflow's `tier3_enrolled` flag. R-6.1b's WorkflowBuilder
 * Triggers section consumes this from R-6.1b.b; R-6.1b.a's admin
 * page Triggers tab summarizes the count read-only.
 */
export async function setTier3Enrollment(
  workflowId: string,
  enrolled: boolean,
): Promise<Tier3EnrollmentResponse> {
  const { data } = await apiClient.patch<Tier3EnrollmentResponse>(
    `/email-classification/workflows/${encodeURIComponent(workflowId)}/tier3-enrollment`,
    { enrolled },
  );
  return data;
}

// ── Audit log + replay ──────────────────────────────────────────────

export interface ListClassificationsParams {
  /** Tier filter (1, 2, or 3). */
  tier?: number;
  /** Server hard-cap is 500. */
  limit?: number;
}

export async function listClassifications(
  params: ListClassificationsParams = {},
): Promise<WorkflowEmailClassification[]> {
  const { data } = await apiClient.get<{
    classifications: WorkflowEmailClassification[];
  }>("/email-classification/classifications", { params });
  return data.classifications;
}

export async function getClassification(
  classificationId: string,
): Promise<WorkflowEmailClassification> {
  const { data } = await apiClient.get<WorkflowEmailClassification>(
    `/email-classification/classifications/${encodeURIComponent(classificationId)}`,
  );
  return data;
}

export async function replayClassification(
  messageId: string,
): Promise<ReplayResponse> {
  const { data } = await apiClient.post<ReplayResponse>(
    `/email-classification/messages/${encodeURIComponent(messageId)}/replay-classification`,
  );
  return data;
}

export async function routeClassificationToWorkflow(
  classificationId: string,
  payload: ManualRoutePayload,
): Promise<ManualRouteResponse> {
  const { data } = await apiClient.post<ManualRouteResponse>(
    `/email-classification/classifications/${encodeURIComponent(classificationId)}/route-to-workflow`,
    payload,
  );
  return data;
}

// ── R-6.1a.1 — Confidence floors + suppression ─────────────────────

export async function getConfidenceFloors(): Promise<ConfidenceFloors> {
  const { data } = await apiClient.get<ConfidenceFloors>(
    "/email-classification/confidence-floors",
  );
  return data;
}

export async function putConfidenceFloors(
  floors: ConfidenceFloors,
): Promise<ConfidenceFloors> {
  const { data } = await apiClient.put<ConfidenceFloors>(
    "/email-classification/confidence-floors",
    floors,
  );
  return data;
}

/**
 * Suppress a classified message via the canonical append-only
 * audit-chain endpoint. R-6.1b.a ships this method for completeness;
 * the EmailUnclassifiedItemDisplay wiring lands in R-6.1b.b. No UI
 * consumes this in R-6.1b.a.
 */
export async function suppressClassification(
  classificationId: string,
  payload: SuppressPayload = {},
): Promise<WorkflowEmailClassification> {
  const { data } = await apiClient.post<WorkflowEmailClassification>(
    `/email-classification/classifications/${encodeURIComponent(classificationId)}/suppress`,
    payload,
  );
  return data;
}

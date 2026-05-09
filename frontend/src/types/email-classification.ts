/**
 * Email classification types — Pydantic mirrors of R-6.1a + R-6.1a.1
 * admin endpoint response shapes.
 *
 * The backend resides at `backend/app/api/routes/admin_email_classification.py`
 * and exposes 17 canonical endpoints. Per CLAUDE.md §14 R-6.1a.1 architectural
 * pattern, the user-facing UI vocabulary distinguishes "categories" while the
 * backend's URL surface uses `/taxonomy/nodes/*`. The mapping is documented in
 * `frontend/src/services/email-classification-service.ts` file header.
 */

// ── Tier 1 rule shapes ──────────────────────────────────────────────

/**
 * Canonical match-condition operator vocabulary. The backend's
 * `tier_1_rules.py` evaluator dispatches on these five keys exactly.
 */
export type MatchOperator =
  | "subject_contains_any"
  | "sender_email_in"
  | "sender_domain_in"
  | "body_contains_any"
  | "thread_label_in";

export const MATCH_OPERATORS: readonly MatchOperator[] = [
  "subject_contains_any",
  "sender_email_in",
  "sender_domain_in",
  "body_contains_any",
  "thread_label_in",
] as const;

/**
 * Per-operator JSONB shape: `{ operator_key: [string, ...] }`.
 *
 * Multiple operators in the same record are AND-conjoined at the
 * evaluator. Multiple values inside one operator are OR-conjoined.
 * Inline help in MatchConditionsEditor surfaces both rules.
 */
export type MatchConditions = Partial<Record<MatchOperator, string[]>>;

/**
 * `fire_action.workflow_id` resolves to a tenant-visible workflow id
 * OR is null when the rule suppresses (drops the message). When
 * suppressing, `suppression_reason` carries operator-authored copy.
 */
export interface FireAction {
  workflow_id?: string | null;
  suppression_reason?: string | null;
}

export interface TenantWorkflowEmailRule {
  id: string;
  tenant_id: string;
  priority: number;
  name: string;
  match_conditions: MatchConditions;
  fire_action: FireAction;
  is_active: boolean;
  created_at: string | null;
  updated_at: string | null;
}

export interface RuleCreatePayload {
  name: string;
  priority: number;
  match_conditions: MatchConditions;
  fire_action: FireAction;
  is_active?: boolean;
}

export interface RuleUpdatePayload {
  name?: string;
  priority?: number;
  match_conditions?: MatchConditions;
  fire_action?: FireAction;
  is_active?: boolean;
}

// ── Tier 2 category (taxonomy node) shapes ──────────────────────────

/**
 * Backend table is `tenant_workflow_email_categories`; admin URL
 * surface is `/taxonomy/nodes/*`. UX vocabulary calls them "categories".
 * R-6.1b ships v1 flat (no parent_id tree authoring) — the schema's
 * `parent_id` self-FK is preserved for R-6.x nested-category UX when
 * concrete tenant signal warrants.
 */
export interface TenantWorkflowEmailCategory {
  id: string;
  tenant_id: string;
  parent_id: string | null;
  label: string;
  description: string | null;
  mapped_workflow_id: string | null;
  position: number;
  is_active: boolean;
  created_at: string | null;
  updated_at: string | null;
}

export interface CategoryCreatePayload {
  label: string;
  description?: string | null;
  parent_id?: string | null;
  mapped_workflow_id?: string | null;
  position?: number;
  is_active?: boolean;
}

export interface CategoryUpdatePayload {
  label?: string;
  description?: string | null;
  parent_id?: string | null;
  mapped_workflow_id?: string | null;
  position?: number;
  is_active?: boolean;
}

// ── Tier 3 enrollment ───────────────────────────────────────────────

export interface Tier3EnrollmentResponse {
  workflow_id: string;
  tier3_enrolled: boolean;
}

// ── Confidence floors (R-6.1a.1) ────────────────────────────────────

export interface ConfidenceFloors {
  tier_2: number;
  tier_3: number;
}

// ── Audit log (classifications) ─────────────────────────────────────

export interface WorkflowEmailClassification {
  id: string;
  tenant_id: string;
  email_message_id: string;
  tier: number | null;
  tier1_rule_id: string | null;
  tier2_category_id: string | null;
  tier2_confidence: number | null;
  tier3_confidence: number | null;
  selected_workflow_id: string | null;
  is_suppressed: boolean;
  workflow_run_id: string | null;
  is_replay: boolean;
  replay_of_classification_id: string | null;
  error_message: string | null;
  latency_ms: number | null;
  tier_reasoning: Record<string, unknown>;
  created_at: string | null;
}

export interface ManualRoutePayload {
  workflow_id: string;
  decision_notes?: string | null;
}

export interface SuppressPayload {
  reason?: string | null;
}

export interface ReplayResponse {
  classification_id: string;
  tier: number | null;
  selected_workflow_id: string | null;
  workflow_run_id: string | null;
  is_suppressed: boolean;
}

export interface ManualRouteResponse {
  classification_id: string;
  selected_workflow_id: string | null;
  workflow_run_id: string | null;
}

// ── Workflow summary (read from /workflows/library/all on admin page) ──

/**
 * Subset of the `WorkflowCard` shape from `/workflows/library/all` —
 * the fields WorkflowPicker actually consumes. Kept narrow on purpose
 * so the picker's contract stays minimal even if the library payload
 * adds fields.
 */
export interface WorkflowSummary {
  id: string;
  name: string;
  description: string | null;
  vertical: string | null;
  is_active: boolean;
  tier3_enrolled?: boolean;
}

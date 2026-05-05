/**
 * Calendar Step 4 — operational-action affordance types.
 *
 * Mirror the backend Pydantic shapes in
 * ``backend/app/api/routes/calendar_actions.py``. Keep in sync.
 */

export type CalendarActionType =
  | "service_date_acceptance"
  | "delivery_date_acceptance"
  | "joint_event_acceptance"
  | "recurring_meeting_proposal"
  | "event_reschedule_proposal";

export type CalendarActionOutcome =
  | "accept"
  | "reject"
  | "counter_propose";

export type CalendarActionStatus =
  | "pending"
  | "accepted"
  | "rejected"
  | "counter_proposed";

export type CalendarActionTargetType =
  | "fh_case"
  | "sales_order"
  | "cross_tenant_event"
  | "calendar_event";

export interface CascadeImpact {
  linked_entity_count: number;
  paired_cross_tenant_count: number;
  linked_entities?: Array<{
    linked_entity_type: string;
    linked_entity_id: string;
  }>;
  paired_tenants?: string[];
}

export interface MagicLinkActionDetails {
  tenant_name: string;
  tenant_brand_color: string | null;
  organizer_name: string | null;
  event_subject: string | null;
  event_start_at: string;
  event_end_at: string;
  event_location: string | null;
  action_idx: number;
  action_type: CalendarActionType;
  action_target_type: CalendarActionTargetType;
  action_target_id: string;
  action_metadata: Record<string, unknown>;
  action_status: CalendarActionStatus;
  recipient_email: string;
  expires_at: string;
  consumed: boolean;
  cascade_impact?: CascadeImpact | null;
}

export interface CommitActionRequest {
  outcome: CalendarActionOutcome;
  completion_note?: string;
  counter_proposed_start_at?: string;
  counter_proposed_end_at?: string;
}

export interface CommitActionResponse {
  action_idx: number;
  action_type: CalendarActionType;
  action_status: CalendarActionStatus;
  action_completed_at: string | null;
  action_target_type: CalendarActionTargetType;
  action_target_id: string;
  target_status: string | null;
  counter_action_idx: number | null;
  pairing_id: string | null;
}

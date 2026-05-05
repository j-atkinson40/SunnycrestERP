/**
 * Calendar Account types — Phase W-4b Layer 1 Calendar Step 1.
 *
 * Mirror the backend Pydantic shapes in
 * `backend/app/api/routes/calendar_accounts.py` +
 * `backend/app/api/routes/calendar_events.py`. Keep in sync.
 *
 * Per Q3 confirmed pre-build: only 3 provider types ship at Step 1
 * (CalDAV omitted entirely per canonical deferral). Per Q4: local
 * provider ships functional at Step 1.
 */

export type CalendarAccountType = "shared" | "personal";

export type CalendarProviderType = "google_calendar" | "msgraph" | "local";

export type CalendarAccessLevel = "read" | "read_write" | "admin";

export type EventStatus = "tentative" | "confirmed" | "cancelled";

export type EventTransparency = "opaque" | "transparent";

export type AttendeeRole =
  | "organizer"
  | "required_attendee"
  | "optional_attendee"
  | "chair"
  | "non_participant";

export type AttendeeResponseStatus =
  | "needs_action"
  | "accepted"
  | "declined"
  | "tentative"
  | "delegated";

export type LinkageSource =
  | "manual_pre_link"
  | "manual_post_link"
  | "intelligence_inferred";

export interface CalendarAccount {
  id: string;
  tenant_id: string;
  account_type: CalendarAccountType;
  display_name: string;
  primary_email_address: string;
  provider_type: CalendarProviderType;
  provider_config_keys: string[];
  outbound_enabled: boolean;
  default_event_timezone: string;
  is_active: boolean;
  is_default: boolean;
  // Step 2: sync_status from CalendarAccountSyncState. Pending if no
  // sync state row exists yet (account never synced).
  sync_status: string | null;
  // Step 2: credential lifecycle surfaced for the CalendarAccountsPage
  // status sub-row. None when account hasn't completed OAuth yet.
  last_credential_op?: string | null;
  last_credential_op_at?: string | null;
  backfill_status?: string;
  backfill_progress_pct?: number;
  created_by_user_id: string | null;
  created_at: string;
  updated_at: string;
}

// Step 2 — OAuth flow types
export interface OAuthAuthorizeUrlResponse {
  authorize_url: string;
  state: string;
}

export interface OAuthCallbackRequest {
  provider_type: "google_calendar" | "msgraph";
  code: string;
  state: string;
  redirect_uri: string;
  account_id?: string | null;
  primary_email_address?: string | null;
  display_name?: string | null;
  account_type?: CalendarAccountType;
}

export interface OAuthCallbackResponse {
  account_id: string;
  primary_email_address: string;
  backfill_status: string;
  backfill_progress_pct: number;
}

export interface CalendarSyncStatus {
  account_id: string;
  sync_status: string;
  sync_error_message: string | null;
  consecutive_error_count: number;
  last_sync_at: string | null;
  sync_in_progress: boolean;
  backfill_status: string;
  backfill_progress_pct: number;
  backfill_started_at: string | null;
  backfill_completed_at: string | null;
  last_credential_op: string | null;
  last_credential_op_at: string | null;
  token_expires_at: string | null;
}

export interface CalendarAccountAccess {
  id: string;
  account_id: string;
  user_id: string;
  user_email: string | null;
  user_name: string | null;
  access_level: CalendarAccessLevel;
  granted_by_user_id: string | null;
  granted_at: string;
  revoked_at: string | null;
}

export interface CalendarProviderInfo {
  provider_type: CalendarProviderType;
  display_label: string;
  supports_inbound: boolean;
  supports_realtime: boolean;
  supports_freebusy: boolean;
}

export interface CreateCalendarAccountRequest {
  account_type: CalendarAccountType;
  display_name: string;
  primary_email_address: string;
  provider_type: CalendarProviderType;
  provider_config?: Record<string, unknown>;
  default_event_timezone?: string;
  is_default?: boolean;
}

export interface UpdateCalendarAccountRequest {
  display_name?: string;
  default_event_timezone?: string;
  is_default?: boolean;
  is_active?: boolean;
  outbound_enabled?: boolean;
  provider_config_patch?: Record<string, unknown>;
}

export interface GrantCalendarAccessRequest {
  user_id: string;
  access_level: CalendarAccessLevel;
}

// ── Event types ──────────────────────────────────────────────────

export interface CalendarEvent {
  id: string;
  tenant_id: string;
  account_id: string;
  provider_event_id: string | null;
  subject: string | null;
  description_text: string | null;
  description_html: string | null;
  location: string | null;
  start_at: string;
  end_at: string;
  is_all_day: boolean;
  event_timezone: string | null;
  recurrence_rule: string | null;
  recurrence_master_event_id: string | null;
  status: EventStatus;
  transparency: EventTransparency;
  is_cross_tenant: boolean;
  is_active: boolean;
  // Step 3 — state-change drafted-event provenance per §3.26.16.18.
  // null for events authored directly by an operator.
  generation_source?: string | null;
  generation_entity_type?: string | null;
  generation_entity_id?: string | null;
  created_by_user_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface CalendarEventAttendee {
  id: string;
  event_id: string;
  email_address: string;
  display_name: string | null;
  role: AttendeeRole;
  response_status: AttendeeResponseStatus;
  responded_at: string | null;
  comment: string | null;
  is_internal: boolean;
  first_seen_at: string;
}

export interface CalendarEventLinkage {
  id: string;
  event_id: string;
  linked_entity_type: string;
  linked_entity_id: string;
  linkage_source: LinkageSource;
  confidence: number | null;
  linked_at: string;
  dismissed_at: string | null;
}

export interface CreateCalendarEventRequest {
  account_id: string;
  subject?: string | null;
  description_text?: string | null;
  description_html?: string | null;
  location?: string | null;
  start_at: string;
  end_at: string;
  is_all_day?: boolean;
  event_timezone?: string | null;
  recurrence_rule?: string | null;
  status?: EventStatus;
  transparency?: EventTransparency;
}

export interface UpdateCalendarEventRequest {
  subject?: string | null;
  description_text?: string | null;
  description_html?: string | null;
  location?: string | null;
  start_at?: string;
  end_at?: string;
  is_all_day?: boolean;
  event_timezone?: string | null;
  recurrence_rule?: string | null;
  status?: EventStatus;
  transparency?: EventTransparency;
}

export interface AddAttendeeRequest {
  email_address: string;
  display_name?: string | null;
  role?: AttendeeRole;
  response_status?: AttendeeResponseStatus;
  is_internal?: boolean;
}

export interface UpdateAttendeeResponseRequest {
  response_status: AttendeeResponseStatus;
  comment?: string | null;
}

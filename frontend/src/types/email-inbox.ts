/**
 * Email inbox types — Phase W-4b Layer 1 Step 4a.
 *
 * Mirrors backend Pydantic shapes in
 * `backend/app/api/routes/email_inbox.py`. Keep in sync.
 */

export type EmailStatusFilter =
  | "all"
  | "unread"
  | "read"
  | "archived"
  | "flagged"
  | "snoozed";

export interface ThreadSummary {
  id: string;
  account_id: string;
  subject: string | null;
  sender_summary: string;
  snippet: string;
  last_message_at: string | null;
  message_count: number;
  unread_count: number;
  is_archived: boolean;
  is_flagged_thread: boolean;
  is_cross_tenant: boolean;
  cross_tenant_partner_tenant_id: string | null;
  label_ids: string[];
  assigned_to_user_id: string | null;
}

export interface ThreadListResponse {
  threads: ThreadSummary[];
  total: number;
  page: number;
  page_size: number;
}

export interface MessageDetail {
  id: string;
  thread_id: string;
  sender_email: string;
  sender_name: string | null;
  subject: string | null;
  body_text: string | null;
  body_html: string | null;
  sent_at: string | null;
  received_at: string;
  direction: "inbound" | "outbound";
  is_read: boolean;
  is_flagged: boolean;
  in_reply_to_message_id: string | null;
  provider_message_id: string | null;
  to: { email_address: string; display_name: string | null }[];
  cc: { email_address: string; display_name: string | null }[];
  bcc: { email_address: string; display_name: string | null }[];
}

export interface ThreadDetail {
  id: string;
  account_id: string;
  subject: string | null;
  is_archived: boolean;
  is_cross_tenant: boolean;
  cross_tenant_partner_tenant_id: string | null;
  label_ids: string[];
  participants_summary: string[];
  messages: MessageDetail[];
}

// Step 4b — labels, recipients, role-based routing

export interface EmailLabel {
  id: string;
  name: string;
  color: string | null;
  icon: string | null;
  is_system: boolean;
}

export type RecipientSourceType =
  | "crm_contact"
  | "recent"
  | "internal_user"
  | "role_expansion"
  | "external_tenant"
  | "cross_tenant_user";

export interface ResolvedRecipient {
  email_address: string;
  display_name: string | null;
  source_type: RecipientSourceType;
  resolution_id: string | null;
  rank_score: number;
}

export interface RoleRecipient {
  label: string;
  role_kind: "account_access" | "role_slug";
  id_value: string;
  member_count: number;
}

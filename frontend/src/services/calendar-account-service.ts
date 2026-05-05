/**
 * Calendar Account API client — Phase W-4b Layer 1 Calendar Step 1.
 *
 * Wraps endpoints under /api/v1/calendar-accounts/* + /api/v1/calendar-events/*.
 * Plain axios via the existing apiClient — no caching layer per `CLAUDE.md`.
 *
 * Mirrors the shape of `email-account-service.ts` precedent.
 */

import apiClient from "@/lib/api-client";
import type {
  AddAttendeeRequest,
  CalendarAccount,
  CalendarAccountAccess,
  CalendarEvent,
  CalendarEventAttendee,
  CalendarEventLinkage,
  CalendarProviderInfo,
  CalendarSyncStatus,
  CreateCalendarAccountRequest,
  CreateCalendarEventRequest,
  GrantCalendarAccessRequest,
  OAuthAuthorizeUrlResponse,
  OAuthCallbackRequest,
  OAuthCallbackResponse,
  UpdateAttendeeResponseRequest,
  UpdateCalendarAccountRequest,
  UpdateCalendarEventRequest,
} from "@/types/calendar-account";

const ACCOUNT_BASE = "/calendar-accounts";
const EVENT_BASE = "/calendar-events";

// ── Provider catalog ────────────────────────────────────────────────

export async function listCalendarProviders(): Promise<CalendarProviderInfo[]> {
  const r = await apiClient.get<CalendarProviderInfo[]>(
    `${ACCOUNT_BASE}/providers`,
  );
  return r.data;
}

// ── CalendarAccount CRUD ────────────────────────────────────────────

export async function listCalendarAccounts(
  includeInactive = false,
): Promise<CalendarAccount[]> {
  const r = await apiClient.get<CalendarAccount[]>(ACCOUNT_BASE, {
    params: { include_inactive: includeInactive },
  });
  return r.data;
}

export async function listMyCalendarAccounts(): Promise<CalendarAccount[]> {
  const r = await apiClient.get<CalendarAccount[]>(`${ACCOUNT_BASE}/mine`);
  return r.data;
}

export async function getCalendarAccount(
  accountId: string,
): Promise<CalendarAccount> {
  const r = await apiClient.get<CalendarAccount>(
    `${ACCOUNT_BASE}/${accountId}`,
  );
  return r.data;
}

export async function createCalendarAccount(
  body: CreateCalendarAccountRequest,
): Promise<CalendarAccount> {
  const r = await apiClient.post<CalendarAccount>(ACCOUNT_BASE, body);
  return r.data;
}

export async function updateCalendarAccount(
  accountId: string,
  body: UpdateCalendarAccountRequest,
): Promise<CalendarAccount> {
  const r = await apiClient.patch<CalendarAccount>(
    `${ACCOUNT_BASE}/${accountId}`,
    body,
  );
  return r.data;
}

export async function deleteCalendarAccount(
  accountId: string,
): Promise<{ deleted: boolean }> {
  const r = await apiClient.delete<{ deleted: boolean }>(
    `${ACCOUNT_BASE}/${accountId}`,
  );
  return r.data;
}

// ── Access scope management ─────────────────────────────────────────

export async function listCalendarAccessGrants(
  accountId: string,
  includeRevoked = false,
): Promise<CalendarAccountAccess[]> {
  const r = await apiClient.get<CalendarAccountAccess[]>(
    `${ACCOUNT_BASE}/${accountId}/access`,
    { params: { include_revoked: includeRevoked } },
  );
  return r.data;
}

export async function grantCalendarAccess(
  accountId: string,
  body: GrantCalendarAccessRequest,
): Promise<CalendarAccountAccess> {
  const r = await apiClient.post<CalendarAccountAccess>(
    `${ACCOUNT_BASE}/${accountId}/access`,
    body,
  );
  return r.data;
}

export async function revokeCalendarAccess(
  accountId: string,
  userId: string,
): Promise<{ revoked: boolean }> {
  const r = await apiClient.delete<{ revoked: boolean }>(
    `${ACCOUNT_BASE}/${accountId}/access/${userId}`,
  );
  return r.data;
}

// ── CalendarEvent CRUD ──────────────────────────────────────────────

export interface ListEventsParams {
  accountId: string;
  rangeStart?: string;
  rangeEnd?: string;
  includeInactive?: boolean;
  limit?: number;
}

export async function listCalendarEvents(
  params: ListEventsParams,
): Promise<CalendarEvent[]> {
  const r = await apiClient.get<CalendarEvent[]>(EVENT_BASE, {
    params: {
      account_id: params.accountId,
      range_start: params.rangeStart,
      range_end: params.rangeEnd,
      include_inactive: params.includeInactive ?? false,
      limit: params.limit ?? 500,
    },
  });
  return r.data;
}

export async function getCalendarEvent(
  eventId: string,
): Promise<CalendarEvent> {
  const r = await apiClient.get<CalendarEvent>(`${EVENT_BASE}/${eventId}`);
  return r.data;
}

export async function createCalendarEvent(
  body: CreateCalendarEventRequest,
): Promise<CalendarEvent> {
  const r = await apiClient.post<CalendarEvent>(EVENT_BASE, body);
  return r.data;
}

export async function updateCalendarEvent(
  eventId: string,
  body: UpdateCalendarEventRequest,
): Promise<CalendarEvent> {
  const r = await apiClient.patch<CalendarEvent>(
    `${EVENT_BASE}/${eventId}`,
    body,
  );
  return r.data;
}

export async function deleteCalendarEvent(
  eventId: string,
): Promise<{ deleted: boolean }> {
  const r = await apiClient.delete<{ deleted: boolean }>(
    `${EVENT_BASE}/${eventId}`,
  );
  return r.data;
}

// ── Attendee management ─────────────────────────────────────────────

export async function listEventAttendees(
  eventId: string,
): Promise<CalendarEventAttendee[]> {
  const r = await apiClient.get<CalendarEventAttendee[]>(
    `${EVENT_BASE}/${eventId}/attendees`,
  );
  return r.data;
}

export async function addEventAttendee(
  eventId: string,
  body: AddAttendeeRequest,
): Promise<CalendarEventAttendee> {
  const r = await apiClient.post<CalendarEventAttendee>(
    `${EVENT_BASE}/${eventId}/attendees`,
    body,
  );
  return r.data;
}

export async function updateAttendeeResponse(
  eventId: string,
  attendeeId: string,
  body: UpdateAttendeeResponseRequest,
): Promise<CalendarEventAttendee> {
  const r = await apiClient.patch<CalendarEventAttendee>(
    `${EVENT_BASE}/${eventId}/attendees/${attendeeId}/response`,
    body,
  );
  return r.data;
}

export async function removeEventAttendee(
  eventId: string,
  attendeeId: string,
): Promise<{ removed: boolean }> {
  const r = await apiClient.delete<{ removed: boolean }>(
    `${EVENT_BASE}/${eventId}/attendees/${attendeeId}`,
  );
  return r.data;
}

// ── Linkage management ─────────────────────────────────────────────


/** List polymorphic linkages for a calendar event.
 *
 * Phase W-4b Layer 1 Calendar Step 5 — powers the linked-entities
 * section of the native event detail page (§14.10.3).
 */
export async function listEventLinkages(
  eventId: string,
  includeDismissed = false,
): Promise<CalendarEventLinkage[]> {
  const r = await apiClient.get<CalendarEventLinkage[]>(
    `${EVENT_BASE}/${eventId}/linkages`,
    { params: { include_dismissed: includeDismissed } },
  );
  return r.data;
}

// ── Step 2 — OAuth + sync ───────────────────────────────────────────

export async function getCalendarOAuthAuthorizeUrl(
  providerType: "google_calendar" | "msgraph",
  redirectUri: string,
): Promise<OAuthAuthorizeUrlResponse> {
  const r = await apiClient.get<OAuthAuthorizeUrlResponse>(
    `${ACCOUNT_BASE}/oauth/${providerType}/authorize-url`,
    { params: { redirect_uri: redirectUri } },
  );
  return r.data;
}

export async function postCalendarOAuthCallback(
  body: OAuthCallbackRequest,
): Promise<OAuthCallbackResponse> {
  const r = await apiClient.post<OAuthCallbackResponse>(
    `${ACCOUNT_BASE}/oauth/callback`,
    body,
  );
  return r.data;
}

export async function getCalendarSyncStatus(
  accountId: string,
): Promise<CalendarSyncStatus> {
  const r = await apiClient.get<CalendarSyncStatus>(
    `${ACCOUNT_BASE}/${accountId}/sync-status`,
  );
  return r.data;
}

export async function calendarSyncNow(
  accountId: string,
): Promise<Record<string, string>> {
  const r = await apiClient.post<Record<string, string>>(
    `${ACCOUNT_BASE}/${accountId}/sync-now`,
  );
  return r.data;
}

// ── Step 3 — Outbound (commit + cancel) ─────────────────────────────

export interface SendEventResponse {
  status: string;
  event_id: string;
  provider_event_id: string | null;
  recipient_count: number;
}

export interface CancelEventResponse {
  status: string;
  event_id: string;
  recipient_count: number;
}

export async function sendCalendarEvent(
  eventId: string,
): Promise<SendEventResponse> {
  const r = await apiClient.post<SendEventResponse>(
    `${EVENT_BASE}/${eventId}/send`,
  );
  return r.data;
}

export async function cancelCalendarEvent(
  eventId: string,
): Promise<CancelEventResponse> {
  const r = await apiClient.post<CancelEventResponse>(
    `${EVENT_BASE}/${eventId}/cancel`,
  );
  return r.data;
}

export async function listStateChangeDrafts(
  limit = 100,
): Promise<CalendarEvent[]> {
  // Note: route declared at "/calendar-events-drafts/state-change" so
  // the dash-separated suffix avoids shadowing the polymorphic
  // /:event_id route segment.
  const r = await apiClient.get<CalendarEvent[]>(
    `${EVENT_BASE}-drafts/state-change`,
    { params: { limit } },
  );
  return r.data;
}

// ── Step 3 — Free/busy ──────────────────────────────────────────────

export interface FreebusyWindow {
  start: string;
  end: string;
  status: "busy" | "tentative" | "out_of_office";
  subject: string | null;
  location: string | null;
  attendee_count_bucket: string | null;
}

export interface FreebusyResponse {
  windows: FreebusyWindow[];
  last_sync_at: string | null;
  stale: boolean;
  account_id: string;
}

export interface CrossTenantFreebusyResponse {
  partner_tenant_id: string;
  windows: FreebusyWindow[];
  consent_level: "free_busy_only" | "full_details";
  last_sync_at: string | null;
  stale: boolean;
}

export async function getPerAccountFreebusy(params: {
  accountId: string;
  start: string;
  end: string;
}): Promise<FreebusyResponse> {
  const r = await apiClient.get<FreebusyResponse>(`/calendar/free-busy`, {
    params: {
      account_id: params.accountId,
      start: params.start,
      end: params.end,
    },
  });
  return r.data;
}

export async function getCrossTenantFreebusy(params: {
  partnerTenantId: string;
  start: string;
  end: string;
  granularity?: "hour" | "day";
}): Promise<CrossTenantFreebusyResponse> {
  const r = await apiClient.get<CrossTenantFreebusyResponse>(
    `/calendar/free-busy/cross-tenant`,
    {
      params: {
        partner_tenant_id: params.partnerTenantId,
        start: params.start,
        end: params.end,
        granularity: params.granularity ?? "hour",
      },
    },
  );
  return r.data;
}

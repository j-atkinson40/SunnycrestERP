/**
 * Email inbox API client — Phase W-4b Layer 1 Step 4a.
 *
 * Wraps GET /threads + GET /threads/{id} + status mutation endpoints.
 */

import apiClient from "@/lib/api-client";
import type {
  EmailLabel,
  EmailStatusFilter,
  ResolvedRecipient,
  RoleRecipient,
  ThreadDetail,
  ThreadListResponse,
  ThreadSummary,
} from "@/types/email-inbox";

const BASE = "/email";

export async function listThreads(params: {
  account_id?: string | null;
  status_filter?: EmailStatusFilter;
  label_id?: string | null;
  page?: number;
  page_size?: number;
}): Promise<ThreadListResponse> {
  const r = await apiClient.get<ThreadListResponse>(`${BASE}/threads`, {
    params: {
      ...(params.account_id ? { account_id: params.account_id } : {}),
      status_filter: params.status_filter ?? "all",
      ...(params.label_id ? { label_id: params.label_id } : {}),
      page: params.page ?? 1,
      page_size: params.page_size ?? 50,
    },
  });
  return r.data;
}

export async function getThreadDetail(
  threadId: string,
): Promise<ThreadDetail> {
  const r = await apiClient.get<ThreadDetail>(`${BASE}/threads/${threadId}`);
  return r.data;
}

export async function markRead(messageId: string): Promise<void> {
  await apiClient.post(`${BASE}/messages/${messageId}/read`);
}

export async function markUnread(messageId: string): Promise<void> {
  await apiClient.post(`${BASE}/messages/${messageId}/unread`);
}

export async function archiveThread(threadId: string): Promise<void> {
  await apiClient.post(`${BASE}/threads/${threadId}/archive`);
}

export async function unarchiveThread(threadId: string): Promise<void> {
  await apiClient.post(`${BASE}/threads/${threadId}/unarchive`);
}

export async function flagThread(threadId: string): Promise<void> {
  await apiClient.post(`${BASE}/threads/${threadId}/flag`);
}

export async function unflagThread(threadId: string): Promise<void> {
  await apiClient.post(`${BASE}/threads/${threadId}/unflag`);
}

// ── Step 4b — search ────────────────────────────────────────────────

export async function searchThreads(params: {
  q: string;
  account_id?: string | null;
  limit?: number;
}): Promise<ThreadSummary[]> {
  const r = await apiClient.get<ThreadSummary[]>(`${BASE}/search/threads`, {
    params: {
      q: params.q,
      ...(params.account_id ? { account_id: params.account_id } : {}),
      limit: params.limit ?? 50,
    },
  });
  return r.data;
}

// ── Step 4b — snooze ────────────────────────────────────────────────

export async function snoozeThread(
  threadId: string,
  snoozedUntil: Date,
): Promise<void> {
  await apiClient.post(`${BASE}/threads/${threadId}/snooze`, {
    snoozed_until: snoozedUntil.toISOString(),
  });
}

export async function unsnoozeThread(threadId: string): Promise<void> {
  await apiClient.delete(`${BASE}/threads/${threadId}/snooze`);
}

// ── Step 4b — labels ────────────────────────────────────────────────

export async function listLabels(): Promise<EmailLabel[]> {
  const r = await apiClient.get<EmailLabel[]>(`${BASE}/labels`);
  return r.data;
}

export async function createLabel(
  name: string,
  color?: string,
): Promise<EmailLabel> {
  const r = await apiClient.post<EmailLabel>(`${BASE}/labels`, {
    name,
    color,
  });
  return r.data;
}

export async function addLabelToThread(
  threadId: string,
  labelId: string,
): Promise<void> {
  await apiClient.post(`${BASE}/threads/${threadId}/labels`, {
    label_id: labelId,
  });
}

export async function removeLabelFromThread(
  threadId: string,
  labelId: string,
): Promise<void> {
  await apiClient.delete(`${BASE}/threads/${threadId}/labels/${labelId}`);
}

// ── Step 4b — recipients + role-based routing ──────────────────────

export async function resolveRecipients(params: {
  q: string;
  account_id?: string | null;
  limit?: number;
}): Promise<ResolvedRecipient[]> {
  const r = await apiClient.get<ResolvedRecipient[]>(
    `${BASE}/recipients/resolve`,
    {
      params: {
        q: params.q,
        ...(params.account_id ? { account_id: params.account_id } : {}),
        limit: params.limit ?? 10,
      },
    },
  );
  return r.data;
}

export async function listRoleRecipients(
  accountId: string,
): Promise<RoleRecipient[]> {
  const r = await apiClient.get<RoleRecipient[]>(`${BASE}/recipients/roles`, {
    params: { account_id: accountId },
  });
  return r.data;
}

export async function expandRoleRecipient(
  roleKind: "account_access" | "role_slug",
  idValue: string,
): Promise<ResolvedRecipient[]> {
  const r = await apiClient.post<ResolvedRecipient[]>(
    `${BASE}/recipients/expand-role`,
    { role_kind: roleKind, id_value: idValue },
  );
  return r.data;
}

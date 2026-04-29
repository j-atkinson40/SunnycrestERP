/**
 * Email inbox API client — Phase W-4b Layer 1 Step 4a.
 *
 * Wraps GET /threads + GET /threads/{id} + status mutation endpoints.
 */

import apiClient from "@/lib/api-client";
import type {
  EmailStatusFilter,
  ThreadDetail,
  ThreadListResponse,
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

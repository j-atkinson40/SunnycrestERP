/**
 * Email Account API client — Phase W-4b Layer 1 Step 1.
 *
 * Wraps the 11 endpoints under /api/v1/email-accounts/*. Plain axios
 * via the existing apiClient — no caching layer per `CLAUDE.md`.
 */

import apiClient from "@/lib/api-client";
import type {
  CreateAccountRequest,
  EmailAccount,
  EmailAccountAccess,
  OAuthAuthorizeUrlResponse,
  OAuthCallbackRequest,
  OAuthCallbackResponse,
  ProviderInfo,
  SyncStatus,
  UpdateAccountRequest,
  AccessLevel,
  ProviderType,
} from "@/types/email-account";

const BASE = "/email-accounts";

export async function listProviders(): Promise<ProviderInfo[]> {
  const r = await apiClient.get<ProviderInfo[]>(`${BASE}/providers`);
  return r.data;
}

export async function listAccounts(
  includeInactive = false,
): Promise<EmailAccount[]> {
  const r = await apiClient.get<EmailAccount[]>(BASE, {
    params: { include_inactive: includeInactive },
  });
  return r.data;
}

export async function listMyAccounts(): Promise<EmailAccount[]> {
  const r = await apiClient.get<EmailAccount[]>(`${BASE}/mine`);
  return r.data;
}

export async function getAccount(accountId: string): Promise<EmailAccount> {
  const r = await apiClient.get<EmailAccount>(`${BASE}/${accountId}`);
  return r.data;
}

export async function createAccount(
  request: CreateAccountRequest,
): Promise<EmailAccount> {
  const r = await apiClient.post<EmailAccount>(BASE, request);
  return r.data;
}

export async function updateAccount(
  accountId: string,
  request: UpdateAccountRequest,
): Promise<EmailAccount> {
  const r = await apiClient.patch<EmailAccount>(`${BASE}/${accountId}`, request);
  return r.data;
}

export async function deleteAccount(
  accountId: string,
): Promise<{ deleted: boolean }> {
  const r = await apiClient.delete<{ deleted: boolean }>(
    `${BASE}/${accountId}`,
  );
  return r.data;
}

export async function listAccessGrants(
  accountId: string,
  includeRevoked = false,
): Promise<EmailAccountAccess[]> {
  const r = await apiClient.get<EmailAccountAccess[]>(
    `${BASE}/${accountId}/access`,
    { params: { include_revoked: includeRevoked } },
  );
  return r.data;
}

export async function grantAccess(
  accountId: string,
  userId: string,
  accessLevel: AccessLevel,
): Promise<EmailAccountAccess> {
  const r = await apiClient.post<EmailAccountAccess>(
    `${BASE}/${accountId}/access`,
    { user_id: userId, access_level: accessLevel },
  );
  return r.data;
}

export async function revokeAccess(
  accountId: string,
  userId: string,
): Promise<{ revoked: boolean }> {
  const r = await apiClient.delete<{ revoked: boolean }>(
    `${BASE}/${accountId}/access/${userId}`,
  );
  return r.data;
}

export async function getOAuthAuthorizeUrl(
  providerType: ProviderType,
  redirectUri: string,
): Promise<OAuthAuthorizeUrlResponse> {
  const r = await apiClient.get<OAuthAuthorizeUrlResponse>(
    `${BASE}/oauth/${providerType}/authorize-url`,
    { params: { redirect_uri: redirectUri } },
  );
  return r.data;
}

export async function postOAuthCallback(
  request: OAuthCallbackRequest,
): Promise<OAuthCallbackResponse> {
  const r = await apiClient.post<OAuthCallbackResponse>(
    `${BASE}/oauth/callback`,
    request,
  );
  return r.data;
}

export async function getSyncStatus(accountId: string): Promise<SyncStatus> {
  const r = await apiClient.get<SyncStatus>(`${BASE}/${accountId}/sync-status`);
  return r.data;
}

export async function syncNow(
  accountId: string,
): Promise<Record<string, string>> {
  const r = await apiClient.post<Record<string, string>>(
    `${BASE}/${accountId}/sync-now`,
  );
  return r.data;
}

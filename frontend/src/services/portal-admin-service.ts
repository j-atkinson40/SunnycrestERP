/**
 * Portal admin API client — Workflow Arc Phase 8e.2.1.
 *
 * TENANT-authed — uses the shared `apiClient` (tenant JWT + X-
 * Company-Slug header). NOT the portal axios instance. These
 * endpoints are for tenant admins managing portal users, not for
 * portal users themselves.
 */

import apiClient from "@/lib/api-client";

import type {
  BrandingPatchBody,
  EditPortalUserBody,
  InvitePortalUserBody,
  LogoUploadResponse,
  PortalBrandingResponse,
  PortalUserStatus,
  PortalUserSummary,
  PortalUsersListResponse,
} from "@/types/portal-admin";

// ── Portal users CRUD ────────────────────────────────────────────

export async function listPortalUsers(params: {
  status?: PortalUserStatus;
  space?: string;
} = {}): Promise<PortalUsersListResponse> {
  const query: Record<string, string> = {};
  if (params.status) query.status = params.status;
  if (params.space) query.space = params.space;
  const r = await apiClient.get<PortalUsersListResponse>(
    "/portal/admin/users",
    { params: query },
  );
  return r.data;
}

export async function invitePortalUser(
  body: InvitePortalUserBody,
): Promise<{ user: PortalUserSummary }> {
  const r = await apiClient.post<{ user: PortalUserSummary }>(
    "/portal/admin/users",
    body,
  );
  return r.data;
}

export async function editPortalUser(
  portalUserId: string,
  body: EditPortalUserBody,
): Promise<PortalUserSummary> {
  const r = await apiClient.patch<PortalUserSummary>(
    `/portal/admin/users/${portalUserId}`,
    body,
  );
  return r.data;
}

export async function deactivatePortalUser(
  portalUserId: string,
): Promise<PortalUserSummary> {
  const r = await apiClient.post<PortalUserSummary>(
    `/portal/admin/users/${portalUserId}/deactivate`,
  );
  return r.data;
}

export async function reactivatePortalUser(
  portalUserId: string,
): Promise<PortalUserSummary> {
  const r = await apiClient.post<PortalUserSummary>(
    `/portal/admin/users/${portalUserId}/reactivate`,
  );
  return r.data;
}

export async function unlockPortalUser(
  portalUserId: string,
): Promise<PortalUserSummary> {
  const r = await apiClient.post<PortalUserSummary>(
    `/portal/admin/users/${portalUserId}/unlock`,
  );
  return r.data;
}

export async function resetPortalUserPassword(
  portalUserId: string,
): Promise<void> {
  await apiClient.post(
    `/portal/admin/users/${portalUserId}/reset-password`,
  );
}

export async function resendInvite(portalUserId: string): Promise<void> {
  await apiClient.post(
    `/portal/admin/users/${portalUserId}/resend-invite`,
  );
}

// ── Branding ─────────────────────────────────────────────────────

export async function getBranding(): Promise<PortalBrandingResponse> {
  const r = await apiClient.get<PortalBrandingResponse>(
    "/portal/admin/branding",
  );
  return r.data;
}

export async function updateBranding(
  body: BrandingPatchBody,
): Promise<PortalBrandingResponse> {
  const r = await apiClient.patch<PortalBrandingResponse>(
    "/portal/admin/branding",
    body,
  );
  return r.data;
}

export async function uploadLogo(file: File): Promise<LogoUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  const r = await apiClient.post<LogoUploadResponse>(
    "/portal/admin/branding/logo",
    formData,
    {
      headers: { "Content-Type": "multipart/form-data" },
    },
  );
  return r.data;
}

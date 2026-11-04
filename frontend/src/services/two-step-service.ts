import apiClient from "@/lib/api-client";
import type { TokenResponse } from "@/types/auth";

/**
 * Two-step sign-in and invite acceptance.
 *
 * Both halves of Payroll 2's goal sentence live here: no password through a
 * request body (invites), and a second step for anyone who can reach payroll.
 */

export interface TwoStepStatus {
  required: boolean;
  enrolled: boolean;
  unused_recovery_codes: number;
}

export interface BeginEnrolment {
  secret: string;
  provisioning_uri: string;
  issuer: string;
}

export interface ConfirmEnrolment extends TokenResponse {
  /** Shown once, never retrievable again. */
  recovery_codes: string[];
}

export interface InvitePreview {
  email: string;
  first_name: string;
  last_name: string;
  company_name: string;
}

export interface AcceptedInvite {
  email: string;
  company_slug: string;
  two_step_required: boolean;
}

export const twoStepService = {
  async getStatus(): Promise<TwoStepStatus> {
    const r = await apiClient.get<TwoStepStatus>("/two-step/status");
    return r.data;
  },

  async begin(): Promise<BeginEnrolment> {
    const r = await apiClient.post<BeginEnrolment>("/two-step/begin");
    return r.data;
  },

  async confirm(code: string): Promise<ConfirmEnrolment> {
    const r = await apiClient.post<ConfirmEnrolment>("/two-step/confirm", { code });
    return r.data;
  },

  /** Exchange a first-step token for one that has passed the second step. */
  async verify(code: string): Promise<TokenResponse> {
    const r = await apiClient.post<TokenResponse>("/two-step/verify", { code });
    return r.data;
  },

  async useRecoveryCode(code: string): Promise<TokenResponse> {
    const r = await apiClient.post<TokenResponse>("/two-step/recovery", { code });
    return r.data;
  },
};

export const inviteService = {
  /**
   * Both of these are unauthenticated — she has no credential yet. The token
   * in the path IS the credential.
   */
  async preview(token: string): Promise<InvitePreview> {
    const r = await apiClient.get<InvitePreview>(`/invites/${encodeURIComponent(token)}`);
    return r.data;
  },

  async accept(token: string, password: string): Promise<AcceptedInvite> {
    const r = await apiClient.post<AcceptedInvite>(
      `/invites/${encodeURIComponent(token)}/accept`,
      { password },
    );
    return r.data;
  },
};

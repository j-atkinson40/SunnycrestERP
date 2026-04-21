/**
 * Portal admin types — Workflow Arc Phase 8e.2.1.
 *
 * Mirror of the backend `/api/v1/portal/admin/*` shapes. Used by
 * the /settings/portal-users + /settings/portal-branding pages.
 */

export type PortalUserStatus = "active" | "pending" | "locked" | "inactive";

export interface PortalUserSummary {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  assigned_space_id: string | null;
  assigned_space_name: string | null;
  status: PortalUserStatus;
  last_login_at: string | null;
  driver_id: string | null;
  created_at: string;
}

export interface PortalUsersListResponse {
  users: PortalUserSummary[];
}

export interface InvitePortalUserBody {
  email: string;
  first_name: string;
  last_name: string;
  assigned_space_id: string;
}

export interface EditPortalUserBody {
  first_name?: string;
  last_name?: string;
  email?: string;
  assigned_space_id?: string;
}

// ── Branding ─────────────────────────────────────────────────────

export interface PortalBrandingResponse {
  slug: string;
  display_name: string;
  logo_url: string | null;
  brand_color: string;
  footer_text: string | null;
}

export interface BrandingPatchBody {
  brand_color?: string;
  footer_text?: string | null;
}

export interface LogoUploadResponse {
  logo_url: string;
}

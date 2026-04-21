/**
 * Portal types — Workflow Arc Phase 8e.2.
 *
 * Mirror of the backend portal API contract. Separate from tenant-
 * realm types to keep the identity boundary explicit.
 */

// ── Branding ─────────────────────────────────────────────────────

/**
 * Tenant branding payload returned by the public
 * GET /api/v1/portal/<slug>/branding endpoint. Used by
 * PortalLogin (pre-auth) + PortalBrandProvider (post-auth) to set
 * CSS vars + render tenant logo / display name.
 */
export interface PortalBranding {
  slug: string;
  display_name: string;
  logo_url: string | null;
  /** Hex string like "#1E40AF". Falls through to the platform
   *  brass accent if the tenant hasn't set one. Applied as a wash
   *  — NOT a reskin. See SPACES_ARCHITECTURE.md §10.6. */
  brand_color: string;
  footer_text: string | null;
}

// ── Auth ────────────────────────────────────────────────────────

export interface PortalLoginBody {
  email: string;
  password: string;
}

export interface PortalTokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
  /** The portal user's assigned space id; UI uses it to pick the
   *  correct template / landing route without a separate round trip. */
  space_id: string;
}

export interface PortalMe {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  company_id: string;
  assigned_space_id: string | null;
}

// ── Driver summary (Phase 8e.2 minimal mirror) ───────────────────

export interface PortalDriverSummary {
  portal_user_id: string;
  driver_id: string | null;
  driver_name: string;
  today_stops_count: number;
  tenant_display_name: string;
}

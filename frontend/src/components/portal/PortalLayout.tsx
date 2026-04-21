/**
 * PortalLayout — Workflow Arc Phase 8e.2.
 *
 * Mobile-first portal shell. Key differences from tenant AppLayout:
 *
 *   - NO DotNav (portal users have one space)
 *   - NO command bar (out of portal scope per SPACES_ARCHITECTURE.md §10)
 *   - NO settings, no saved views, no peek
 *   - Tenant-branded header (logo + display name, background is
 *     `var(--portal-brand)`, foreground is `var(--portal-brand-fg)`)
 *   - Minimal chrome; content fills the viewport
 *   - Optional bottom tab bar (for the driver portal — inherited
 *     from the existing DriverLayout pattern)
 *
 * The layout relies on PortalBrandProvider being mounted above it
 * (it reads the --portal-brand CSS var, which the provider sets).
 * PortalAuthProvider must also be mounted above — logout action
 * lives here.
 */

import { Outlet, useNavigate } from "react-router-dom";

import { usePortalAuth } from "@/contexts/portal-auth-context";
import { usePortalBrand } from "@/contexts/portal-brand-context";

export function PortalLayout() {
  const navigate = useNavigate();
  const { me, slug, logout } = usePortalAuth();
  const { branding } = usePortalBrand();

  return (
    <div className="flex min-h-screen flex-col bg-surface-base">
      {/* Header — tenant-branded. Background is the tenant's brand
          color; foreground is contrast-safe. Height matches the
          pre-existing DriverLayout (h-12 = 48px) which is WCAG 2.2
          Target Size compliant. */}
      <header
        className="flex h-12 items-center justify-between px-4 shadow-level-1"
        style={{
          backgroundColor: "var(--portal-brand, var(--accent-brass))",
          color: "var(--portal-brand-fg, white)",
        }}
        data-testid="portal-header"
      >
        <div className="flex items-center gap-2 min-w-0">
          {branding?.logo_url ? (
            <img
              src={branding.logo_url}
              alt={branding.display_name}
              className="h-7 w-auto max-w-[140px] object-contain"
            />
          ) : (
            <span className="text-body-sm font-semibold truncate">
              {branding?.display_name ?? ""}
            </span>
          )}
        </div>
        <div className="flex items-center gap-3 min-w-0">
          {me ? (
            <span className="text-caption truncate">
              {me.first_name} {me.last_name}
            </span>
          ) : null}
          <button
            type="button"
            onClick={() => {
              logout();
              if (slug) navigate(`/portal/${slug}/login`, { replace: true });
            }}
            className="text-caption font-medium hover:underline focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-white/50 rounded"
            data-testid="portal-logout"
          >
            Sign Out
          </button>
        </div>
      </header>

      {/* Main — single-column, padded content, overflow scroll.
          Minimum 44px touch targets expected from child pages. */}
      <main className="flex-1 overflow-y-auto p-4" data-testid="portal-main">
        <Outlet />
      </main>

      {/* Optional footer — shows tenant footer text if configured. */}
      {branding?.footer_text ? (
        <footer className="border-t border-border-subtle bg-surface-sunken p-3 text-center text-caption text-content-muted">
          {branding.footer_text}
        </footer>
      ) : null}
    </div>
  );
}

/**
 * PublicPortalLayout — Phase R-6.2b.
 *
 * Mobile-first portal shell for fully-anonymous public portal pages.
 * Distinct from PortalLayout (which requires PortalAuthProvider for
 * its Sign Out affordance).
 *
 * Architectural pattern locked in CLAUDE.md §4:
 *   Portal substrate has TWO access modes. PortalLayout serves
 *   magic-link-authenticated portal users (Phase 8e.2.1 driver
 *   portal). PublicPortalLayout serves fully-anonymous public
 *   intake (R-6.2b). Future anonymous portal surfaces (FH website
 *   embed widgets, public-facing inquiry forms, vendor registration)
 *   inherit PublicPortalLayout.
 *
 * Requires PortalBrandProvider mounted above — reads `--portal-brand`
 * + `--portal-brand-fg` CSS vars. Does NOT require PortalAuthProvider.
 *
 * "Wash, not reskin" discipline preserved per SPACES_ARCHITECTURE.md
 * §10.6 — brand color affects header background + foreground only;
 * everything else stays DESIGN_LANGUAGE.
 */

import { Outlet } from "react-router-dom";

import { usePortalBrand } from "@/contexts/portal-brand-context";

interface Props {
  children?: React.ReactNode;
}

export function PublicPortalLayout({ children }: Props) {
  const { branding } = usePortalBrand();

  return (
    <div
      className="flex min-h-screen flex-col bg-surface-base"
      data-testid="public-portal-layout"
    >
      {/* Header — tenant-branded. Same h-12 + WCAG-AA brand-fg fallback
          as PortalLayout per Session 4 M2; no logout button. */}
      <header
        className="flex h-12 items-center justify-between px-4 shadow-level-1"
        style={{
          backgroundColor: "var(--portal-brand, var(--accent))",
          color: "var(--portal-brand-fg, var(--content-on-accent))",
        }}
        data-testid="public-portal-header"
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
      </header>

      <main
        className="flex-1 overflow-y-auto p-4"
        data-testid="public-portal-main"
      >
        {children ?? <Outlet />}
      </main>

      {/* Footer — small attribution + optional tenant footer copy.
          Stays subtle per "wash, not reskin." */}
      <footer
        className="border-t border-border-subtle bg-surface-sunken p-3 text-center text-caption text-content-muted"
        data-testid="public-portal-footer"
      >
        {branding?.footer_text ? (
          <span className="block mb-1">{branding.footer_text}</span>
        ) : null}
        <span className="text-content-subtle">Powered by Bridgeable</span>
      </footer>
    </div>
  );
}

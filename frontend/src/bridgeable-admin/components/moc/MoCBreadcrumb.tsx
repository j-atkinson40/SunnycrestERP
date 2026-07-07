/**
 * MoCBreadcrumb — the hierarchy spine (MoC Hierarchy H-3).
 *
 * Platform › Manufacturing › Test Vault Co — ROUTE-DERIVED (a cold deep-link
 * renders the full crumb; no navigation history involved), every non-current
 * segment a link. Replaces the H-1/H-2 up-link stubs: the crumb IS the
 * up-navigation.
 *
 * Levels: the VERTICAL page shows Platform › <Vertical>; the TENANT page shows
 * all three. The PLATFORM page shows NO crumb — a single-segment crumb is
 * noise, not orientation (the workspace root needs no path to itself).
 * Notion-quiet: top-of-page text, orientation not chrome.
 */
import { Link } from "react-router-dom"

import { adminPath } from "@/bridgeable-admin/lib/admin-routes"
import { KNOWN_VERTICALS } from "@/bridgeable-admin/components/moc/MoCVerticalsRail"

function verticalLabel(slug: string): string {
  return KNOWN_VERTICALS.find((v) => v.slug === slug)?.label ?? slug
}

const SEG = "text-body-sm text-content-muted hover:text-content-base"
const SEP = <span className="text-content-subtle">›</span>

export function MoCBreadcrumb({
  vertical, tenantLabel,
}: {
  vertical: string
  /** Present on the tenant level — the current (non-link) segment. */
  tenantLabel?: string
}) {
  return (
    <nav
      className="flex items-center gap-1.5"
      aria-label="Map hierarchy"
      data-testid="moc-breadcrumb"
    >
      <Link to={adminPath("/")} className={SEG} data-testid="moc-crumb-platform">
        Platform
      </Link>
      {SEP}
      {tenantLabel ? (
        <>
          <Link
            to={adminPath(`/maps/${vertical}`)}
            className={SEG}
            data-testid="moc-crumb-vertical"
          >
            {verticalLabel(vertical)}
          </Link>
          {SEP}
          <span className="text-body-sm text-content-strong" data-testid="moc-crumb-current">
            {tenantLabel}
          </span>
        </>
      ) : (
        <span className="text-body-sm text-content-strong" data-testid="moc-crumb-current">
          {verticalLabel(vertical)}
        </span>
      )}
    </nav>
  )
}

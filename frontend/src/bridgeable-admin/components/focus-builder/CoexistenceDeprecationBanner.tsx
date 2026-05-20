/**
 * CoexistenceDeprecationBanner — legacy Focus editor banner (sub-arc F-5).
 *
 * Renders inside the legacy `/studio/focuses` (Tier 1/Tier 2) editor
 * page to point operators at the new Focus Builder at
 * `/studio/builder/focuses`. Dismissible per-session via localStorage
 * (key: bridgeable.focus-builder.coexistence-banner-dismissed) so it
 * doesn't pile on after the first operator acknowledgment.
 *
 * Locked decision (F-5 #3):
 *   - Forward-only — banner is on the LEGACY route only. The new
 *     route renders nothing.
 *   - Link is clickable; the operator can self-navigate without
 *     dismissing.
 *   - Subtle/non-blocking — single row, brass-accent border-left,
 *     `×` dismiss affordance.
 *
 * The link uses an admin-tree-aware href so it works under both
 * `admin.<domain>` (path `/studio/builder/focuses`) and any host's
 * `/bridgeable-admin/*` prefix. Relies on the consumer to pass the
 * correct href via `linkHref` so this component stays presentational
 * and host-agnostic.
 */
import * as React from "react"


export const COEXISTENCE_BANNER_STORAGE_KEY =
  "bridgeable.focus-builder.coexistence-banner-dismissed"


function readDismissed(): boolean {
  if (typeof window === "undefined") return false
  try {
    return (
      window.localStorage.getItem(COEXISTENCE_BANNER_STORAGE_KEY) === "true"
    )
  } catch {
    return false
  }
}


function writeDismissed() {
  if (typeof window === "undefined") return
  try {
    window.localStorage.setItem(COEXISTENCE_BANNER_STORAGE_KEY, "true")
  } catch {
    // ignore
  }
}


export interface CoexistenceDeprecationBannerProps {
  /** Absolute or relative href to the new Focus Builder. */
  linkHref?: string
}


export function CoexistenceDeprecationBanner({
  linkHref = "/studio/builder/focuses",
}: CoexistenceDeprecationBannerProps) {
  const [dismissed, setDismissed] = React.useState<boolean>(() =>
    readDismissed(),
  )

  if (dismissed) return null

  const handleDismiss = () => {
    writeDismissed()
    setDismissed(true)
  }

  return (
    <div
      data-testid="coexistence-banner"
      role="status"
      className="flex items-center gap-3 border-b border-[color:var(--border-subtle)] border-l-2 border-l-[color:var(--accent)] bg-[color:var(--accent-subtle)] px-4 py-2 text-[12px] text-[color:var(--content-base)]"
      style={{ fontFamily: "var(--font-plex-sans)" }}
    >
      <div className="flex-1">
        This is the legacy Focus editor. The new{" "}
        <a
          data-testid="coexistence-banner-link"
          href={linkHref}
          className="font-medium text-[color:var(--accent)] underline underline-offset-2 hover:text-[color:var(--accent-strong,var(--accent))] focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[color:var(--accent)]"
        >
          Focus Builder
        </a>{" "}
        is at <span className="font-plex-mono">{linkHref}</span> — try it now.
      </div>
      <button
        type="button"
        data-testid="coexistence-banner-dismiss"
        onClick={handleDismiss}
        aria-label="Dismiss legacy editor banner"
        className="rounded-sm px-1.5 py-0.5 text-[14px] leading-none text-[color:var(--content-muted)] hover:bg-[color:var(--surface-base)] hover:text-[color:var(--content-base)] focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[color:var(--accent)]"
      >
        ×
      </button>
    </div>
  )
}

export default CoexistenceDeprecationBanner

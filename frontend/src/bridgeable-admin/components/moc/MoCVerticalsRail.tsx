/**
 * Maps of Content — Verticals rail (Phase 1.2 two-pane).
 *
 * The persistent left navigation rail of the MoC two-pane: the vertical list
 * (Manufacturing live → links to /maps/:vertical; the others in the §18
 * "no map yet" not-built state from 1.1). Shared by MoCHome (no active
 * vertical) and MoCPage (active = the route's :vertical) — rendered as a
 * COMPONENT in both, NOT a route-tree change, so routing stays byte-identical
 * (the rail merely LINKS to the existing /maps/:vertical route).
 *
 * §18 materials, not Notion chrome: surface-sunken rail, content tones, the
 * brass accent for the active item. The not-built items are muted + non-link
 * (the unbuilt truth, never the orphan "no longer available" wording).
 */

import * as React from "react"
import { Link, useParams } from "react-router-dom"
import { Map as MapIcon } from "lucide-react"

import { adminPath } from "@/bridgeable-admin/lib/admin-routes"
import { Icon } from "@/components/ui/icon"
import {
  listPages,
  type MoCPageRecord,
} from "@/bridgeable-admin/services/moc-service"

// The platform verticals (the 4 presets; mirrors the `verticals` table). A
// constant, not a fetch — stable set; dynamic fetch is a deliberate follow-up.
export const KNOWN_VERTICALS: ReadonlyArray<{ slug: string; label: string }> = [
  { slug: "manufacturing", label: "Manufacturing" },
  { slug: "funeral_home", label: "Funeral Home" },
  { slug: "cemetery", label: "Cemetery" },
  { slug: "crematory", label: "Crematory" },
]

export function MoCVerticalsRail() {
  const { vertical: activeSlug } = useParams<{ vertical: string }>()
  const [seeded, setSeeded] = React.useState<Set<string>>(new Set())
  const [titleBySlug, setTitleBySlug] = React.useState<Map<string, string>>(
    new Map(),
  )

  React.useEffect(() => {
    let alive = true
    listPages({ scope: "vertical_default" })
      .then((pages: MoCPageRecord[]) => {
        if (!alive) return
        const withMap = pages.filter((p) => p.vertical)
        setSeeded(new Set(withMap.map((p) => p.vertical as string)))
        setTitleBySlug(
          new Map(withMap.map((p) => [p.vertical as string, p.title])),
        )
      })
      .catch(() => {
        /* rail degrades to all-not-yet; the content pane surfaces errors */
      })
    return () => {
      alive = false
    }
  }, [])

  return (
    <nav
      aria-label="Verticals"
      data-testid="moc-verticals-rail"
      className="w-60 shrink-0 border-r border-border-subtle bg-surface-sunken p-3"
    >
      <h2 className="px-2 pb-2 text-caption font-medium uppercase tracking-wide text-content-subtle">
        Verticals
      </h2>
      <ul className="space-y-0.5">
        {KNOWN_VERTICALS.map((v) => {
          const isSeeded = seeded.has(v.slug)
          const isActive = activeSlug === v.slug
          const label = titleBySlug.get(v.slug) ?? v.label

          if (!isSeeded) {
            return (
              <li
                key={v.slug}
                data-testid={`moc-rail-item-${v.slug}`}
                data-available="false"
                className="flex items-center gap-2 rounded-md px-2 py-1.5 text-content-subtle"
              >
                <Icon icon={MapIcon} size={16} className="text-content-subtle" />
                <span className="flex-1 truncate">{v.label}</span>
                <span className="text-caption">no map yet</span>
              </li>
            )
          }

          return (
            <li key={v.slug} data-testid={`moc-rail-item-${v.slug}`} data-available="true">
              <Link
                to={adminPath(`/maps/${v.slug}`)}
                aria-current={isActive ? "page" : undefined}
                className={[
                  "flex items-center gap-2 rounded-md px-2 py-1.5 focus-ring-accent",
                  isActive
                    ? "bg-accent-subtle text-content-strong"
                    : "text-content-base hover:bg-surface-base hover:text-accent",
                ].join(" ")}
              >
                <Icon
                  icon={MapIcon}
                  size={16}
                  className={isActive ? "text-accent" : "text-content-muted"}
                />
                <span className="flex-1 truncate">{label}</span>
              </Link>
            </li>
          )
        })}
      </ul>
    </nav>
  )
}

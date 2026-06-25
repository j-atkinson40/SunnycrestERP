/**
 * Maps of Content — home dashboard (MoC Phase 1).
 *
 * A NEW admin surface (NOT a Space — PlatformUser has no preferences;
 * investigation §C). The always-available admin landing for artifact-first
 * navigation: the authored MoC pages, each a link into its per-vertical
 * map. Shares the LinkedTable rendering with the page surface (§E) — here
 * the rows are internal links to /maps/:vertical, kind "Map".
 */

import * as React from "react"
import { Map as MapIcon } from "lucide-react"

import { adminPath } from "@/bridgeable-admin/lib/admin-routes"
import {
  listPages,
  type MoCPageRecord,
} from "@/bridgeable-admin/services/moc-service"
import {
  LinkedTable,
  type LinkedTableSection,
} from "@/bridgeable-admin/components/moc/LinkedTable"
import { Panel, PanelBody, PanelHeader, PanelTitle } from "@/components/ui/panel"
import { ErrorState } from "@/components/ui/error-state"
import { SkeletonLines } from "@/components/ui/skeleton"
import { useDelayedLoading } from "@/hooks/use-delayed-loading"

// The platform verticals (the 4 presets; mirrors the `verticals` table —
// manufacturing / funeral_home / cemetery / crematory). A constant, not a
// fetch: the front door's first load shouldn't depend on a second request,
// and the set is stable. If verticals grow, this list follows (a dynamic
// fetch is a deliberate follow-up, not Phase-1.1 scope).
const KNOWN_VERTICALS: ReadonlyArray<{ slug: string; label: string }> = [
  { slug: "manufacturing", label: "Manufacturing" },
  { slug: "funeral_home", label: "Funeral Home" },
  { slug: "cemetery", label: "Cemetery" },
  { slug: "crematory", label: "Crematory" },
]

// All four verticals always render: a seeded one is a LIVE link to its map;
// an unseeded one is an honest §18 "no map yet" row (muted, non-link) — an
// UNBUILT truth, distinct from the orphan "no longer available" state. The
// front door looks intentional on first load, never half-seeded.
function toSections(pages: MoCPageRecord[]): LinkedTableSection[] {
  const bySlug = new Map(
    pages.filter((p) => p.vertical).map((p) => [p.vertical as string, p]),
  )
  return [
    {
      section_id: "maps",
      title: "Maps",
      description: "Authored navigation, one per vertical.",
      rows: KNOWN_VERTICALS.map((v) => {
        const page = bySlug.get(v.slug)
        if (page) {
          return {
            row_id: page.id,
            label: page.title,
            href: adminPath(`/maps/${v.slug}`),
            available: true,
            icon: MapIcon,
            kindLabel: "Map",
          }
        }
        return {
          row_id: `not-built-${v.slug}`,
          label: v.label,
          href: null,
          available: false,
          unavailableReason: "not-built" as const,
          icon: MapIcon,
          kindLabel: "Map",
        }
      }),
    },
  ]
}

export default function MoCHome() {
  const [pages, setPages] = React.useState<MoCPageRecord[]>([])
  const [loading, setLoading] = React.useState(true)
  const [error, setError] = React.useState<string | null>(null)
  const showSkeleton = useDelayedLoading(loading)

  const load = React.useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      setPages(await listPages({ scope: "vertical_default" }))
    } catch {
      setError("Couldn't load the maps.")
    } finally {
      setLoading(false)
    }
  }, [])

  React.useEffect(() => {
    void load()
  }, [load])

  return (
    <div
      className="min-h-[calc(100vh-7rem)] space-y-6 rounded-lg bg-surface-base p-6"
      data-testid="moc-home"
    >
      <Panel>
        <PanelHeader>
          <PanelTitle>Maps of Content</PanelTitle>
        </PanelHeader>
        <PanelBody>
          {loading && showSkeleton ? (
            <SkeletonLines count={4} />
          ) : error ? (
            <ErrorState
              what={error}
              survived="Nothing was changed."
              onRetry={() => void load()}
              data-testid="moc-home-error"
            />
          ) : (
            <LinkedTable
              sections={toSections(pages)}
              emptyTitle="No maps authored yet"
              emptyDescription="A per-vertical map appears here once authored."
              data-testid="moc-home-table"
            />
          )}
        </PanelBody>
      </Panel>
    </div>
  )
}

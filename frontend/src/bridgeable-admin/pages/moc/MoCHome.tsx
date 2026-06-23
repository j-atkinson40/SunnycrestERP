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

function toSections(pages: MoCPageRecord[]): LinkedTableSection[] {
  if (pages.length === 0) return [{ section_id: "maps", title: "Maps", rows: [] }]
  return [
    {
      section_id: "maps",
      title: "Maps",
      description: "Authored navigation, one per vertical.",
      rows: pages
        .filter((p) => p.vertical)
        .map((p) => ({
          row_id: p.id,
          label: p.title,
          href: adminPath(`/maps/${p.vertical}`),
          available: true,
          icon: MapIcon,
          kindLabel: "Map",
        })),
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
    <div className="space-y-6 p-6" data-testid="moc-home">
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

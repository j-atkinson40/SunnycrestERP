/**
 * Maps of Content — per-vertical page surface (MoC Phase 1).
 *
 * Mounted at /maps/:vertical (admin tree, AdminLayout). Fetches the
 * context-resolved page (3-tier walk + reference resolution), maps each
 * builder row to a LinkedTable row — computing the deep-link href via
 * mocDeepLink → adminPath, null when the artifact resolved unavailable —
 * and renders it. Minimal authoring this phase: rename + "create starter"
 * when no page exists yet; row/artifact-picker authoring is MoC-2.
 */

import * as React from "react"
import { useParams } from "react-router-dom"
import {
  FileText,
  LayoutGrid,
  Layers,
  Workflow,
  type LucideIcon,
} from "lucide-react"

import { adminPath } from "@/bridgeable-admin/lib/admin-routes"
import { mocDeepLink } from "@/bridgeable-admin/lib/moc-deep-link"
import {
  createPage,
  readForContext,
  updatePage,
  type MoCResolvedPage,
} from "@/bridgeable-admin/services/moc-service"
import {
  LinkedTable,
  type LinkedTableSection,
} from "@/bridgeable-admin/components/moc/LinkedTable"
import { Panel, PanelBody, PanelHeader, PanelTitle } from "@/components/ui/panel"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { EmptyState } from "@/components/ui/empty-state"
import { ErrorState } from "@/components/ui/error-state"
import { SkeletonLines } from "@/components/ui/skeleton"
import { useDelayedLoading } from "@/hooks/use-delayed-loading"

const BUILDER_PRESENTATION: Record<
  string,
  { icon: LucideIcon; label: string }
> = {
  workflows: { icon: Workflow, label: "Workflow" },
  focuses: { icon: Layers, label: "Focus" },
  widgets: { icon: LayoutGrid, label: "Widget" },
  documents: { icon: FileText, label: "Document" },
}

/** Resolved page → LinkedTable sections (href computed, orphan → null). */
function toLinkedSections(page: MoCResolvedPage): LinkedTableSection[] {
  return page.sections.map((s) => ({
    section_id: s.section_id,
    title: s.title,
    description: s.description,
    rows: s.rows.map((r) => {
      const presentation = BUILDER_PRESENTATION[r.builder]
      const path = r.resolution.available
        ? mocDeepLink({
            builder: r.builder,
            artifact_id: r.artifact_id,
            routing: r.resolution.routing,
          })
        : null
      return {
        row_id: r.row_id,
        label: r.resolution.label || r.label,
        href: path ? adminPath(path) : null,
        available: r.resolution.available && path !== null,
        icon: presentation?.icon,
        kindLabel: presentation?.label ?? r.builder,
      }
    }),
  }))
}

export default function MoCPage() {
  const { vertical = "" } = useParams<{ vertical: string }>()
  const [page, setPage] = React.useState<MoCResolvedPage | null>(null)
  const [loading, setLoading] = React.useState(true)
  const [error, setError] = React.useState<string | null>(null)
  const [notFound, setNotFound] = React.useState(false)
  const [renaming, setRenaming] = React.useState(false)
  const [draftTitle, setDraftTitle] = React.useState("")
  const showSkeleton = useDelayedLoading(loading)

  const load = React.useCallback(async () => {
    setLoading(true)
    setError(null)
    setNotFound(false)
    try {
      const data = await readForContext({ vertical })
      setPage(data)
    } catch (e: unknown) {
      const status = (e as { response?: { status?: number } })?.response?.status
      if (status === 404) {
        setNotFound(true)
        setPage(null)
      } else {
        setError("Couldn't load this map.")
      }
    } finally {
      setLoading(false)
    }
  }, [vertical])

  React.useEffect(() => {
    void load()
  }, [load])

  const createStarter = async () => {
    await createPage({
      scope: "vertical_default",
      vertical,
      slug: `${vertical}-map`,
      title: `${vertical} map`,
      description: "Authored navigation for this vertical.",
      sections: [],
    })
    await load()
  }

  const saveRename = async () => {
    if (!page || !draftTitle.trim()) return
    await updatePage(page.id, { title: draftTitle.trim() })
    setRenaming(false)
    await load()
  }

  if (loading && showSkeleton) {
    return (
      <div className="p-6">
        <SkeletonLines count={5} />
      </div>
    )
  }

  if (error) {
    return (
      <div className="p-6">
        <ErrorState
          what={error}
          survived="Nothing was changed."
          onRetry={() => void load()}
          data-testid="moc-page-error"
        />
      </div>
    )
  }

  if (notFound) {
    return (
      <div className="p-6">
        <EmptyState
          variant="panel"
          title={`No map for ${vertical} yet`}
          description="Create a starter page, then add references from the builders (MoC-2)."
          action={
            <Button onClick={() => void createStarter()} data-testid="moc-create-starter">
              Create starter page
            </Button>
          }
        />
      </div>
    )
  }

  if (!page) return null

  return (
    <div className="space-y-6 p-6" data-testid="moc-page">
      <Panel>
        <PanelHeader>
          {renaming ? (
            <div className="flex items-center gap-2">
              <Input
                value={draftTitle}
                onChange={(e) => setDraftTitle(e.target.value)}
                className="max-w-xs"
                data-testid="moc-rename-input"
              />
              <Button size="sm" onClick={() => void saveRename()}>
                Save
              </Button>
              <Button
                size="sm"
                variant="ghost"
                onClick={() => setRenaming(false)}
              >
                Cancel
              </Button>
            </div>
          ) : (
            <div className="flex items-center gap-3">
              <PanelTitle data-testid="moc-page-title">{page.title}</PanelTitle>
              <Button
                size="sm"
                variant="ghost"
                onClick={() => {
                  setDraftTitle(page.title)
                  setRenaming(true)
                }}
                data-testid="moc-rename"
              >
                Rename
              </Button>
            </div>
          )}
        </PanelHeader>
        <PanelBody>
          {page.description ? (
            <p className="mb-4 text-body-sm text-content-muted">
              {page.description}
            </p>
          ) : null}
          <LinkedTable
            sections={toLinkedSections(page)}
            emptyTitle="No references yet"
            emptyDescription="Add references from the builders (MoC-2 authoring)."
            data-testid="moc-linked-table"
          />
        </PanelBody>
      </Panel>
    </div>
  )
}

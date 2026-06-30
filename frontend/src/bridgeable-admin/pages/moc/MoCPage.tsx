/**
 * Maps of Content — per-vertical page surface (MoC Phase 1 → manufacturing
 * polish Phase A).
 *
 * Mounted at /maps/:vertical (admin tree, AdminLayout). Fetches the
 * context-resolved page (3-tier walk + reference resolution), then GROUPS the
 * rows by builder TYPE into titled per-type cards (Phase A — the Notion model:
 * full-bleed two-pane + a card per builder type present, each entry a deep-link
 * into that artifact's builder). The grouping is data-driven: a new builder
 * type or a 2nd artifact-in-a-type renders with no code change. Minimal
 * authoring this phase: rename + "create starter"; row/artifact-picker
 * authoring + the task table are later arcs.
 *
 * Full-bleed: the two-pane breaks out of AdminLayout's px-6/py-6 wrapper
 * (-mx-6/-my-6) so the dark surface fills the content area edge-to-edge
 * (the "plant floor" treatment), bounded only by AdminLayout's shared
 * max-w-[1600px]. No centered card box.
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
  readTaskCatalog,
  updatePage,
  type MoCResolvedPage,
  type MoCTask,
} from "@/bridgeable-admin/services/moc-service"
import {
  MoCTypeCards,
  type MoCTypeCard,
} from "@/bridgeable-admin/components/moc/MoCTypeCards"
import { MoCTaskTable } from "@/bridgeable-admin/components/moc/MoCTaskTable"
import { MoCVerticalsRail } from "@/bridgeable-admin/components/moc/MoCVerticalsRail"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { EmptyState } from "@/components/ui/empty-state"
import { ErrorState } from "@/components/ui/error-state"
import { SkeletonLines } from "@/components/ui/skeleton"
import { useDelayedLoading } from "@/hooks/use-delayed-loading"

/** Builder type → card presentation (plural title + glyph). */
const CARD_TYPE: Record<string, { title: string; icon: LucideIcon }> = {
  workflows: { title: "Workflows", icon: Workflow },
  focuses: { title: "Focuses", icon: Layers },
  widgets: { title: "Widgets", icon: LayoutGrid },
  documents: { title: "Documents", icon: FileText },
}
/** Canonical card order; unknown builders render after, in first-seen order. */
const TYPE_ORDER = ["workflows", "focuses", "widgets", "documents"]

/**
 * Resolved page → per-type cards. Flattens every section's rows and groups by
 * builder, computing each entry's deep-link (orphan → null → muted). Data-
 * driven: N artifacts in a type → N entries; an unknown builder → its own card.
 */
export function toTypeCards(page: MoCResolvedPage): MoCTypeCard[] {
  const byBuilder = new Map<string, MoCTypeCard["entries"]>()
  for (const section of page.sections) {
    for (const r of section.rows) {
      const path = r.resolution.available
        ? mocDeepLink({
            builder: r.builder,
            artifact_id: r.artifact_id,
            routing: r.resolution.routing,
          })
        : null
      const entry = {
        row_id: r.row_id,
        label: r.resolution.label || r.label,
        href: path ? adminPath(path) : null,
        available: r.resolution.available && path !== null,
        unavailableReason: "orphan" as const,
      }
      const list = byBuilder.get(r.builder)
      if (list) list.push(entry)
      else byBuilder.set(r.builder, [entry])
    }
  }
  const known = TYPE_ORDER.filter((b) => byBuilder.has(b))
  const extra = [...byBuilder.keys()].filter((b) => !TYPE_ORDER.includes(b))
  return [...known, ...extra].map((builder) => ({
    builder,
    title: CARD_TYPE[builder]?.title ?? builder,
    icon: CARD_TYPE[builder]?.icon,
    entries: byBuilder.get(builder) ?? [],
  }))
}

export default function MoCPage() {
  const { vertical = "" } = useParams<{ vertical: string }>()
  const [page, setPage] = React.useState<MoCResolvedPage | null>(null)
  const [tasks, setTasks] = React.useState<MoCTask[]>([])
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
      // The task catalog is independent of the page; a failure here must not
      // break the cards. Empty array → the table self-hides.
      try {
        setTasks(await readTaskCatalog({ vertical }))
      } catch {
        setTasks([])
      }
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

  // After a task write (2b), refetch only the catalog — the page/cards are
  // untouched, so no need to re-walk the 3-tier resolver. Empty array on
  // failure keeps the table coherent.
  const reloadTasks = React.useCallback(async () => {
    try {
      setTasks(await readTaskCatalog({ vertical }))
    } catch {
      setTasks([])
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

  // The two-pane content varies by state; the rail is always beside it.
  let body: React.ReactNode = null
  if (loading && showSkeleton) {
    body = <SkeletonLines count={5} />
  } else if (error) {
    body = (
      <ErrorState
        what={error}
        survived="Nothing was changed."
        onRetry={() => void load()}
        data-testid="moc-page-error"
      />
    )
  } else if (notFound) {
    body = (
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
    )
  } else if (page) {
    body = (
      <div className="space-y-6">
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
            <Button size="sm" variant="ghost" onClick={() => setRenaming(false)}>
              Cancel
            </Button>
          </div>
        ) : (
          <div className="flex items-center gap-3">
            <h1
              className="text-h2 font-semibold text-content-strong"
              data-testid="moc-page-title"
            >
              {page.title}
            </h1>
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
        {page.description ? (
          <p className="text-body-sm text-content-muted">{page.description}</p>
        ) : null}
        <MoCTypeCards
          cards={toTypeCards(page)}
          emptyTitle="No references yet"
          emptyDescription="Add references from the builders (MoC-2 authoring)."
          data-testid="moc-type-cards"
        />
        <MoCTaskTable
          tasks={tasks}
          vertical={vertical}
          onChanged={() => void reloadTasks()}
          data-testid="moc-task-table"
        />
      </div>
    )
  }

  return (
    // A.1 full-page: AdminLayout marks /maps/:vertical full-bleed, so its
    // <main> is `flex min-h-0 flex-1` (full width, fills height below the nav).
    // This two-pane fills that main — flex-1 takes the full width past the
    // (now-absent) 1600px cap, and stretch fills the height so the dark surface
    // reaches the bottom edge (no light page showing through). Rail keeps its
    // sunken tone; content is the base surface. No centered card box.
    <div
      className="flex flex-1 bg-surface-base"
      data-testid="moc-page"
    >
      <MoCVerticalsRail />
      <div className="flex-1 space-y-6 p-6" data-testid="moc-page-content">
        {body}
      </div>
    </div>
  )
}

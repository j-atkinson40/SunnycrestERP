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
import { Link, useParams } from "react-router-dom"
import {
  Building2,
  FileText,
  LayoutGrid,
  Layers,
  Workflow,
  type LucideIcon,
} from "lucide-react"

import { adminApi } from "@/bridgeable-admin/lib/admin-api"
import { adminPath } from "@/bridgeable-admin/lib/admin-routes"
import { mocDeepLink } from "@/bridgeable-admin/lib/moc-deep-link"
import type { TenantSummary } from "@/bridgeable-admin/components/TenantPicker"
import {
  createPage,
  getOfferStates,
  readForContext,
  readTaskCatalog,
  updatePage,
  type MoCResolvedPage,
  type MoCTask,
  type OfferState,
} from "@/bridgeable-admin/services/moc-service"
import {
  FocusFamilyGlyph,
  MoCTypeCards,
  type MoCTypeCard,
} from "@/bridgeable-admin/components/moc/MoCTypeCards"
import { OfferDialog } from "@/bridgeable-admin/components/moc/OfferDialog"
import { MoCBreadcrumb } from "@/bridgeable-admin/components/moc/MoCBreadcrumb"
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
            // Prefer the resolver's rebound id (the ref-decay rebind): after
            // a version bump the stored id points at a retained snapshot; the
            // rebound id opens the lineage's ACTIVE row.
            artifact_id: r.resolution.artifact_id ?? r.artifact_id,
            routing: r.resolution.routing,
          })
        : null
      const entry = {
        row_id: r.row_id,
        label: r.resolution.label || r.label,
        href: path ? adminPath(path) : null,
        available: r.resolution.available && path !== null,
        unavailableReason: "orphan" as const,
        builder: r.builder,
        artifact_id: r.resolution.artifact_id ?? r.artifact_id,
        template_slug: r.resolution.routing.template_slug ?? null,
        // r122: the family icon (focuses + focus-cores resolutions carry it).
        icon: r.resolution.icon ?? null,
      }
      // focus-cores rows fold into the ONE Focuses card (the platform map
      // shows Tier 1 defaults + platform_default templates together); the
      // entry keeps its own builder for per-entry affordances (fork menu).
      const cardKey = r.builder === "focus-cores" ? "focuses" : r.builder
      const list = byBuilder.get(cardKey)
      if (list) list.push(entry)
      else byBuilder.set(cardKey, [entry])
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

/** The vertical's tenants as LINKS to their pages (MoC Hierarchy H-1 —
 * tenants are destinations, superseding the selector; the route is the state).
 * SEARCHABLE: the lookup caps at 100 rows, so a raw dump is unusable at scale
 * (the 2089-tenant dev DB made the investigation's ≤100-row caveat real) —
 * the search (server-side ILIKE via `q`) is how you reach any tenant. */
function TenantsCard({ vertical }: { vertical: string }) {
  const [tenants, setTenants] = React.useState<TenantSummary[]>([])
  const [q, setQ] = React.useState("")
  const debounceRef = React.useRef<ReturnType<typeof setTimeout> | null>(null)

  React.useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    let cancelled = false
    debounceRef.current = setTimeout(() => {
      adminApi
        .get<TenantSummary[]>("/api/platform/admin/tenants/lookup", {
          // P-1: vertical filters SERVER-SIDE — the old client-side filter
          // over a 100-row cross-vertical page left sparse verticals with a
          // near-empty default list. The client filter stays as a cheap
          // belt-and-suspenders against a stale backend.
          params: { q: q || undefined, limit: 100, vertical },
        })
        .then(({ data }) => {
          if (cancelled) return
          setTenants(
            data.filter((t) => (t.vertical ?? "").toLowerCase() === vertical.toLowerCase()),
          )
        })
        .catch(() => { if (!cancelled) setTenants([]) })
    }, q ? 250 : 0)
    return () => { cancelled = true }
  }, [vertical, q])

  const shown = tenants.slice(0, 30)
  return (
    <section className="space-y-2" data-testid="moc-tenants-card">
      <div className="flex items-center gap-3">
        <h2 className="flex items-center gap-1.5 text-h4 font-semibold text-content-strong">
          <Building2 size={16} className="text-content-muted" /> Tenants
        </h2>
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search tenants…"
          data-testid="moc-tenants-search"
          className="w-56 rounded-md border border-border-base bg-surface-raised px-2.5 py-1 text-body-sm text-content-base placeholder:text-content-subtle focus-visible:border-accent focus-visible:outline-none"
        />
      </div>
      {shown.length === 0 ? (
        <p className="text-body-sm text-content-subtle">
          {q ? `No tenants matching “${q}” in this vertical.` : "No tenants in this vertical yet."}
        </p>
      ) : (
        <>
          <ul className="flex flex-wrap gap-2">
            {shown.map((t) => (
              <li key={t.id}>
                <Link
                  to={adminPath(`/maps/${vertical}/${t.slug}`)}
                  className="inline-flex items-center gap-1.5 rounded-md border border-border-subtle bg-surface-elevated px-3 py-1.5 text-body-sm text-content-base hover:border-accent hover:text-accent"
                  data-testid={`moc-tenant-link-${t.slug}`}
                >
                  {t.name}
                  <span className="text-caption text-content-subtle">{t.slug}</span>
                </Link>
              </li>
            ))}
          </ul>
          {tenants.length > shown.length ? (
            <p className="text-caption text-content-subtle">
              Showing {shown.length} — search to narrow.
            </p>
          ) : null}
        </>
      )}
    </section>
  )
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
  // V-2 offered updates: per-slug offer state for the Focuses pills
  // (pending → badge; declined/behind → quiet gap chip, recallable) +
  // the open offer dialog.
  const [offerStates, setOfferStates] = React.useState<
    Record<string, OfferState>
  >({})
  const [activeOffer, setActiveOffer] = React.useState<{
    offerId: string
    label: string
  } | null>(null)
  const showSkeleton = useDelayedLoading(loading)

  // H-1 supersession: the vertical page is ALWAYS the defaults view (the
  // tenant selector + ?tenant= param retired). Tenant context is a
  // DESTINATION now — /maps/:vertical/:tenantSlug (MoCTenantPage), linked
  // from the Tenants card below. The default read path is unchanged
  // (non-regression pinned by test_no_tenant_returns_defaults_only).
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

  // Offer states follow the page's focuses refs (slug-keyed — lineage
  // identity survives version rotation). Quiet on failure: badges are
  // an enrichment, never a load blocker.
  const refreshOfferStates = React.useCallback(async (p: MoCResolvedPage) => {
    const slugs = [
      ...new Set(
        p.sections
          .flatMap((s) => s.rows)
          .filter((r) => r.builder === "focuses")
          .map((r) => r.resolution.routing.template_slug)
          .filter((s): s is string => Boolean(s)),
      ),
    ]
    try {
      setOfferStates(await getOfferStates(slugs))
    } catch {
      setOfferStates({})
    }
  }, [])

  React.useEffect(() => {
    if (page) void refreshOfferStates(page)
  }, [page, refreshOfferStates])

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
        {/* H-3: the breadcrumb spine (replaces the H-2 up-link stub) + the
            vertical-level Studio hang (the links audit — per-artifact editors
            are the cards' deep-links; this reaches the REST of Studio). */}
        <div className="flex items-center justify-between">
          <MoCBreadcrumb vertical={vertical} />
          <Link
            to={adminPath(`/studio/${vertical}`)}
            className="text-caption text-content-subtle hover:text-accent"
            data-testid="moc-vertical-studio-link"
          >
            Author in Studio →
          </Link>
        </div>
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
          renderEntry={(entry) => {
            // V-2: only focuses entries with an offer state render custom —
            // everything else falls through to the default link.
            const state = entry.template_slug
              ? offerStates[entry.template_slug]
              : undefined
            if (!state || !entry.available || !entry.href) return null
            const pending = state.offer_status === "pending"
            return (
              <span className="flex items-center gap-2">
                <Link
                  to={entry.href}
                  className="focus-ring-accent flex items-center gap-1.5 rounded-sm py-0.5 text-body-sm text-content-base hover:text-accent"
                >
                  <FocusFamilyGlyph icon={entry.icon} />
                  {entry.label}
                </Link>
                {pending ? (
                  <button
                    type="button"
                    onClick={() =>
                      state.offer_id &&
                      setActiveOffer({
                        offerId: state.offer_id,
                        label: entry.label,
                      })
                    }
                    className="focus-ring-accent inline-flex items-center gap-1 rounded-full bg-accent-subtle px-2 py-0.5 text-caption text-accent hover:bg-accent-muted"
                    title={`Update available — v${state.pinned_version} → v${state.core_version}`}
                    data-testid={`offer-badge-${entry.template_slug}`}
                  >
                    <span className="h-1.5 w-1.5 rounded-full bg-accent" />
                    update
                  </button>
                ) : (
                  // Declined or quietly behind: the gap DISCOVERABLE, not
                  // nagging — muted chip; click re-opens the offer (recall).
                  <button
                    type="button"
                    onClick={() =>
                      state.offer_id &&
                      setActiveOffer({
                        offerId: state.offer_id,
                        label: entry.label,
                      })
                    }
                    disabled={!state.offer_id}
                    className="rounded-sm text-caption text-content-subtle hover:text-content-muted disabled:cursor-default"
                    title="Based on an older default — click to review the offered update"
                    data-testid={`offer-gap-${entry.template_slug}`}
                  >
                    v{state.pinned_version} · core v{state.core_version}
                  </button>
                )}
              </span>
            )
          }}
          data-testid="moc-type-cards"
        />

        {/* V-2: the offer review — the diff IS the evidence-backed confirm. */}
        {activeOffer ? (
          <OfferDialog
            offerId={activeOffer.offerId}
            targetLabel={activeOffer.label}
            onClose={() => setActiveOffer(null)}
            onDecided={() => {
              setActiveOffer(null)
              void load() // labels/pins may have moved (accept version-bumps)
            }}
          />
        ) : null}

        {/* H-1 — tenants as DESTINATIONS: links down to each tenant's page. */}
        <TenantsCard vertical={vertical} />

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

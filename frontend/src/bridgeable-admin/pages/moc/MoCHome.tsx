/**
 * Maps of Content — home: THE PLATFORM MoC (MoC Hierarchy H-2).
 *
 * The admin front door renders the hierarchy's TOP — the resolved
 * platform_default page (the tier existed since Phase 1; seed_moc_platform
 * authors the first page into it) surrounded by the platform-level cards:
 * VERTICALS as the map's primary descent (live → linked; unbuilt → deliberate
 * coming-room), the CORE workflows' canonical home (the authored rows), the
 * cross-tenant RECENT FIRES pulse, counts-as-links (tenants / health), and
 * the PLATFORM task table (vertical-less tasks; Add-task authors
 * scope=platform_default — the coherence guard at platform scope).
 *
 * THE FIRST-RENDER DISCIPLINE (this is the login landing — every session's
 * first impression): no error-flash on the happy path (skeleton while
 * loading; each card fetches independently and fails QUIET); every empty
 * state says WHAT BELONGS THERE (deliberate room, never a no-data shrug);
 * the frame renders first, cards fill progressively.
 */

import * as React from "react"
import { Link, useNavigate } from "react-router-dom"
import { toast } from "sonner"
import { Activity, ArrowUpRight, Building2, Map as MapIcon } from "lucide-react"

import { adminApi } from "@/bridgeable-admin/lib/admin-api"
import { adminPath } from "@/bridgeable-admin/lib/admin-routes"
import {
  listMoCFires,
  readForContext,
  readTaskCatalog,
  type MoCResolvedPage,
  type MoCScheduleRun,
  type MoCTask,
} from "@/bridgeable-admin/services/moc-service"
import { MoCFiresCard } from "@/bridgeable-admin/components/moc/MoCFiresCard"
import { MoCTaskTable } from "@/bridgeable-admin/components/moc/MoCTaskTable"
import {
  KNOWN_VERTICALS,
  MoCVerticalsRail,
} from "@/bridgeable-admin/components/moc/MoCVerticalsRail"
import {
  MoCTypeCards,
  type MoCTypeCardEntry,
} from "@/bridgeable-admin/components/moc/MoCTypeCards"
import { ForkMenu } from "@/bridgeable-admin/components/moc/ForkMenu"
import { PublishDialog } from "@/bridgeable-admin/components/moc/PublishDialog"
import { VariationFlowDialog } from "@/bridgeable-admin/components/moc/VariationFlowDialog"
import { mocDeepLink } from "@/bridgeable-admin/lib/moc-deep-link"
import { toTypeCards } from "./MoCPage"
import { SkeletonLines } from "@/components/ui/skeleton"
import { useDelayedLoading } from "@/hooks/use-delayed-loading"

/** The map's primary descent — every vertical as a card. Live maps link down;
 * unbuilt ones read as deliberate coming-room (never a broken link). */
function VerticalsCards({ seededSlugs }: { seededSlugs: Set<string> }) {
  return (
    <section className="space-y-2" data-testid="moc-platform-verticals">
      <h2 className="flex items-center gap-1.5 text-h4 font-semibold text-content-strong">
        <MapIcon size={16} className="text-content-muted" /> Verticals
      </h2>
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {KNOWN_VERTICALS.map((v) => {
          const live = seededSlugs.has(v.slug)
          return live ? (
            <Link
              key={v.slug}
              to={adminPath(`/maps/${v.slug}`)}
              className="group rounded-lg border border-border-subtle bg-surface-elevated p-4 hover:border-accent"
              data-testid={`moc-platform-vertical-${v.slug}`}
            >
              <div className="flex items-center justify-between">
                <span className="font-medium text-content-strong group-hover:text-accent">
                  {v.label}
                </span>
                <ArrowUpRight size={14} className="text-content-subtle group-hover:text-accent" />
              </div>
              <p className="mt-1 text-caption text-content-muted">Open the map</p>
            </Link>
          ) : (
            <div
              key={v.slug}
              className="rounded-lg border border-dashed border-border-base bg-surface-base p-4"
              data-testid={`moc-platform-vertical-${v.slug}`}
            >
              <span className="font-medium text-content-muted">{v.label}</span>
              <p className="mt-1 text-caption text-content-subtle">
                Map coming — this vertical's home when its map is authored.
              </p>
            </div>
          )
        })}
      </div>
    </section>
  )
}

/** Counts-as-links + the OPERATIONS row (the H-3 links audit): every
 * platform-level admin destination hangs off the map (the spine principle —
 * the map links to things; things stay themselves). These DUPLICATE the
 * header deliberately: the header is the task-interrupt shortcut layer; the
 * map is where they belong in the structure. */
const PLATFORM_DESTINATIONS: ReadonlyArray<{ label: string; path: string }> = [
  { label: "Studio", path: "/studio" },
  { label: "Migrations", path: "/migrations" },
  { label: "Deployments", path: "/deployments" },
  { label: "Staging", path: "/staging" },
  { label: "Audit", path: "/audit" },
  { label: "Feature flags", path: "/feature-flags" },
  { label: "Telemetry", path: "/telemetry" },
  { label: "Verticals registry", path: "/verticals" },
]

function PlatformLinksStrip({ tenantTotal }: { tenantTotal: number | null }) {
  return (
    <div className="space-y-1.5" data-testid="moc-platform-links">
      <div className="flex items-center gap-4">
        <Link
          to={adminPath("/tenants")}
          className="inline-flex items-center gap-1.5 text-body-sm text-content-muted hover:text-accent"
        >
          <Building2 size={14} />
          {tenantTotal !== null ? `${tenantTotal} tenants` : "Tenants"}
        </Link>
        <Link
          to={adminPath("/health")}
          className="inline-flex items-center gap-1.5 text-body-sm text-content-muted hover:text-accent"
        >
          <Activity size={14} /> Health
        </Link>
      </div>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1" data-testid="moc-platform-operations">
        {PLATFORM_DESTINATIONS.map((d) => (
          <Link
            key={d.path}
            to={adminPath(d.path)}
            className="text-caption text-content-subtle hover:text-accent"
          >
            {d.label}
          </Link>
        ))}
      </div>
    </div>
  )
}

export default function MoCHome() {
  const navigate = useNavigate()
  const [page, setPage] = React.useState<MoCResolvedPage | null>(null)
  const [notAuthored, setNotAuthored] = React.useState(false)
  const [tasks, setTasks] = React.useState<MoCTask[]>([])
  const [fires, setFires] = React.useState<MoCScheduleRun[]>([])
  const [tenantTotal, setTenantTotal] = React.useState<number | null>(null)
  const [seededSlugs, setSeededSlugs] = React.useState<Set<string>>(new Set())
  const [loading, setLoading] = React.useState(true)
  // The fork menu's "Create a variation" target (null = flow closed). The
  // guided flow dialog consumes this (Focus Variations V-1).
  const [variationSource, setVariationSource] =
    React.useState<MoCTypeCardEntry | null>(null)
  // V-2: the publish dialog's target (null = closed).
  const [publishSource, setPublishSource] =
    React.useState<MoCTypeCardEntry | null>(null)
  const showSkeleton = useDelayedLoading(loading)

  const loadTasks = React.useCallback(async () => {
    try {
      setTasks(await readTaskCatalog({ scope: "platform_default" }))
    } catch {
      setTasks([]) // quiet — the table renders its deliberate empty
    }
  }, [])

  React.useEffect(() => {
    let cancelled = false
    // The frame renders immediately; every card fills independently and fails
    // QUIET (the first-render discipline — no error-flash on the landing).
    readForContext({})
      .then((data) => { if (!cancelled) setPage(data) })
      .catch(() => { if (!cancelled) setNotAuthored(true) })
      .finally(() => { if (!cancelled) setLoading(false) })
    void loadTasks()
    listMoCFires({ limit: 8 })
      .then((f) => { if (!cancelled) setFires(f) })
      .catch(() => { if (!cancelled) setFires([]) })
    adminApi
      .get<{ total?: number }>("/api/platform/tenants/", { params: { limit: 1 } })
      .then(({ data }) => { if (!cancelled) setTenantTotal(data.total ?? null) })
      .catch(() => { if (!cancelled) setTenantTotal(null) })
    // Which verticals have maps (the rail knows the same — one cheap list call).
    adminApi
      .get<Array<{ vertical: string | null }>>("/api/platform/admin/moc/", {
        params: { scope: "vertical_default" },
      })
      .then(({ data }) => {
        if (cancelled) return
        setSeededSlugs(new Set(data.map((p) => p.vertical).filter(Boolean) as string[]))
      })
      .catch(() => { if (!cancelled) setSeededSlugs(new Set()) })
    return () => { cancelled = true }
  }, [loadTasks])

  return (
    // Hierarchy polish: the SAME full-bleed treatment as the vertical/tenant
    // maps (AdminLayout's isFullBleedRoute now matches the exact root) — the
    // level transition doesn't change the frame. The §18 surface stays.
    <div
      className="flex flex-1 bg-surface-base"
      data-testid="moc-home"
    >
      <MoCVerticalsRail />
      <div className="flex-1 space-y-6 overflow-y-auto p-6" data-testid="moc-home-content">
        {loading && showSkeleton ? (
          <SkeletonLines count={5} />
        ) : (
          <>
            <div>
              <h1 className="text-h2 font-semibold text-content-strong" data-testid="moc-platform-title">
                {page?.title ?? "Bridgeable"}
              </h1>
              <p className="mt-1 text-body-sm text-content-muted">
                {page?.description ??
                  "The platform, whole — every vertical, the core machinery, and what's firing."}
              </p>
              <div className="mt-2">
                <PlatformLinksStrip tenantTotal={tenantTotal} />
              </div>
            </div>

            <VerticalsCards seededSlugs={seededSlugs} />

            {/* The core workflows' canonical home — the authored rows. The
                Focuses card's Tier 1 defaults render through the FORK MENU
                (Focus Variations V-1): edit-with-blast-radius vs create a
                variation — the consequence legible at the moment of choice. */}
            {page ? (
              <MoCTypeCards
                cards={toTypeCards(page)}
                emptyTitle="Core machinery lives here"
                emptyDescription="Cross-vertical workflows — Month-End Close, AR Collections — get their canonical home on this map when authored."
                renderEntry={(entry: MoCTypeCardEntry) =>
                  entry.builder === "focus-cores" && entry.available ? (
                    <ForkMenu
                      entry={entry}
                      onCreateVariation={setVariationSource}
                      onPublish={setPublishSource}
                    />
                  ) : null
                }
                data-testid="moc-platform-cards"
              />
            ) : notAuthored ? (
              <p
                className="rounded-lg border border-dashed border-border-base bg-surface-elevated px-4 py-6 text-body-sm text-content-subtle"
                data-testid="moc-platform-not-authored"
              >
                The platform map hasn't been authored yet — the core workflows'
                canonical home appears here once <code>seed_moc_platform</code> runs.
              </p>
            ) : null}

            {/* The platform task table — vertical-less tasks. Deliberate room:
                Add-task here authors scope=platform_default. */}
            <div data-testid="moc-platform-tasks">
              <MoCTaskTable
                tasks={tasks}
                vertical=""
                platformScope
                onChanged={() => void loadTasks()}
              />
              {tasks.length === 0 ? (
                <p className="mt-2 text-caption text-content-subtle" data-testid="moc-platform-tasks-room">
                  Platform-wide tasks live here — the home for automations that
                  belong to no single vertical.
                </p>
              ) : null}
            </div>

            <MoCFiresCard
              fires={fires}
              emptyText="Platform activity lands here — every MoC schedule and event fire, across all tenants."
              data-testid="moc-platform-fires"
            />

            {/* V-2: the publish dialog — the explicit release boundary. */}
            {publishSource ? (
              <PublishDialog
                source={publishSource}
                onClose={() => setPublishSource(null)}
                onPublished={(offersCreated) => {
                  setPublishSource(null)
                  toast.success(
                    offersCreated === 0
                      ? "Published — no downstream variations to offer."
                      : `Published — ${offersCreated} variation${
                          offersCreated === 1 ? "" : "s"
                        } offered the update.`,
                  )
                }}
              />
            ) : null}

            {/* The guided variation flow — lands the operator in the editor
                on the new variation; the refs are already on the maps. */}
            {variationSource ? (
              <VariationFlowDialog
                source={variationSource}
                onClose={() => setVariationSource(null)}
                onCreated={(r) => {
                  setVariationSource(null)
                  const path = mocDeepLink({
                    builder: "focuses",
                    artifact_id: r.template_id,
                    routing: {
                      vertical: r.home_vertical,
                      template_slug: r.template_slug,
                    },
                  })
                  if (path) navigate(adminPath(path))
                }}
              />
            ) : null}
          </>
        )}
      </div>
    </div>
  )
}

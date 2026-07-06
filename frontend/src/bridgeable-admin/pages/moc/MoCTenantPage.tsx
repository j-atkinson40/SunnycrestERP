/**
 * MoC Tenant page (MoC Hierarchy H-1) — /maps/:vertical/:tenantSlug.
 *
 * The tenant as a DESTINATION (superseding the vertical page's tenant
 * selector): the route IS the state — deep-linkable, no picker. Assembled
 * from the tenant-view arc's machinery, transferred verbatim:
 * - the MERGED task table (vertical defaults + THIS tenant's overrides,
 *   overrides pilled) via readTaskCatalog(tenant_id) — the sweep-honest
 *   "what runs for this tenant", with trigger chips + Live/Dry-run toggles;
 * - the tenant-aware Add-task (creates scope=tenant_override for THIS tenant
 *   — the coherence guard, unchanged in MoCTaskTable/TaskEditorPanel);
 * - artifact cards via the existing resolve walk — a tenant's OWN MoCPage
 *   when authored (zero exist today), else the vertical's defaults with an
 *   honest source note (no inflation);
 * - the tenant-fires card (the unified fires log filtered to this company).
 *
 * Breadcrumb spine is H-3; H-1 ships the working "up" link to the vertical map.
 */

import * as React from "react"
import { Link, useParams } from "react-router-dom"
import { ArrowLeft, Building2, Radio } from "lucide-react"

import { adminApi } from "@/bridgeable-admin/lib/admin-api"
import { adminPath } from "@/bridgeable-admin/lib/admin-routes"
import type { TenantSummary } from "@/bridgeable-admin/components/TenantPicker"
import {
  listMoCFires,
  readForContext,
  readTaskCatalog,
  type MoCResolvedPage,
  type MoCScheduleRun,
  type MoCTask,
} from "@/bridgeable-admin/services/moc-service"
import { MoCTypeCards } from "@/bridgeable-admin/components/moc/MoCTypeCards"
import { MoCTaskTable } from "@/bridgeable-admin/components/moc/MoCTaskTable"
import { MoCVerticalsRail } from "@/bridgeable-admin/components/moc/MoCVerticalsRail"
import { toTypeCards } from "./MoCPage"
import { ErrorState } from "@/components/ui/error-state"
import { SkeletonLines } from "@/components/ui/skeleton"
import { useDelayedLoading } from "@/hooks/use-delayed-loading"

/** Compact recent-fires list for THIS tenant (schedule + event, dry-run/live). */
function TenantFiresCard({ fires }: { fires: MoCScheduleRun[] }) {
  return (
    <section className="space-y-2" data-testid="moc-tenant-fires">
      <h2 className="text-h4 font-semibold text-content-strong">Recent fires</h2>
      {fires.length === 0 ? (
        <p className="text-body-sm text-content-subtle">
          Nothing has fired for this tenant yet — schedule and event fires land
          here (dry-run and live).
        </p>
      ) : (
        <ul className="divide-y divide-border-subtle rounded-md border border-border-subtle">
          {fires.map((f) => (
            <li key={f.run_id} className="flex items-center gap-2 px-3 py-1.5 text-body-sm">
              <span
                className={`inline-flex items-center rounded-full px-1.5 py-0.5 text-caption ${
                  f.is_dry_run
                    ? "bg-surface-sunken text-content-muted"
                    : "bg-accent text-content-on-accent font-semibold"
                }`}
              >
                {f.is_dry_run ? "Dry-run" : "LIVE"}
              </span>
              <span className="text-content-base">{f.task_name ?? "—"}</span>
              <span className="text-content-subtle">
                {f.source === "event" ? `event ${f.event_key ?? ""}` : "schedule"}
              </span>
              <span className="ml-auto text-caption text-content-subtle">
                {f.started_at ? new Date(f.started_at).toLocaleString() : ""}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

export default function MoCTenantPage() {
  const { vertical = "", tenantSlug = "" } = useParams<{
    vertical: string
    tenantSlug: string
  }>()
  const [tenant, setTenant] = React.useState<TenantSummary | null>(null)
  const [tenantMissing, setTenantMissing] = React.useState(false)
  const [page, setPage] = React.useState<MoCResolvedPage | null>(null)
  const [tasks, setTasks] = React.useState<MoCTask[]>([])
  const [fires, setFires] = React.useState<MoCScheduleRun[]>([])
  const [loading, setLoading] = React.useState(true)
  const [error, setError] = React.useState<string | null>(null)
  const showSkeleton = useDelayedLoading(loading)

  // The route is the state: resolve :tenantSlug → the tenant (exact match).
  React.useEffect(() => {
    let cancelled = false
    setTenantMissing(false)
    setTenant(null)
    adminApi
      .get<TenantSummary[]>("/api/platform/admin/tenants/lookup", {
        params: { q: tenantSlug },
      })
      .then(({ data }) => {
        if (cancelled) return
        const hit = data.find((t) => t.slug === tenantSlug) ?? null
        if (hit) setTenant(hit)
        else setTenantMissing(true)
      })
      .catch(() => { if (!cancelled) setTenantMissing(true) })
    return () => { cancelled = true }
  }, [tenantSlug])

  const tenantId = tenant?.id
  const load = React.useCallback(async () => {
    if (!tenantId) return
    setLoading(true)
    setError(null)
    try {
      const data = await readForContext({ vertical, tenant_id: tenantId })
      setPage(data)
      try {
        setTasks(await readTaskCatalog({ vertical, tenant_id: tenantId }))
      } catch {
        setTasks([])
      }
      try {
        setFires(await listMoCFires({ company_id: tenantId, limit: 10 }))
      } catch {
        setFires([])
      }
    } catch {
      setError("Couldn't load this tenant's map.")
    } finally {
      setLoading(false)
    }
  }, [vertical, tenantId])

  const reloadTasks = React.useCallback(async () => {
    if (!tenantId) return
    try {
      setTasks(await readTaskCatalog({ vertical, tenant_id: tenantId }))
    } catch {
      setTasks([])
    }
  }, [vertical, tenantId])

  React.useEffect(() => {
    void load()
  }, [load])

  const upHref = adminPath(`/maps/${vertical}`)

  let body: React.ReactNode = null
  if (tenantMissing) {
    body = (
      <ErrorState
        what={`No tenant "${tenantSlug}" in ${vertical}.`}
        survived="Nothing was changed."
        data-testid="moc-tenant-missing"
      />
    )
  } else if (loading && showSkeleton) {
    body = <SkeletonLines count={5} />
  } else if (error) {
    body = (
      <ErrorState what={error} survived="Nothing was changed." onRetry={() => void load()} />
    )
  } else if (tenant && page) {
    const tenantHasOwnPage = page.scope === "tenant_override"
    body = (
      <div className="space-y-6">
        {/* Identity strip + the up-link (the H-1 breadcrumb stub). */}
        <div>
          <Link
            to={upHref}
            className="inline-flex items-center gap-1 text-body-sm text-content-muted hover:text-content-base"
            data-testid="moc-tenant-up-link"
          >
            <ArrowLeft size={14} /> {vertical} map
          </Link>
          <div className="mt-2 flex items-center gap-3">
            <Building2 size={20} className="text-accent" />
            <h1 className="text-h2 font-semibold text-content-strong" data-testid="moc-tenant-title">
              {tenant.name}
            </h1>
            <span className="rounded-full bg-surface-sunken px-2 py-0.5 text-caption text-content-muted">
              {tenant.slug} · {vertical}
            </span>
          </div>
          <p className="mt-1 flex items-center gap-1.5 text-body-sm text-content-muted">
            <Radio size={13} className="text-accent" />
            What runs for this tenant, and which of it is live.
          </p>
        </div>

        {/* Artifact cards — the tenant's OWN page when authored, else the
            vertical's defaults, stated honestly. */}
        <p className="text-caption text-content-subtle" data-testid="moc-tenant-cards-source">
          {tenantHasOwnPage
            ? `${tenant.name} has its own map page — these cards replace the ${vertical} defaults.`
            : `Showing the ${vertical} defaults — this tenant has no map page of its own yet.`}
        </p>
        <MoCTypeCards
          cards={toTypeCards(page)}
          emptyTitle="No references yet"
          emptyDescription="Add references from the builders."
          data-testid="moc-tenant-type-cards"
        />

        {/* The MERGED task table — defaults + this tenant's overrides
            (pilled), trigger chips + Live toggles, tenant-aware Add-task.
            The tenant-view machinery, transferred verbatim. */}
        <MoCTaskTable
          tasks={tasks}
          vertical={vertical}
          activeTenant={tenant}
          onChanged={() => void reloadTasks()}
          data-testid="moc-tenant-task-table"
        />

        <TenantFiresCard fires={fires} />
      </div>
    )
  }

  return (
    <div className="flex flex-1 bg-surface-base" data-testid="moc-tenant-page">
      <MoCVerticalsRail />
      <div className="flex-1 space-y-6 p-6" data-testid="moc-tenant-page-content">
        {body}
      </div>
    </div>
  )
}

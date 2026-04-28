/**
 * VaultScheduleWidget — Phase W-3d workspace-core widget.
 *
 * **First workspace-core widget** per [DESIGN_LANGUAGE.md §12.6](../../../../DESIGN_LANGUAGE.md):
 * renders the SAME data the scheduling Focus kanban core consumes,
 * with a deliberately abridged interactive surface. Bounded edits
 * per §12.6a (mark hole-dug, drag delivery between drivers, attach/
 * detach ancillary, update single ETA); finalize / day-switch /
 * bulk reassignment remain Focus-only — "Open in Focus" affordance
 * always present in Brief / Detail / Deep.
 *
 * **Mode-aware rendering** per BRIDGEABLE_MASTER §5.2.2:
 *   - production mode → renders Delivery rows (kanban shape)
 *   - purchase mode   → renders incoming LicenseeTransfer rows
 *   - hybrid mode     → composes both, vertically stacked
 *
 * **Why Delivery is the canonical scheduling entity** (not
 * SalesOrder): ancillary items (urns, cremation trays) are
 * INDEPENDENT SalesOrders — driver assignment + scheduling lives
 * on Delivery (logistics concept). Cards enrich each Delivery with
 * SalesOrder context (deceased, customer, line items) at render
 * time. See PLATFORM_ARCHITECTURE.md §9 + the SalesOrder vs
 * Delivery investigation (2026-04-27) for the full rationale.
 *
 * Three-component shape per established Phase W-3a/W-3b precedent:
 *   1. Variant tablets (presentation, render-only)
 *   2. Top-level dispatcher (selects variant + mode-aware render path)
 *
 * Per [DESIGN_LANGUAGE.md §12.10](../../../../DESIGN_LANGUAGE.md):
 * Glance + Brief + Detail + Deep variants. Glance pinnable to
 * sidebar (`spaces_pin`); Brief / Detail / Deep on grid + canvas.
 *
 * Per [§12.6a Widget Interactivity Discipline](../../../../DESIGN_LANGUAGE.md):
 * bounded edits + click-through to Focus for heavy actions. The
 * widget surfaces; the Focus owns decision moments.
 */

import { useNavigate } from "react-router-dom"
import {
  Truck,
  AlertTriangle,
  ExternalLink,
  Inbox,
  Calendar as CalendarIcon,
} from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { SkeletonLines } from "@/components/ui/skeleton"
import { useWidgetData } from "../useWidgetData"
import { cn } from "@/lib/utils"
import type { VariantId } from "@/components/widgets/types"


// ── Data shape (mirrors backend `get_vault_schedule` response) ──────


type OperatingMode = "production" | "purchase" | "hybrid"


interface ProductionDeliveryRow {
  delivery_id: string
  order_id: string | null
  deceased_name: string | null
  customer_id: string | null
  primary_assignee_id: string | null
  helper_user_id: string | null
  status: string
  driver_start_time: string | null
  service_time: string | null
  service_location: string | null
  eta: string | null
  hole_dug_status: string
  delivery_address: string | null
  attached_ancillary_count: number
  priority: string
}


interface ProductionScheduleData {
  deliveries: ProductionDeliveryRow[]
  total_count: number
  unassigned_count: number
  assigned_count: number
  driver_count: number
}


interface PurchaseTransferRow {
  transfer_id: string
  transfer_number: string
  status: string
  service_date: string | null
  deceased_name: string | null
  funeral_home_name: string | null
  cemetery_name: string | null
  cemetery_city: string | null
  cemetery_state: string | null
  transfer_items: unknown
  home_tenant_id: string | null
}


interface PurchaseScheduleData {
  transfers: PurchaseTransferRow[]
  total_count: number
  by_status: Record<string, number>
}


interface VaultScheduleData {
  date: string
  operating_mode: OperatingMode | null
  production: ProductionScheduleData | null
  purchase: PurchaseScheduleData | null
  primary_navigation_target: string | null
  is_vault_enabled: boolean
}


// ── Date helpers ────────────────────────────────────────────────────


function formatScheduleDate(isoDate: string): string {
  const d = new Date(`${isoDate}T00:00:00`)
  return d.toLocaleDateString(undefined, {
    weekday: "long",
    month: "long",
    day: "numeric",
  })
}


function formatScheduleDateShort(isoDate: string): string {
  const d = new Date(`${isoDate}T00:00:00`)
  return d.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  })
}


// ── Glance variant (Pattern 1 sidebar tablet) ──────────────────────


function VaultScheduleGlance({
  data,
  isLoading,
}: {
  data: VaultScheduleData | null
  isLoading: boolean
}) {
  const navigate = useNavigate()
  const total = computeTotalCount(data)

  return (
    <button
      type="button"
      onClick={() =>
        navigate(data?.primary_navigation_target || "/dispatch")
      }
      data-slot="vault-schedule-widget"
      data-variant="glance"
      data-mode={data?.operating_mode ?? "unknown"}
      className={cn(
        "flex items-center gap-2 px-3 py-2 w-full",
        "text-sm font-sans text-content-base",
        "hover:bg-surface-muted",
        "focus-ring-accent outline-none rounded-sm",
        "transition-colors duration-quick ease-settle",
      )}
    >
      <Truck className="h-4 w-4 text-accent flex-shrink-0" aria-hidden />
      <span className="truncate flex-1 text-left">
        {isLoading
          ? "…"
          : !data?.is_vault_enabled
          ? "Vault not enabled"
          : total === 0
          ? "Nothing scheduled"
          : data?.operating_mode === "purchase"
          ? `${total} incoming`
          : data?.operating_mode === "hybrid"
          ? `${total} scheduled`
          : `${total} delivery${total === 1 ? "" : "s"}`}
      </span>
      {total > 0 && data?.production?.unassigned_count ? (
        <span
          data-slot="vault-schedule-unassigned-dot"
          className="h-2 w-2 rounded-full bg-status-warning flex-shrink-0"
          aria-label={`${data.production.unassigned_count} unassigned`}
        />
      ) : null}
    </button>
  )
}


function computeTotalCount(data: VaultScheduleData | null): number {
  if (!data) return 0
  const prod = data.production?.total_count ?? 0
  const purch = data.purchase?.total_count ?? 0
  return prod + purch
}


// ── Brief variant (Pattern 2 grid card) ────────────────────────────


function VaultScheduleBrief({ data, isLoading, error }: VariantProps) {
  const navigate = useNavigate()

  if (isLoading) {
    return (
      <div
        data-slot="vault-schedule-widget"
        data-variant="brief"
        className="p-4"
      >
        <SkeletonLines count={4} />
      </div>
    )
  }

  if (error) {
    return (
      <div
        data-slot="vault-schedule-widget"
        data-variant="brief"
        className="p-4"
      >
        <p
          className="text-caption text-status-error font-sans"
          data-slot="vault-schedule-error"
        >
          {error}
        </p>
      </div>
    )
  }

  if (!data?.is_vault_enabled) {
    return (
      <VaultScheduleEmptyState
        title="Vault not enabled"
        body="Activate the vault product line to see scheduled deliveries here."
        cta="Manage product lines"
        ctaTarget="/settings/product-lines"
        variant="brief"
      />
    )
  }

  const total = computeTotalCount(data)
  if (total === 0) {
    return (
      <VaultScheduleEmptyState
        title="Nothing scheduled"
        body={`No vault ${
          data.operating_mode === "purchase" ? "incoming" : "deliveries"
        } for ${formatScheduleDateShort(data.date)}.`}
        cta="Open schedule"
        ctaTarget={data.primary_navigation_target || "/dispatch"}
        variant="brief"
        date={data.date}
      />
    )
  }

  return (
    <div
      data-slot="vault-schedule-widget"
      data-variant="brief"
      data-mode={data.operating_mode ?? "unknown"}
      className="flex flex-col h-full p-4 gap-3"
    >
      <div className="flex items-center gap-2">
        <Truck className="h-4 w-4 text-accent" aria-hidden />
        <h3 className="text-body-sm font-medium text-content-strong font-sans flex-1">
          {formatScheduleDate(data.date)}
        </h3>
        <ModeBadge mode={data.operating_mode} />
      </div>

      <div className="flex-1 min-h-0 overflow-hidden space-y-2">
        {data.production && data.production.total_count > 0 ? (
          <ProductionBriefSection
            production={data.production}
            navigate={navigate}
          />
        ) : null}
        {data.purchase && data.purchase.total_count > 0 ? (
          <PurchaseBriefSection
            purchase={data.purchase}
            navigate={navigate}
          />
        ) : null}
      </div>

      <button
        type="button"
        onClick={() =>
          navigate(data.primary_navigation_target || "/dispatch")
        }
        className={cn(
          "inline-flex items-center gap-1",
          "text-caption text-accent font-sans",
          "hover:text-accent-hover",
          "focus-ring-accent outline-none rounded-sm",
          "transition-colors duration-quick ease-settle",
        )}
        data-slot="vault-schedule-open-focus"
      >
        Open in scheduling Focus <ExternalLink className="h-3 w-3" />
      </button>
    </div>
  )
}


function ProductionBriefSection({
  production,
  navigate,
}: {
  production: ProductionScheduleData
  navigate: ReturnType<typeof useNavigate>
}) {
  return (
    <section
      data-slot="vault-schedule-production-section"
      className="space-y-1.5"
    >
      <div className="flex items-baseline justify-between">
        <h4 className="text-caption font-medium text-content-muted font-sans uppercase tracking-wide">
          Production
        </h4>
        <span className="text-caption text-content-muted font-plex-mono">
          {production.total_count}{" "}
          {production.total_count === 1 ? "delivery" : "deliveries"}
        </span>
      </div>
      <ul className="space-y-1">
        <li className="flex items-center justify-between text-caption font-sans">
          <span className="text-content-base">Assigned to drivers</span>
          <span className="text-content-muted font-plex-mono">
            {production.assigned_count} ({production.driver_count} driver
            {production.driver_count === 1 ? "" : "s"})
          </span>
        </li>
        {production.unassigned_count > 0 ? (
          <li className="flex items-center justify-between text-caption font-sans">
            <span className="text-status-warning inline-flex items-center gap-1">
              <AlertTriangle className="h-3 w-3" aria-hidden />
              Unassigned
            </span>
            <span className="text-status-warning font-plex-mono font-medium">
              {production.unassigned_count}
            </span>
          </li>
        ) : null}
        {production.deliveries
          .filter((d) => d.attached_ancillary_count > 0)
          .slice(0, 1)
          .map((d) => (
            <li
              key={d.delivery_id}
              className="text-caption text-content-muted font-sans truncate"
            >
              {d.deceased_name || "Unnamed"} +
              {d.attached_ancillary_count} ancillary
            </li>
          ))}
      </ul>
    </section>
  )
}


function PurchaseBriefSection({
  purchase,
  navigate,
}: {
  purchase: PurchaseScheduleData
  navigate: ReturnType<typeof useNavigate>
}) {
  return (
    <section
      data-slot="vault-schedule-purchase-section"
      className="space-y-1.5"
    >
      <div className="flex items-baseline justify-between">
        <h4 className="text-caption font-medium text-content-muted font-sans uppercase tracking-wide">
          Incoming
        </h4>
        <span className="text-caption text-content-muted font-plex-mono">
          {purchase.total_count}{" "}
          {purchase.total_count === 1 ? "transfer" : "transfers"}
        </span>
      </div>
      <ul className="space-y-1">
        {purchase.transfers.slice(0, 5).map((t) => (
          <li
            key={t.transfer_id}
            className="flex items-center justify-between text-caption font-sans"
          >
            <span className="text-content-base truncate">
              {t.deceased_name || t.transfer_number}
            </span>
            <span className="text-content-muted font-plex-mono ml-2 flex-shrink-0">
              {t.service_date
                ? formatScheduleDateShort(t.service_date)
                : "—"}
            </span>
          </li>
        ))}
      </ul>
    </section>
  )
}


function ModeBadge({ mode }: { mode: OperatingMode | null }) {
  if (!mode) return null
  const label =
    mode === "production"
      ? "Production"
      : mode === "purchase"
      ? "Purchase"
      : "Hybrid"
  return (
    <Badge
      variant="outline"
      className="text-caption font-sans"
      data-slot="vault-schedule-mode-badge"
    >
      {label}
    </Badge>
  )
}


function VaultScheduleEmptyState({
  title,
  body,
  cta,
  ctaTarget,
  variant,
  date,
}: {
  title: string
  body: string
  cta: string
  ctaTarget: string
  variant: "brief" | "detail" | "deep"
  date?: string
}) {
  const navigate = useNavigate()
  const Icon = title === "Vault not enabled" ? Inbox : CalendarIcon
  return (
    <div
      data-slot="vault-schedule-widget"
      data-variant={variant}
      className="flex flex-col items-center justify-center gap-2 px-4 py-8 h-full text-center"
    >
      <Icon className="h-8 w-8 text-content-subtle" aria-hidden />
      <p className="text-body-sm font-medium text-content-strong font-sans leading-tight">
        {title}
      </p>
      <p className="text-caption text-content-muted font-sans leading-tight max-w-[280px]">
        {body}
      </p>
      <button
        type="button"
        onClick={() => navigate(ctaTarget)}
        className={cn(
          "mt-1 text-caption text-accent font-sans",
          "hover:text-accent-hover",
          "focus-ring-accent outline-none rounded-sm",
          "transition-colors duration-quick ease-settle",
        )}
        data-slot="vault-schedule-empty-cta"
      >
        {cta} →
      </button>
    </div>
  )
}


// ── Detail variant (rich card with full per-driver breakdown) ──────


function VaultScheduleDetail({ data, isLoading, error }: VariantProps) {
  const navigate = useNavigate()

  if (isLoading) {
    return (
      <div
        data-slot="vault-schedule-widget"
        data-variant="detail"
        className="p-4"
      >
        <SkeletonLines count={6} />
      </div>
    )
  }

  if (error) {
    return (
      <div
        data-slot="vault-schedule-widget"
        data-variant="detail"
        className="p-4"
      >
        <p
          className="text-caption text-status-error font-sans"
          data-slot="vault-schedule-error"
        >
          {error}
        </p>
      </div>
    )
  }

  if (!data?.is_vault_enabled) {
    return (
      <VaultScheduleEmptyState
        title="Vault not enabled"
        body="Activate the vault product line to see scheduled deliveries here."
        cta="Manage product lines"
        ctaTarget="/settings/product-lines"
        variant="detail"
      />
    )
  }

  const total = computeTotalCount(data)
  if (total === 0) {
    return (
      <VaultScheduleEmptyState
        title="Nothing scheduled"
        body={`No vault ${
          data.operating_mode === "purchase" ? "incoming" : "deliveries"
        } for ${formatScheduleDateShort(data.date)}.`}
        cta="Open schedule"
        ctaTarget={data.primary_navigation_target || "/dispatch"}
        variant="detail"
      />
    )
  }

  return (
    <div
      data-slot="vault-schedule-widget"
      data-variant="detail"
      data-mode={data.operating_mode ?? "unknown"}
      className="flex flex-col h-full p-4 gap-3 overflow-y-auto"
    >
      <div className="flex items-center gap-2">
        <Truck className="h-5 w-5 text-accent" aria-hidden />
        <h3 className="text-body font-medium text-content-strong font-sans flex-1">
          {formatScheduleDate(data.date)}
        </h3>
        <ModeBadge mode={data.operating_mode} />
      </div>

      {data.production && data.production.total_count > 0 ? (
        <ProductionDetailSection
          production={data.production}
          navigate={navigate}
        />
      ) : null}
      {data.purchase && data.purchase.total_count > 0 ? (
        <PurchaseDetailSection
          purchase={data.purchase}
          navigate={navigate}
        />
      ) : null}

      <button
        type="button"
        onClick={() =>
          navigate(data.primary_navigation_target || "/dispatch")
        }
        className={cn(
          "inline-flex items-center gap-1 mt-auto",
          "text-caption text-accent font-sans",
          "hover:text-accent-hover",
          "focus-ring-accent outline-none rounded-sm",
          "transition-colors duration-quick ease-settle",
        )}
        data-slot="vault-schedule-open-focus"
      >
        Open in scheduling Focus <ExternalLink className="h-3 w-3" />
      </button>
    </div>
  )
}


function ProductionDetailSection({
  production,
  navigate,
}: {
  production: ProductionScheduleData
  navigate: ReturnType<typeof useNavigate>
}) {
  // Group deliveries by primary_assignee_id (or "unassigned").
  const byDriver: Record<string, ProductionDeliveryRow[]> = {}
  for (const d of production.deliveries) {
    const key = d.primary_assignee_id || "__unassigned__"
    byDriver[key] = byDriver[key] ?? []
    byDriver[key].push(d)
  }

  return (
    <section
      data-slot="vault-schedule-production-section"
      className="space-y-2"
    >
      <div className="flex items-baseline justify-between">
        <h4 className="text-caption font-medium text-content-muted font-sans uppercase tracking-wide">
          Production · Driver lanes
        </h4>
        <span className="text-caption text-content-muted font-plex-mono">
          {production.total_count} total
        </span>
      </div>
      <ul className="space-y-2">
        {Object.entries(byDriver).map(([key, ds]) => (
          <li
            key={key}
            data-slot="vault-schedule-driver-lane"
            data-unassigned={key === "__unassigned__" ? "true" : "false"}
            className={cn(
              "rounded-sm px-2 py-1.5",
              key === "__unassigned__"
                ? "bg-status-warning-muted"
                : "bg-surface-muted",
            )}
          >
            <div className="flex items-baseline justify-between">
              <span
                className={cn(
                  "text-caption font-medium font-sans",
                  key === "__unassigned__"
                    ? "text-status-warning"
                    : "text-content-base",
                )}
              >
                {key === "__unassigned__"
                  ? "Unassigned"
                  : `Driver ${key.slice(0, 8)}`}
              </span>
              <span className="text-caption text-content-muted font-plex-mono">
                {ds.length}{" "}
                {ds.length === 1 ? "delivery" : "deliveries"}
              </span>
            </div>
            <ul className="mt-1 space-y-0.5">
              {ds.slice(0, 3).map((d) => (
                <li
                  key={d.delivery_id}
                  className="flex items-baseline gap-2 text-caption font-sans"
                >
                  <span className="text-content-base truncate flex-1">
                    {d.deceased_name || "Unnamed"}
                  </span>
                  {d.attached_ancillary_count > 0 ? (
                    <span className="text-content-muted font-plex-mono text-[10px]">
                      +{d.attached_ancillary_count}
                    </span>
                  ) : null}
                  <span className="text-content-muted font-plex-mono">
                    {d.driver_start_time?.slice(0, 5) ?? "—"}
                  </span>
                </li>
              ))}
              {ds.length > 3 ? (
                <li className="text-caption text-content-muted font-sans italic">
                  + {ds.length - 3} more
                </li>
              ) : null}
            </ul>
          </li>
        ))}
      </ul>
    </section>
  )
}


function PurchaseDetailSection({
  purchase,
  navigate,
}: {
  purchase: PurchaseScheduleData
  navigate: ReturnType<typeof useNavigate>
}) {
  // Group transfers by service_date for week view.
  const byDate: Record<string, PurchaseTransferRow[]> = {}
  for (const t of purchase.transfers) {
    const key = t.service_date || "unscheduled"
    byDate[key] = byDate[key] ?? []
    byDate[key].push(t)
  }

  return (
    <section
      data-slot="vault-schedule-purchase-section"
      className="space-y-2"
    >
      <div className="flex items-baseline justify-between">
        <h4 className="text-caption font-medium text-content-muted font-sans uppercase tracking-wide">
          Incoming · By service date
        </h4>
        <span className="text-caption text-content-muted font-plex-mono">
          {purchase.total_count} total
        </span>
      </div>
      <ul className="space-y-2">
        {Object.entries(byDate).map(([dateKey, ts]) => (
          <li
            key={dateKey}
            data-slot="vault-schedule-date-bucket"
            className="rounded-sm px-2 py-1.5 bg-surface-muted"
          >
            <div className="flex items-baseline justify-between">
              <span className="text-caption font-medium text-content-base font-sans">
                {dateKey === "unscheduled"
                  ? "Unscheduled"
                  : formatScheduleDate(dateKey)}
              </span>
              <span className="text-caption text-content-muted font-plex-mono">
                {ts.length}{" "}
                {ts.length === 1 ? "transfer" : "transfers"}
              </span>
            </div>
            <ul className="mt-1 space-y-0.5">
              {ts.slice(0, 3).map((t) => (
                <li
                  key={t.transfer_id}
                  className="flex items-baseline gap-2 text-caption font-sans"
                >
                  <span className="text-content-base truncate flex-1">
                    {t.deceased_name || t.transfer_number}
                  </span>
                  <span className="text-content-muted font-sans">
                    {t.cemetery_city || ""}
                  </span>
                </li>
              ))}
            </ul>
          </li>
        ))}
      </ul>
    </section>
  )
}


// ── Deep variant — Detail with extended max-height ────────────────


function VaultScheduleDeep(props: VariantProps) {
  // Deep is Detail at max-height 900px; the renderer chrome gives
  // additional vertical room. Same content shape — Detail's
  // grouping is already information-rich; Deep doesn't add a new
  // layout.
  return <VaultScheduleDetail {...props} />
}


// ── Common props ──────────────────────────────────────────────────


interface VariantProps {
  data: VaultScheduleData | null
  isLoading: boolean
  error: string | null
}


// ── Top-level dispatcher ──────────────────────────────────────────


export interface VaultScheduleWidgetProps {
  widgetId?: string
  variant_id?: VariantId
  surface?:
    | "focus_canvas"
    | "focus_stack"
    | "spaces_pin"
    | "pulse_grid"
    | "dashboard_grid"
  config?: Record<string, unknown>
}


export function VaultScheduleWidget(props: VaultScheduleWidgetProps) {
  // `target_date` from config — defaults to tenant-local today
  // (resolved server-side). Future: allow widget instances to pin
  // "next Tuesday" via config.target_date.
  const cfg = (props.config ?? {}) as { target_date?: string }
  const url =
    cfg.target_date && typeof cfg.target_date === "string"
      ? `/widget-data/vault-schedule?target_date=${encodeURIComponent(cfg.target_date)}`
      : "/widget-data/vault-schedule"

  const { data, isLoading, error } = useWidgetData<VaultScheduleData>(url, {
    refreshInterval: 5 * 60 * 1000, // 5 min
  })

  const variant = props.variant_id ?? "brief"

  if (variant === "glance") {
    return <VaultScheduleGlance data={data} isLoading={isLoading} />
  }
  if (variant === "detail") {
    return <VaultScheduleDetail data={data} isLoading={isLoading} error={error} />
  }
  if (variant === "deep") {
    return <VaultScheduleDeep data={data} isLoading={isLoading} error={error} />
  }
  // Default + brief
  return <VaultScheduleBrief data={data} isLoading={isLoading} error={error} />
}


export default VaultScheduleWidget

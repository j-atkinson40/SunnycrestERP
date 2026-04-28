/**
 * AnomaliesWidget — Phase W-3a cross-vertical foundation widget.
 *
 * Surfaces real production anomaly data from `agent_anomalies` (Phase 1
 * accounting agent infrastructure). Cross-vertical visibility (every
 * tenant sees the widget); cross-line.
 *
 * Per [DESIGN_LANGUAGE.md §12.10](../../../../DESIGN_LANGUAGE.md):
 * Brief + Detail variants ONLY — anomalies need at least Brief
 * context (no Glance — count alone doesn't communicate severity or
 * actionability).
 *
 * Per [§12.6a Widget Interactivity Discipline](../../../../DESIGN_LANGUAGE.md):
 * Acknowledge is a **bounded state flip** — single anomaly, single
 * field (`resolved=true`), audit-logged. This is the canonical
 * widget-appropriate interaction per the four-test framework:
 *   1. Bounded scope: single anomaly per click ✓
 *   2. No coordination required: independent of other anomalies ✓
 *   3. Reversible / low-stakes: false alarm acks can be re-investigated ✓
 *   4. Time-bounded: instant ✓
 *
 * Severity vocabulary per `app.schemas.agent.AnomalySeverity`:
 *   - critical → status-error (terracotta)
 *   - warning → status-warning (terracotta-muted)
 *   - info → status-info
 *
 * Three-component shape per established Phase W-3a precedent.
 */

import { useMemo, useState } from "react"
import { useNavigate } from "react-router-dom"
import { CheckCircle2, AlertTriangle, AlertCircle, Info, Check } from "lucide-react"

import { useWidgetData } from "../useWidgetData"
import apiClient from "@/lib/api-client"
import { cn } from "@/lib/utils"
import type { VariantId } from "@/components/widgets/types"


// ── Data shape ──────────────────────────────────────────────────────


type Severity = "critical" | "warning" | "info"


interface Anomaly {
  id: string
  severity: Severity | string
  anomaly_type: string
  description: string
  entity_type: string | null
  entity_id: string | null
  amount: string | null
  source_agent_job_id: string
  source_agent_type: string | null
  created_at: string
  resolved: boolean
  resolved_by: string | null
  resolved_at: string | null
  resolution_note: string | null
}


interface AnomaliesResponse {
  anomalies: Anomaly[]
  total_unresolved: number
  critical_count: number
}


// ── Helpers ─────────────────────────────────────────────────────────


function relativeTime(iso: string): string {
  const then = new Date(iso).getTime()
  const now = Date.now()
  const diff = Math.max(0, now - then)
  const min = Math.floor(diff / 60_000)
  if (min < 1) return "just now"
  if (min < 60) return `${min} min ago`
  const hr = Math.floor(min / 60)
  if (hr < 24) return `${hr}h ago`
  const day = Math.floor(hr / 24)
  if (day < 7) return `${day}d ago`
  return new Date(iso).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  })
}


/** Severity → token-mapped className (left-edge indicator + icon color). */
function severityTokens(sev: string): {
  borderClass: string
  iconClass: string
  Icon: typeof AlertCircle
  label: string
} {
  switch (sev) {
    case "critical":
      return {
        borderClass: "border-l-status-error",
        iconClass: "text-status-error",
        Icon: AlertCircle,
        label: "Critical",
      }
    case "warning":
      return {
        borderClass: "border-l-status-warning",
        iconClass: "text-status-warning",
        Icon: AlertTriangle,
        label: "Warning",
      }
    case "info":
      return {
        borderClass: "border-l-status-info",
        iconClass: "text-status-info",
        Icon: Info,
        label: "Info",
      }
    default:
      return {
        borderClass: "border-l-content-muted",
        iconClass: "text-content-muted",
        Icon: Info,
        label: sev,
      }
  }
}


/** Resolve navigation target for an anomaly's source entity. Falls
 *  back to the agent jobs admin surface when no entity is linked. */
function resolveAnomalyTarget(item: Anomaly): string {
  if (item.entity_type && item.entity_id) {
    // Future enhancement: per-entity-type routing (invoice → /invoices/{id},
    // order → /orders/{id}, etc.). For Phase W-3a Phase 1, route
    // generically via the agent-job admin surface where the anomaly
    // was raised.
  }
  return `/admin/agents/jobs/${item.source_agent_job_id}`
}


// ── Anomaly row (shared) ───────────────────────────────────────────


interface AnomalyRowProps {
  anomaly: Anomaly
  onInvestigate: () => void
  onAcknowledge: () => void
  isAcknowledging: boolean
}


function AnomalyRow({
  anomaly,
  onInvestigate,
  onAcknowledge,
  isAcknowledging,
}: AnomalyRowProps) {
  const tok = severityTokens(anomaly.severity)
  const when = relativeTime(anomaly.created_at)
  return (
    <li
      data-slot="anomalies-widget-row"
      data-anomaly-id={anomaly.id}
      data-severity={anomaly.severity}
      className={cn(
        "flex items-stretch gap-2 rounded-sm pr-2",
        "border-l-2 bg-surface-base/50",
        "hover:bg-accent-subtle/30",
        "transition-colors duration-quick ease-settle",
        tok.borderClass,
      )}
    >
      <button
        onClick={onInvestigate}
        className={cn(
          "flex min-w-0 flex-1 items-baseline gap-2 px-2 py-1.5",
          "text-left text-body-sm text-content-base",
          "focus-ring-accent outline-none rounded-sm",
        )}
        data-slot="anomalies-widget-row-investigate"
      >
        <tok.Icon
          className={cn("h-4 w-4 shrink-0 self-center", tok.iconClass)}
          aria-hidden
        />
        <span className="min-w-0 flex-1 truncate">
          <span className="text-content-strong">{anomaly.description}</span>
          {anomaly.source_agent_type && (
            <>
              {" "}
              <span className="text-content-muted">·</span>{" "}
              <span className="text-caption text-content-muted">
                {anomaly.source_agent_type}
              </span>
            </>
          )}
        </span>
        <span
          className={cn(
            "shrink-0 text-caption text-content-subtle font-mono",
            "tabular-nums",
          )}
        >
          {when}
        </span>
      </button>
      <button
        onClick={onAcknowledge}
        disabled={isAcknowledging || anomaly.resolved}
        className={cn(
          "shrink-0 self-center inline-flex items-center justify-center",
          "h-6 w-6 rounded-full",
          "text-content-muted hover:text-status-success",
          "hover:bg-status-success/10",
          "transition-colors duration-quick ease-settle",
          "focus-ring-accent outline-none",
          "disabled:opacity-50 disabled:cursor-not-allowed",
        )}
        title="Acknowledge"
        aria-label={`Acknowledge anomaly: ${anomaly.description}`}
        data-slot="anomalies-widget-row-acknowledge"
      >
        <Check className="h-3.5 w-3.5" aria-hidden />
      </button>
    </li>
  )
}


// ── Brief variant ──────────────────────────────────────────────────


interface BriefProps {
  data: AnomaliesResponse | null
  isLoading: boolean
  error: string | null
  acknowledgingIds: Set<string>
  onInvestigate: (anomaly: Anomaly) => void
  onAcknowledge: (anomaly: Anomaly) => void
  onViewAll: () => void
  // Surface-specific compaction per DESIGN_LANGUAGE §13.4.1 amendment
  // (Phase W-4a Step 2.D, April 2026): Pulse honors grid cell size
  // constraints — Brief variant in pulse_grid compacts to header +
  // footer when content density exceeds cell height. Dashboard
  // surfaces render full Brief content with rows.
  surface?: "focus_canvas" | "focus_stack" | "spaces_pin" | "pulse_grid"
}


function AnomaliesBriefCard({
  data,
  isLoading,
  error,
  acknowledgingIds,
  onInvestigate,
  onAcknowledge,
  onViewAll,
  surface,
}: BriefProps) {
  if (error) {
    return (
      <div
        data-slot="anomalies-widget-error"
        className="p-4 text-caption text-status-error"
      >
        Couldn't load anomalies.
      </div>
    )
  }

  const items = (data?.anomalies ?? []).slice(0, 4)
  const totalUnresolved = data?.total_unresolved ?? 0
  const criticalCount = data?.critical_count ?? 0

  // Pulse compaction (DESIGN_LANGUAGE §13.4.1 amendment): when this
  // widget renders inside the Pulse tetris grid, the Brief variant's
  // 4-row body (~340px intrinsic) doesn't fit 2x1=80px grid cells.
  // Compact to header summary + footer link only — full row rendering
  // available in Detail variant or on dashboard surfaces.
  const isPulse = surface === "pulse_grid"

  return (
    <div
      data-slot="anomalies-widget"
      data-variant="brief"
      data-surface={surface ?? "default"}
      className={cn(
        "flex flex-col h-full",
        isLoading && "opacity-80",
        // In Pulse, render as a single dense row (header + count
        // badge + inline View-all CTA) rather than vertical stack.
        isPulse && "anomalies-widget-pulse-compact",
      )}
    >
      <div
        data-slot="anomalies-widget-header"
        className={cn(
          "flex items-baseline justify-between gap-2",
          "border-b border-border-subtle/40 px-4 py-3",
        )}
      >
        <div className="min-w-0 flex-1">
          <p
            className={cn(
              "text-micro uppercase tracking-wider",
              "text-content-muted font-mono",
            )}
          >
            Anomalies
          </p>
          <h3
            className={cn(
              "mt-0.5 text-body-sm font-medium leading-tight",
              "text-content-strong font-sans",
            )}
          >
            {totalUnresolved === 0
              ? "All clear"
              : criticalCount > 0
              ? `${criticalCount} critical · ${totalUnresolved} total`
              : `${totalUnresolved} unresolved`}
          </h3>
        </div>
        {totalUnresolved > 0 && (
          <span
            data-slot="anomalies-widget-count"
            className={cn(
              "inline-flex items-center justify-center",
              "min-w-[20px] h-5 px-1.5 rounded-full",
              "text-caption font-medium font-mono tabular-nums shrink-0",
              criticalCount > 0
                ? "bg-status-error text-content-on-accent"
                : "bg-accent-muted text-content-muted",
            )}
          >
            {totalUnresolved}
          </span>
        )}
      </div>

      {/* Pulse compact: skip the 4-row body. Header carries the
          count + critical breakdown; the footer link routes to full
          investigation. Per §13.4.1 amendment. */}
      {!isPulse && (
        <div data-slot="anomalies-widget-body" className="flex-1">
          {!isLoading && items.length === 0 && (
            <div
              data-slot="anomalies-widget-empty"
              className="flex flex-col items-center justify-center gap-2 px-4 py-6 text-center"
            >
              <CheckCircle2
                className="h-6 w-6 text-status-success"
                aria-hidden
              />
              <p className="text-caption text-content-muted font-sans leading-tight">
                All clear
              </p>
              <p className="text-micro text-content-subtle font-sans leading-tight">
                No unresolved anomalies right now.
              </p>
            </div>
          )}
          {items.length > 0 && (
            <ul
              data-slot="anomalies-widget-rows"
              className="space-y-1 px-2 py-2"
            >
              {items.map((anomaly) => (
                <AnomalyRow
                  key={anomaly.id}
                  anomaly={anomaly}
                  onInvestigate={() => onInvestigate(anomaly)}
                  onAcknowledge={() => onAcknowledge(anomaly)}
                  isAcknowledging={acknowledgingIds.has(anomaly.id)}
                />
              ))}
            </ul>
          )}
        </div>
      )}

      {/* Footer: in Pulse (compact), ALWAYS render the navigation
          affordance when totalUnresolved > 0 — the footer IS the
          interaction surface in compact mode (no rows above it).
          In dashboard mode, footer surfaces only when the body shows
          a partial slice. */}
      {((isPulse && totalUnresolved > 0) ||
        (!isPulse && totalUnresolved > items.length)) && (
        <div
          data-slot="anomalies-widget-footer"
          className={cn(
            "px-4 py-2",
            // Brass-thread separator only in non-Pulse (with rows
            // above). In Pulse compact, the header's bottom border
            // already separates from the footer.
            !isPulse && "border-t border-border-subtle/40",
          )}
        >
          <button
            onClick={onViewAll}
            className={cn(
              "text-caption text-accent font-sans",
              "hover:text-accent-hover",
              "transition-colors duration-quick ease-settle",
              "focus-ring-accent outline-none rounded-sm",
            )}
            data-slot="anomalies-widget-view-all"
          >
            {isPulse
              ? `Investigate ${totalUnresolved} →`
              : `View all ${totalUnresolved} →`}
          </button>
        </div>
      )}
    </div>
  )
}


// ── Detail variant ──────────────────────────────────────────────────


interface DetailProps {
  data: AnomaliesResponse | null
  isLoading: boolean
  error: string | null
  acknowledgingIds: Set<string>
  onInvestigate: (anomaly: Anomaly) => void
  onAcknowledge: (anomaly: Anomaly) => void
}


type SeverityFilter = "all" | "critical" | "warning" | "info"


function AnomaliesDetailCard({
  data,
  isLoading,
  error,
  acknowledgingIds,
  onInvestigate,
  onAcknowledge,
}: DetailProps) {
  const [filter, setFilter] = useState<SeverityFilter>("all")

  const anomalies = data?.anomalies ?? []
  const filtered = useMemo(
    () =>
      filter === "all"
        ? anomalies
        : anomalies.filter((a) => a.severity === filter),
    [anomalies, filter],
  )

  if (error) {
    return (
      <div
        data-slot="anomalies-widget-error"
        className="p-4 text-caption text-status-error"
      >
        Couldn't load anomalies.
      </div>
    )
  }

  return (
    <div
      data-slot="anomalies-widget"
      data-variant="detail"
      className={cn("flex flex-col h-full", isLoading && "opacity-80")}
    >
      <div
        data-slot="anomalies-widget-header"
        className="border-b border-border-subtle/40 px-4 py-3"
      >
        <p
          className={cn(
            "text-micro uppercase tracking-wider",
            "text-content-muted font-mono",
          )}
        >
          Anomalies
        </p>
        <h3
          className={cn(
            "mt-0.5 text-body-sm font-medium leading-tight",
            "text-content-strong font-sans",
          )}
        >
          {filter === "all"
            ? `${anomalies.length} unresolved`
            : `${filtered.length} ${filter}`}
        </h3>
        <div
          data-slot="anomalies-widget-filters"
          className="mt-2 flex flex-wrap gap-1.5"
          role="tablist"
          aria-label="Filter anomalies by severity"
        >
          {(
            [
              ["all", "All"],
              ["critical", "Critical"],
              ["warning", "Warning"],
              ["info", "Info"],
            ] as const
          ).map(([key, label]) => {
            const active = filter === key
            return (
              <button
                key={key}
                role="tab"
                aria-selected={active}
                onClick={() => setFilter(key)}
                data-slot="anomalies-widget-filter-chip"
                data-filter-key={key}
                data-active={active ? "true" : "false"}
                className={cn(
                  "px-2 py-0.5 rounded-full text-caption font-sans",
                  "transition-colors duration-quick ease-settle",
                  "focus-ring-accent outline-none",
                  active
                    ? "bg-accent text-content-on-accent"
                    : "bg-accent-muted/30 text-content-muted hover:bg-accent-muted/50",
                )}
              >
                {label}
              </button>
            )
          })}
        </div>
      </div>

      <div
        data-slot="anomalies-widget-body"
        className="flex-1 overflow-y-auto"
      >
        {!isLoading && filtered.length === 0 && (
          <div
            data-slot="anomalies-widget-empty"
            className="flex flex-col items-center justify-center gap-2 px-4 py-8 text-center"
          >
            <CheckCircle2
              className="h-6 w-6 text-status-success"
              aria-hidden
            />
            <p className="text-caption text-content-muted font-sans leading-tight">
              {anomalies.length === 0
                ? "All clear"
                : "No anomalies in this filter"}
            </p>
            {anomalies.length === 0 && (
              <p className="text-micro text-content-subtle font-sans leading-tight">
                No unresolved anomalies right now.
              </p>
            )}
          </div>
        )}
        {filtered.length > 0 && (
          <ul
            data-slot="anomalies-widget-rows"
            className="space-y-1 px-2 py-2"
          >
            {filtered.map((anomaly) => (
              <AnomalyRow
                key={anomaly.id}
                anomaly={anomaly}
                onInvestigate={() => onInvestigate(anomaly)}
                onAcknowledge={() => onAcknowledge(anomaly)}
                isAcknowledging={acknowledgingIds.has(anomaly.id)}
              />
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}


// ── Top-level dispatcher ────────────────────────────────────────────


export interface AnomaliesWidgetProps {
  widgetId?: string
  variant_id?: VariantId
  surface?: "focus_canvas" | "focus_stack" | "spaces_pin" | "pulse_grid"
}


/**
 * Top-level dispatcher. Anomalies has NO Glance variant per §12.10 —
 * `surface=spaces_pin` falls through to Brief (a deliberately compact
 * sidebar render).
 */
export function AnomaliesWidget(props: AnomaliesWidgetProps) {
  if (props.variant_id === "detail") {
    return <AnomaliesDetailVariant />
  }
  return <AnomaliesBriefVariant surface={props.surface} />
}


function useAnomaliesController() {
  const navigate = useNavigate()
  const { data, isLoading, error, refresh } =
    useWidgetData<AnomaliesResponse>("/widget-data/anomalies?limit=20", {
      refreshInterval: 2 * 60 * 1000, // 2 min — anomalies are higher-urgency
    })
  const [acknowledgingIds, setAcknowledgingIds] = useState<Set<string>>(
    () => new Set(),
  )

  async function handleAcknowledge(anomaly: Anomaly) {
    setAcknowledgingIds((prev) => new Set(prev).add(anomaly.id))
    try {
      await apiClient.post(
        `/widget-data/anomalies/${anomaly.id}/acknowledge`,
        {},
      )
      // Refresh the widget data so the acknowledged anomaly drops
      // out of the unresolved list.
      refresh()
    } catch (err) {
      // Non-blocking — keep the row visible. Future enhancement:
      // surface a toast on failure. For W-3a Phase 1, the row stays
      // rendered and the user can retry.
      console.error("Failed to acknowledge anomaly:", err)
    } finally {
      setAcknowledgingIds((prev) => {
        const next = new Set(prev)
        next.delete(anomaly.id)
        return next
      })
    }
  }

  function handleInvestigate(anomaly: Anomaly) {
    navigate(resolveAnomalyTarget(anomaly))
  }

  function handleViewAll() {
    navigate("/admin/agents")
  }

  return {
    data,
    isLoading,
    error,
    acknowledgingIds,
    handleAcknowledge,
    handleInvestigate,
    handleViewAll,
  }
}


function AnomaliesBriefVariant({
  surface,
}: {
  surface?: AnomaliesWidgetProps["surface"]
}) {
  const ctl = useAnomaliesController()
  return (
    <AnomaliesBriefCard
      data={ctl.data}
      isLoading={ctl.isLoading}
      error={ctl.error}
      acknowledgingIds={ctl.acknowledgingIds}
      onInvestigate={ctl.handleInvestigate}
      onAcknowledge={ctl.handleAcknowledge}
      onViewAll={ctl.handleViewAll}
      surface={surface}
    />
  )
}


function AnomaliesDetailVariant() {
  const ctl = useAnomaliesController()
  return (
    <AnomaliesDetailCard
      data={ctl.data}
      isLoading={ctl.isLoading}
      error={ctl.error}
      acknowledgingIds={ctl.acknowledgingIds}
      onInvestigate={ctl.handleInvestigate}
      onAcknowledge={ctl.handleAcknowledge}
    />
  )
}


export default AnomaliesWidget

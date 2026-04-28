/**
 * LineStatusWidget — Phase W-3d cross-line health aggregator.
 *
 * Per [DESIGN_LANGUAGE.md §12.10 reference 5](../../../../DESIGN_LANGUAGE.md):
 * Brief + Detail variants — NO Glance because line status is
 * operational-health information that doesn't compress to count-only.
 *
 * Per active TenantProductLine, renders one health row:
 *   • status indicator (on_track / behind / blocked / idle / unknown)
 *   • headline metric ("8 pours today" / "no incoming today" / hybrid composed)
 *   • mode badge (Production / Purchase / Hybrid)
 *   • click-through to relevant Focus or detail page
 *
 * Multi-line aggregation: backend's multi-line builder pattern surfaces
 * each active line as a row. Sunnycrest (vault-only) sees one row;
 * tenants with vault + redi_rock + urn_sales see three rows. The widget
 * renders whatever the backend returns — frontend is dumb-render.
 *
 * Per [§12.6a Widget Interactivity Discipline](../../../../DESIGN_LANGUAGE.md):
 * view-only with click-through to line-specific Focus or schedule
 * widget. Acknowledge / dismiss / line-level decisions belong in
 * Focus, not the widget.
 *
 * Three-component shape per established Phase W-3a/W-3b precedent.
 */

import { useNavigate } from "react-router-dom"
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  CircleSlash,
  HelpCircle,
} from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { SkeletonLines } from "@/components/ui/skeleton"
import { useWidgetData } from "../useWidgetData"
import { cn } from "@/lib/utils"
import type { VariantId } from "@/components/widgets/types"


// ── Data shape (mirrors backend `get_line_status` response) ────────


type LineStatus = "on_track" | "behind" | "blocked" | "idle" | "unknown"

type OperatingMode = "production" | "purchase" | "hybrid"


interface LineHealthRow {
  line_key: string
  display_name: string
  operating_mode: OperatingMode | string
  status: LineStatus
  headline: string
  metrics: Record<string, unknown>
  navigation_target: string | null
}


interface LineStatusData {
  date: string
  lines: LineHealthRow[]
  total_active_lines: number
  any_attention_needed: boolean
}


// ── Status indicator helpers ───────────────────────────────────────


function StatusIcon({
  status,
  className,
}: {
  status: LineStatus
  className?: string
}) {
  if (status === "on_track") {
    return (
      <CheckCircle2
        className={cn("text-status-success", className)}
        aria-label="On track"
      />
    )
  }
  if (status === "behind") {
    return (
      <AlertTriangle
        className={cn("text-status-warning", className)}
        aria-label="Behind"
      />
    )
  }
  if (status === "blocked") {
    return (
      <AlertTriangle
        className={cn("text-status-error", className)}
        aria-label="Blocked"
      />
    )
  }
  if (status === "idle") {
    return (
      <CircleSlash
        className={cn("text-content-subtle", className)}
        aria-label="Idle"
      />
    )
  }
  return (
    <HelpCircle
      className={cn("text-content-subtle", className)}
      aria-label="Status unknown"
    />
  )
}


function statusBgClass(status: LineStatus): string {
  if (status === "behind") return "bg-status-warning-muted"
  if (status === "blocked") return "bg-status-error-muted"
  if (status === "on_track") return "bg-status-success-muted"
  return "bg-surface-muted"
}


function ModeLabel({ mode }: { mode: OperatingMode | string }) {
  const label =
    mode === "production"
      ? "Production"
      : mode === "purchase"
      ? "Purchase"
      : mode === "hybrid"
      ? "Hybrid"
      : mode
  return (
    <Badge
      variant="outline"
      className="text-caption font-sans"
      data-slot="line-status-mode-badge"
    >
      {label}
    </Badge>
  )
}


// ── Brief variant (Pattern 2 grid card) ────────────────────────────


function LineStatusBrief({
  data,
  isLoading,
  error,
  surface,
}: VariantProps) {
  const navigate = useNavigate()

  if (isLoading) {
    return (
      <div
        data-slot="line-status-widget"
        data-variant="brief"
        className="p-4"
      >
        <SkeletonLines count={3} />
      </div>
    )
  }

  if (error) {
    return (
      <div
        data-slot="line-status-widget"
        data-variant="brief"
        className="p-4"
      >
        <p
          className="text-caption text-status-error font-sans"
          data-slot="line-status-error"
        >
          {error}
        </p>
      </div>
    )
  }

  if (!data || data.total_active_lines === 0) {
    return (
      <div
        data-slot="line-status-widget"
        data-variant="brief"
        className="flex flex-col items-center justify-center gap-2 px-4 py-8 h-full text-center"
      >
        <Activity className="h-8 w-8 text-content-subtle" aria-hidden />
        <p
          className="text-body-sm font-medium text-content-strong font-sans"
          data-slot="line-status-empty"
        >
          No product lines active
        </p>
        <p className="text-caption text-content-muted font-sans max-w-[280px]">
          Activate a product line in settings to see operational
          health here.
        </p>
      </div>
    )
  }

  // Phase W-4a Step 6 Commit 2 — opt INTO §13.4.1 density tiers in
  // the Pulse surface. Three nested density variants + container-
  // query CSS in `pulse-density.css` dispatches which one displays.
  const isPulse = surface === "pulse_grid"
  const attentionLines = data.lines.filter(
    (ln) => ln.status === "behind" || ln.status === "blocked",
  ).length
  const idleLines = data.lines.filter((ln) => ln.status === "idle").length
  const onTrackLines = data.lines.filter(
    (ln) => ln.status === "on_track",
  ).length

  if (isPulse) {
    return (
      <div
        data-slot="line-status-widget"
        data-variant="brief"
        data-surface="pulse_grid"
        data-attention={data.any_attention_needed ? "true" : "false"}
        className="h-full"
      >
        {/* Default tier (≥ 121 px) — full content with rows */}
        <div
          data-slot="line-status-widget-pulse-default"
          className="line-status-widget-pulse-default flex-col h-full p-4 gap-2"
        >
          <LineStatusBriefHeader totalActiveLines={data.total_active_lines} />
          <ul className="space-y-1.5 flex-1 min-h-0 overflow-y-auto">
            {data.lines.map((ln) => (
              <li
                key={ln.line_key}
                data-slot="line-status-row"
                data-line-key={ln.line_key}
                data-status={ln.status}
                className={cn(
                  "flex items-center gap-2 px-2 py-1.5 rounded-sm",
                  statusBgClass(ln.status),
                )}
              >
                <StatusIcon
                  status={ln.status}
                  className="h-4 w-4 flex-shrink-0"
                />
                <div className="flex-1 min-w-0">
                  <div className="text-body-sm font-medium text-content-strong font-sans truncate">
                    {ln.display_name}
                  </div>
                  <div className="text-caption text-content-muted font-sans truncate">
                    {ln.headline}
                  </div>
                </div>
                {ln.navigation_target ? (
                  <button
                    type="button"
                    onClick={() =>
                      navigate(ln.navigation_target as string)
                    }
                    className={cn(
                      "text-caption text-accent font-sans flex-shrink-0",
                      "hover:text-accent-hover",
                      "focus-ring-accent outline-none rounded-sm",
                      "transition-colors duration-quick ease-settle",
                    )}
                    aria-label={`View ${ln.display_name} schedule`}
                    data-slot="line-status-row-cta"
                  >
                    →
                  </button>
                ) : null}
              </li>
            ))}
          </ul>
        </div>

        {/* Compact tier (101–120 px) — header + condensed status pills */}
        <div
          data-slot="line-status-widget-pulse-compact"
          className="line-status-widget-pulse-compact flex-col h-full p-4 gap-2"
        >
          <LineStatusBriefHeader totalActiveLines={data.total_active_lines} />
          <ul className="space-y-1 flex-1 min-h-0 overflow-hidden">
            {data.lines.slice(0, 3).map((ln) => (
              <li
                key={ln.line_key}
                data-slot="line-status-row"
                data-line-key={ln.line_key}
                data-status={ln.status}
                className={cn(
                  "flex items-center gap-2 px-2 py-1 rounded-sm",
                  statusBgClass(ln.status),
                )}
              >
                <StatusIcon
                  status={ln.status}
                  className="h-3.5 w-3.5 flex-shrink-0"
                />
                <span className="text-caption text-content-strong font-sans truncate flex-1">
                  {ln.display_name}
                </span>
                <span className="text-micro text-content-muted font-mono shrink-0">
                  {ln.status}
                </span>
              </li>
            ))}
          </ul>
        </div>

        {/* Ultra-compact tier (80–100 px) — single dense readout */}
        <button
          type="button"
          onClick={() => {
            const target = data.lines.find((ln) => ln.navigation_target)
            if (target?.navigation_target) {
              navigate(target.navigation_target as string)
            }
          }}
          data-slot="line-status-widget-pulse-ultra-compact"
          className={cn(
            "line-status-widget-pulse-ultra-compact items-center h-full w-full px-3 gap-2",
            "text-left text-body-sm",
            "hover:bg-accent-subtle/30",
            "focus-ring-accent outline-none rounded-sm",
            "transition-colors duration-quick ease-settle",
          )}
        >
          <Activity
            className={cn(
              "h-4 w-4 shrink-0",
              data.any_attention_needed
                ? "text-status-warning"
                : "text-accent",
            )}
            aria-hidden
          />
          <span className="min-w-0 flex-1 truncate text-content-strong font-medium">
            {data.total_active_lines}{" "}
            {data.total_active_lines === 1 ? "line" : "lines"}
            {attentionLines > 0
              ? ` · ${attentionLines} attention`
              : onTrackLines > 0
              ? ` · ${onTrackLines} on track`
              : idleLines > 0
              ? ` · ${idleLines} idle`
              : ""}
          </span>
          <span aria-hidden className="shrink-0 text-accent text-caption">
            →
          </span>
        </button>
      </div>
    )
  }

  // Non-Pulse surfaces — full Brief without density dispatch.
  return (
    <div
      data-slot="line-status-widget"
      data-variant="brief"
      data-attention={data.any_attention_needed ? "true" : "false"}
      className="flex flex-col h-full p-4 gap-2"
    >
      <LineStatusBriefHeader totalActiveLines={data.total_active_lines} />
      <ul className="space-y-1.5 flex-1 min-h-0 overflow-y-auto">
        {data.lines.map((ln) => (
          <li
            key={ln.line_key}
            data-slot="line-status-row"
            data-line-key={ln.line_key}
            data-status={ln.status}
            className={cn(
              "flex items-center gap-2 px-2 py-1.5 rounded-sm",
              statusBgClass(ln.status),
            )}
          >
            <StatusIcon status={ln.status} className="h-4 w-4 flex-shrink-0" />
            <div className="flex-1 min-w-0">
              <div className="text-body-sm font-medium text-content-strong font-sans truncate">
                {ln.display_name}
              </div>
              <div className="text-caption text-content-muted font-sans truncate">
                {ln.headline}
              </div>
            </div>
            {ln.navigation_target ? (
              <button
                type="button"
                onClick={() =>
                  navigate(ln.navigation_target as string)
                }
                className={cn(
                  "text-caption text-accent font-sans flex-shrink-0",
                  "hover:text-accent-hover",
                  "focus-ring-accent outline-none rounded-sm",
                  "transition-colors duration-quick ease-settle",
                )}
                aria-label={`View ${ln.display_name} schedule`}
                data-slot="line-status-row-cta"
              >
                →
              </button>
            ) : null}
          </li>
        ))}
      </ul>
    </div>
  )
}


function LineStatusBriefHeader({
  totalActiveLines,
}: {
  totalActiveLines: number
}) {
  return (
    <div className="flex items-center gap-2">
      <Activity className="h-4 w-4 text-accent" aria-hidden />
      <h3 className="text-body-sm font-medium text-content-strong font-sans flex-1">
        Line status
      </h3>
      <span className="text-caption text-content-muted font-plex-mono">
        {totalActiveLines}{" "}
        {totalActiveLines === 1 ? "line" : "lines"}
      </span>
    </div>
  )
}


// ── Detail variant — expanded metrics per row ──────────────────────


function LineStatusDetail({
  data,
  isLoading,
  error,
}: VariantProps) {
  const navigate = useNavigate()

  if (isLoading) {
    return (
      <div
        data-slot="line-status-widget"
        data-variant="detail"
        className="p-4"
      >
        <SkeletonLines count={5} />
      </div>
    )
  }

  if (error) {
    return (
      <div
        data-slot="line-status-widget"
        data-variant="detail"
        className="p-4"
      >
        <p
          className="text-caption text-status-error font-sans"
          data-slot="line-status-error"
        >
          {error}
        </p>
      </div>
    )
  }

  if (!data || data.total_active_lines === 0) {
    return (
      <div
        data-slot="line-status-widget"
        data-variant="detail"
        className="flex flex-col items-center justify-center gap-2 px-4 py-8 h-full text-center"
      >
        <Activity className="h-8 w-8 text-content-subtle" aria-hidden />
        <p
          className="text-body-sm font-medium text-content-strong font-sans"
          data-slot="line-status-empty"
        >
          No product lines active
        </p>
      </div>
    )
  }

  return (
    <div
      data-slot="line-status-widget"
      data-variant="detail"
      data-attention={data.any_attention_needed ? "true" : "false"}
      className="flex flex-col h-full p-4 gap-3 overflow-y-auto"
    >
      <div className="flex items-center gap-2">
        <Activity className="h-5 w-5 text-accent" aria-hidden />
        <h3 className="text-body font-medium text-content-strong font-sans flex-1">
          Line status
        </h3>
      </div>

      <ul className="space-y-2">
        {data.lines.map((ln) => (
          <li
            key={ln.line_key}
            data-slot="line-status-row"
            data-line-key={ln.line_key}
            data-status={ln.status}
            className={cn(
              "rounded-sm px-3 py-2 border border-border-subtle",
              statusBgClass(ln.status),
            )}
          >
            <div className="flex items-center gap-2 mb-1">
              <StatusIcon
                status={ln.status}
                className="h-4 w-4 flex-shrink-0"
              />
              <span className="text-body-sm font-medium text-content-strong font-sans flex-1">
                {ln.display_name}
              </span>
              <ModeLabel mode={ln.operating_mode} />
            </div>
            <div className="text-caption text-content-muted font-sans">
              {ln.headline}
            </div>
            <DetailMetrics metrics={ln.metrics} />
            {ln.navigation_target ? (
              <button
                type="button"
                onClick={() =>
                  navigate(ln.navigation_target as string)
                }
                className={cn(
                  "mt-1.5 inline-flex items-center gap-1",
                  "text-caption text-accent font-sans",
                  "hover:text-accent-hover",
                  "focus-ring-accent outline-none rounded-sm",
                  "transition-colors duration-quick ease-settle",
                )}
                data-slot="line-status-row-cta"
              >
                Open schedule →
              </button>
            ) : null}
          </li>
        ))}
      </ul>
    </div>
  )
}


function DetailMetrics({
  metrics,
}: {
  metrics: Record<string, unknown>
}) {
  const entries = Object.entries(metrics).filter(
    ([, v]) => typeof v === "number" && (v as number) > 0,
  )
  if (entries.length === 0) return null
  return (
    <ul
      className="mt-1 grid grid-cols-2 gap-x-3 gap-y-0.5 text-caption font-sans"
      data-slot="line-status-metrics"
    >
      {entries.map(([k, v]) => (
        <li
          key={k}
          className="flex items-baseline justify-between"
        >
          <span className="text-content-muted truncate">
            {humanizeMetricKey(k)}
          </span>
          <span className="text-content-base font-plex-mono">
            {String(v)}
          </span>
        </li>
      ))}
    </ul>
  )
}


function humanizeMetricKey(key: string): string {
  // production_today → "Today (production)"
  // production_unassigned → "Unassigned"
  // purchase_pending → "Pending (incoming)"
  const map: Record<string, string> = {
    production_today: "Today (pour)",
    production_assigned: "Assigned",
    production_unassigned: "Unassigned",
    purchase_today: "Incoming today",
    purchase_pending: "Pending",
  }
  return map[key] || key.replace(/_/g, " ")
}


// ── Common props ──────────────────────────────────────────────────


interface VariantProps {
  data: LineStatusData | null
  isLoading: boolean
  error: string | null
  surface?: LineStatusWidgetProps["surface"]
}


// ── Top-level dispatcher ──────────────────────────────────────────


export interface LineStatusWidgetProps {
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


export function LineStatusWidget(props: LineStatusWidgetProps) {
  const { data, isLoading, error } = useWidgetData<LineStatusData>(
    "/widget-data/line-status",
    { refreshInterval: 5 * 60 * 1000 },
  )

  const variant = props.variant_id ?? "brief"

  if (variant === "detail") {
    return (
      <LineStatusDetail data={data} isLoading={isLoading} error={error} />
    )
  }
  // Default + glance/deep fallback: Brief. line_status doesn't
  // declare Glance or Deep variants per §12.10; defensive fallback
  // ensures any unexpected variant_id renders meaningful content.
  return (
    <LineStatusBrief
      data={data}
      isLoading={isLoading}
      error={error}
      surface={props.surface}
    />
  )
}


export default LineStatusWidget

/**
 * CalendarConsentPendingWidget — Phase W-4b Layer 1 Calendar Step 5.1.
 *
 * Surfaces cross-tenant calendar consent upgrade requests pending
 * this tenant's response (``state='pending_inbound'`` PTR consent
 * rows). Per Pulse Communications Layer canon (BRIDGEABLE_MASTER
 * §3.26.16.10) — placed alongside `calendar_glance` + `email_glance`.
 * Pattern parallels `CalendarGlanceWidget` Step 5 verbatim.
 *
 * Per [DESIGN_LANGUAGE.md §14.4-14.5](../../../../DESIGN_LANGUAGE.md):
 * three density tiers (canonical Pattern C convention):
 *   - Default (cell_height ≥ 121px) — UserCheck icon + "Requests"
 *     eyebrow + mono count + top requester body (1 line: tenant
 *     label) + "Review consent requests →" footer
 *   - Compact (101-120px) — header row + requester collapsed to
 *     single line; footer dropped
 *   - Ultra-compact (80-100px) — single-row icon + label + count
 *
 * Per §14.2: Lucide `UserCheck` icon canonical. 18×18 stroke-1.5 in
 * `text-content-muted` at rest, `text-accent` when count > 0.
 *
 * Per §14.3 typography: counts in `font-plex-mono`,
 * `text-status-warning` when actionable + `text-content-muted` when
 * zero. Default tier: `text-h3` size; Compact / Ultra-compact:
 * `text-body-sm`.
 *
 * Per [§12.6a Widget Interactivity Discipline](../../../../DESIGN_LANGUAGE.md):
 * **view-only** with click-through navigation. Single-request
 * surface → `/settings/calendar/freebusy-consent?relationship_id={id}`.
 * Multi-request surface → `/settings/calendar/freebusy-consent`.
 * Empty + has tenant context → `/settings/calendar/freebusy-consent`
 * (still navigable; the page renders its own empty state).
 *
 * Accept / decline / revoke happens on the settings page, NOT inline
 * on the widget. Widget is purely informational.
 *
 * Cross-vertical foundation widget — every tenant sees it; renders
 * empty state ("No pending consent requests") when zero PTR rows in
 * `pending_inbound` state.
 *
 * Data source: `GET /api/v1/widget-data/calendar-consent-pending`
 * with auto-refresh every 5 minutes via `useWidgetData`.
 */

import { useNavigate } from "react-router-dom"
import { UserCheck } from "lucide-react"

import { useWidgetData } from "../useWidgetData"
import { cn } from "@/lib/utils"
import type { VariantId } from "@/components/widgets/types"


// ── Data shape (mirrors backend `get_calendar_consent_pending`) ─────


export interface CalendarConsentPendingData {
  has_pending: boolean
  pending_consent_count: number
  top_requester_name: string | null
  top_requester_tenant_label: string | null
  target_relationship_id: string | null
}


// ── Display helpers ─────────────────────────────────────────────────


/** Top-requester display label — falls back to a generic label. */
function topRequesterLabel(data: CalendarConsentPendingData): string | null {
  if (data.top_requester_name) return data.top_requester_name
  if (data.top_requester_tenant_label) return data.top_requester_tenant_label
  return null
}


/** Build the click-through target URL based on widget state. */
function buildClickTarget(
  data: CalendarConsentPendingData | null,
): string {
  const base = "/settings/calendar/freebusy-consent"
  if (!data) return base
  if (data.target_relationship_id) {
    return `${base}?relationship_id=${data.target_relationship_id}`
  }
  return base
}


/** Empty-state copy per §14.3 — primitive empty-state when count=0. */
function emptyStateLabel(): string {
  return "No pending consent requests"
}


// ── Default-tier presentation (≥121px) ──────────────────────────────


function CalendarConsentPendingDefault({
  data,
  isLoading,
  onClick,
}: {
  data: CalendarConsentPendingData | null
  isLoading: boolean
  onClick: () => void
}) {
  const count = data?.pending_consent_count ?? 0
  const isActionable = count > 0
  const requester = data ? topRequesterLabel(data) : null

  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "calendar-consent-pending-widget-pulse-default",
        "flex-col h-full w-full p-4 gap-2 text-left",
        "hover:bg-surface-elevated/50 transition-colors",
        "focus-visible:outline-none focus-ring-accent",
      )}
      data-testid="calendar-consent-pending-default"
      data-tier="default"
    >
      {/* Header row — icon + eyebrow + count */}
      <div className="flex items-baseline justify-between gap-2">
        <span className="flex items-center gap-2 min-w-0">
          <UserCheck
            className={cn(
              "h-[18px] w-[18px] shrink-0",
              isActionable ? "text-accent" : "text-content-muted",
            )}
            strokeWidth={1.5}
            aria-hidden
          />
          <span className="text-micro uppercase tracking-wider text-content-muted">
            Requests
          </span>
        </span>
        <span
          className={cn(
            "font-plex-mono text-h3 font-medium tabular-nums shrink-0",
            isActionable ? "text-status-warning" : "text-content-muted",
          )}
          data-testid="calendar-consent-pending-count"
        >
          {isLoading ? "—" : count}
        </span>
      </div>

      {/* Body — top requester OR empty state */}
      {requester ? (
        <div className="flex-1 min-w-0">
          <p className="font-plex-sans text-body-sm font-medium text-content-strong truncate">
            {requester}
          </p>
          <p className="font-plex-sans text-caption text-content-muted truncate">
            requested calendar consent
          </p>
        </div>
      ) : (
        <div className="flex-1 min-w-0">
          <p
            className="font-plex-sans text-caption text-content-muted italic"
            data-testid="calendar-consent-pending-empty"
          >
            {emptyStateLabel()}
          </p>
        </div>
      )}

      {/* Footer link */}
      <span className="font-plex-sans text-caption text-accent">
        Review consent requests →
      </span>
    </button>
  )
}


// ── Compact-tier presentation (101-120px) ───────────────────────────


function CalendarConsentPendingCompact({
  data,
  isLoading,
  onClick,
}: {
  data: CalendarConsentPendingData | null
  isLoading: boolean
  onClick: () => void
}) {
  const count = data?.pending_consent_count ?? 0
  const isActionable = count > 0
  const requester = data ? topRequesterLabel(data) : null
  const subline = requester ?? emptyStateLabel()

  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "calendar-consent-pending-widget-pulse-compact",
        "flex-col h-full w-full p-3 gap-1 text-left",
        "hover:bg-surface-elevated/50 transition-colors",
        "focus-visible:outline-none focus-ring-accent",
      )}
      data-testid="calendar-consent-pending-compact"
      data-tier="compact"
    >
      <div className="flex items-baseline justify-between gap-2">
        <span className="flex items-center gap-1.5 min-w-0">
          <UserCheck
            className={cn(
              "h-4 w-4 shrink-0",
              isActionable ? "text-accent" : "text-content-muted",
            )}
            strokeWidth={1.5}
            aria-hidden
          />
          <span className="text-micro uppercase tracking-wider text-content-muted">
            Requests
          </span>
        </span>
        <span
          className={cn(
            "font-plex-mono text-body-sm font-medium tabular-nums shrink-0",
            isActionable ? "text-status-warning" : "text-content-muted",
          )}
        >
          {isLoading ? "—" : count}
        </span>
      </div>
      <p className="font-plex-sans text-caption text-content-muted truncate">
        {subline}
      </p>
    </button>
  )
}


// ── Ultra-compact tier (80-100px) ───────────────────────────────────


function CalendarConsentPendingUltraCompact({
  data,
  isLoading,
  onClick,
}: {
  data: CalendarConsentPendingData | null
  isLoading: boolean
  onClick: () => void
}) {
  const count = data?.pending_consent_count ?? 0
  const isActionable = count > 0
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "calendar-consent-pending-widget-pulse-ultra-compact",
        "flex-row items-center justify-between h-full w-full px-3 py-2 gap-2 text-left",
        "hover:bg-surface-elevated/50 transition-colors",
        "focus-visible:outline-none focus-ring-accent",
      )}
      data-testid="calendar-consent-pending-ultra-compact"
      data-tier="ultra-compact"
    >
      <span className="flex items-center gap-2 min-w-0">
        <UserCheck
          className={cn(
            "h-4 w-4 shrink-0",
            isActionable ? "text-accent" : "text-content-muted",
          )}
          strokeWidth={1.5}
          aria-hidden
        />
        <span className="text-micro uppercase tracking-wider text-content-muted">
          Requests
        </span>
      </span>
      <span
        className={cn(
          "font-plex-mono text-body-sm font-medium tabular-nums shrink-0",
          isActionable ? "text-status-warning" : "text-content-muted",
        )}
      >
        {isLoading ? "—" : count}
      </span>
    </button>
  )
}


// ── Spaces-pin (sidebar) presentation — single-tier, Pattern 1 ──────


function CalendarConsentPendingSpacesPin({
  data,
  isLoading,
  onClick,
}: {
  data: CalendarConsentPendingData | null
  isLoading: boolean
  onClick: () => void
}) {
  const count = data?.pending_consent_count ?? 0
  const isActionable = count > 0
  const requester = data ? topRequesterLabel(data) : null
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "flex items-center justify-between w-full gap-2 px-3 py-2",
        "hover:bg-accent-subtle/40 transition-colors rounded-[2px]",
        "focus-visible:outline-none focus-ring-accent",
      )}
      data-testid="calendar-consent-pending-spaces-pin"
    >
      <span className="flex items-center gap-2 min-w-0">
        <UserCheck
          className={cn(
            "h-4 w-4 shrink-0",
            isActionable ? "text-accent" : "text-content-muted",
          )}
          strokeWidth={1.5}
          aria-hidden
        />
        <span className="font-plex-sans text-body-sm text-content-base truncate">
          {requester || (count > 0 ? "Consent requests" : "No pending requests")}
        </span>
      </span>
      {count > 0 && (
        <span className="font-plex-mono text-caption font-medium tabular-nums text-status-warning shrink-0">
          {isLoading ? "—" : count}
        </span>
      )}
    </button>
  )
}


// ── Top-level dispatcher ────────────────────────────────────────────


interface CalendarConsentPendingWidgetProps {
  variant_id?: VariantId
  surface?: string
  config?: Record<string, unknown>
}


export function CalendarConsentPendingWidget({
  variant_id = "glance",
  surface,
}: CalendarConsentPendingWidgetProps) {
  void variant_id // unused for now (Glance-only); kept for shape parity
  const navigate = useNavigate()
  const { data, isLoading } = useWidgetData<CalendarConsentPendingData>(
    "/widget-data/calendar-consent-pending",
    { refreshInterval: 5 * 60 * 1000 }, // 5 min auto-refresh
  )

  const handleClick = () => {
    navigate(buildClickTarget(data))
  }

  // Sidebar (spaces_pin) renders single-tier Pattern 1
  if (surface === "spaces_pin") {
    return (
      <CalendarConsentPendingSpacesPin
        data={data}
        isLoading={isLoading}
        onClick={handleClick}
      />
    )
  }

  // Pulse / dashboard surfaces — three density tiers via @container
  // queries. All three render simultaneously; CSS dispatches visibility.
  return (
    <div
      className="h-full w-full"
      data-testid="calendar-consent-pending-widget"
    >
      <CalendarConsentPendingDefault
        data={data}
        isLoading={isLoading}
        onClick={handleClick}
      />
      <CalendarConsentPendingCompact
        data={data}
        isLoading={isLoading}
        onClick={handleClick}
      />
      <CalendarConsentPendingUltraCompact
        data={data}
        isLoading={isLoading}
        onClick={handleClick}
      />
    </div>
  )
}


// Default export for register.ts side-effect import
export default CalendarConsentPendingWidget

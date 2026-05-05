/**
 * CalendarGlanceWidget — Phase W-4b Layer 1 Calendar Step 5.
 *
 * Surfaces interpersonal-scheduling signals (responses awaiting +
 * cross-tenant invitations) across the user's accessible calendar
 * accounts. Per-primitive Glance widget per Pulse Communications
 * Layer canon (BRIDGEABLE_MASTER §3.26.16.10). Pattern parallels
 * EmailGlanceWidget verbatim (canonical Step 5 cross-surface
 * rendering precedent).
 *
 * Per [DESIGN_LANGUAGE.md §14.4-14.5](../../../../DESIGN_LANGUAGE.md):
 * three density tiers (canonical Pattern C convention):
 *   - Default (cell_height ≥ 121px) — Calendar icon + Calendar eyebrow
 *     + mono count + top inviter body (2 lines: name + tenant) +
 *     "Open calendar →" footer
 *   - Compact (101-120px) — header row + inviter collapsed to single
 *     line "primary — secondary"; footer dropped
 *   - Ultra-compact (80-100px) — single-row icon + label + count
 *
 * Per §14.2: Lucide `Calendar` icon canonical. 18×18 stroke-1.5 in
 * `text-content-muted` at rest, `text-accent` when count > 0.
 *
 * Per §14.3 typography: counts in `font-plex-mono`,
 * `text-status-warning` when actionable + `text-content-muted` when
 * zero. Default tier: `text-h3` size; Compact / Ultra-compact:
 * `text-body-sm`.
 *
 * Per [§12.6a Widget Interactivity Discipline](../../../../DESIGN_LANGUAGE.md):
 * view-only with click-through navigation. Single-event surface →
 * `/calendar/events/{id}`. Multi-event surface →
 * `/calendar?status=needs_action`. Empty + has access → `/calendar`.
 * Empty + no access → no-op.
 *
 * **Communications layer composition** (`communications_layer_service.py`
 * + LayerName "communications" literal extension) deferred to Phase
 * W-4b sequence step 6 per BRIDGEABLE_MASTER §3.26.6.4. Widget renders
 * today on home Pulse + any future scoped Pulse via §3.26.12.3
 * pulse_grid surface inheritance — no scoped-Pulse-specific code.
 *
 * Data source: `GET /api/v1/widget-data/calendar-glance` with auto-
 * refresh every 5 minutes via `useWidgetData`.
 */

import { useNavigate } from "react-router-dom"
import { Calendar } from "lucide-react"

import { useWidgetData } from "../useWidgetData"
import { cn } from "@/lib/utils"
import type { VariantId } from "@/components/widgets/types"


// ── Data shape (mirrors backend `get_calendar_glance` response) ────


export interface CalendarGlanceData {
  has_calendar_access: boolean
  pending_response_count: number
  cross_tenant_invitation_count: number
  top_inviter_email: string | null
  top_inviter_name: string | null
  top_inviter_tenant_label: string | null
  target_event_id: string | null
}


// ── Display helpers ─────────────────────────────────────────────────


/** Top-inviter display name — falls back from name → email → null. */
function topInviterLabel(data: CalendarGlanceData): string | null {
  if (data.top_inviter_name) return data.top_inviter_name
  if (data.top_inviter_email) return data.top_inviter_email
  return null
}


/** Build the click-through target URL based on widget state. */
function buildClickTarget(data: CalendarGlanceData | null): string {
  if (!data || !data.has_calendar_access) return "/calendar"
  if (data.target_event_id) return `/calendar/events/${data.target_event_id}`
  if (data.pending_response_count > 0) return "/calendar?status=needs_action"
  return "/calendar"
}


/** Empty-state copy per §14.3 — primitive empty-state when count=0. */
function emptyStateLabel(data: CalendarGlanceData | null): string {
  if (!data || !data.has_calendar_access) return "No calendar access"
  return "All responded"
}


// ── Default-tier presentation (≥121px) ──────────────────────────────


function CalendarGlanceDefault({
  data,
  isLoading,
  onClick,
}: {
  data: CalendarGlanceData | null
  isLoading: boolean
  onClick: () => void
}) {
  const count = data?.pending_response_count ?? 0
  const isActionable = count > 0
  const inviter = data ? topInviterLabel(data) : null
  const tenantLabel = data?.top_inviter_tenant_label ?? null

  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "calendar-glance-widget-pulse-default",
        "flex-col h-full w-full p-4 gap-2 text-left",
        "hover:bg-surface-elevated/50 transition-colors",
        "focus-visible:outline-none focus-ring-accent",
      )}
      data-testid="calendar-glance-default"
      data-tier="default"
    >
      {/* Header row — icon + eyebrow + count */}
      <div className="flex items-baseline justify-between gap-2">
        <span className="flex items-center gap-2 min-w-0">
          <Calendar
            className={cn(
              "h-[18px] w-[18px] shrink-0",
              isActionable ? "text-accent" : "text-content-muted",
            )}
            strokeWidth={1.5}
            aria-hidden
          />
          <span className="text-micro uppercase tracking-wider text-content-muted">
            Calendar
          </span>
        </span>
        <span
          className={cn(
            "font-plex-mono text-h3 font-medium tabular-nums shrink-0",
            isActionable ? "text-status-warning" : "text-content-muted",
          )}
          data-testid="calendar-glance-count"
        >
          {isLoading ? "—" : count}
        </span>
      </div>

      {/* Body — inviter excerpt OR empty state */}
      {inviter ? (
        <div className="flex-1 min-w-0">
          <p className="font-plex-sans text-body-sm font-medium text-content-strong truncate">
            {inviter}
          </p>
          {tenantLabel && (
            <p className="font-plex-sans text-caption text-content-muted truncate">
              {tenantLabel}
            </p>
          )}
        </div>
      ) : (
        <div className="flex-1 min-w-0">
          <p
            className="font-plex-sans text-caption text-content-muted italic"
            data-testid="calendar-glance-empty"
          >
            {emptyStateLabel(data)}
          </p>
        </div>
      )}

      {/* Footer link */}
      <span className="font-plex-sans text-caption text-accent">
        Open calendar →
      </span>
    </button>
  )
}


// ── Compact-tier presentation (101-120px) ───────────────────────────


function CalendarGlanceCompact({
  data,
  isLoading,
  onClick,
}: {
  data: CalendarGlanceData | null
  isLoading: boolean
  onClick: () => void
}) {
  const count = data?.pending_response_count ?? 0
  const isActionable = count > 0
  const inviter = data ? topInviterLabel(data) : null
  const tenantLabel = data?.top_inviter_tenant_label ?? null

  const inviterLine = inviter
    ? tenantLabel
      ? `${inviter} — ${tenantLabel}`
      : inviter
    : emptyStateLabel(data)

  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "calendar-glance-widget-pulse-compact",
        "flex-col h-full w-full p-3 gap-1 text-left",
        "hover:bg-surface-elevated/50 transition-colors",
        "focus-visible:outline-none focus-ring-accent",
      )}
      data-testid="calendar-glance-compact"
      data-tier="compact"
    >
      <div className="flex items-baseline justify-between gap-2">
        <span className="flex items-center gap-1.5 min-w-0">
          <Calendar
            className={cn(
              "h-4 w-4 shrink-0",
              isActionable ? "text-accent" : "text-content-muted",
            )}
            strokeWidth={1.5}
            aria-hidden
          />
          <span className="text-micro uppercase tracking-wider text-content-muted">
            Calendar
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
        {inviterLine}
      </p>
    </button>
  )
}


// ── Ultra-compact tier (80-100px) ───────────────────────────────────


function CalendarGlanceUltraCompact({
  data,
  isLoading,
  onClick,
}: {
  data: CalendarGlanceData | null
  isLoading: boolean
  onClick: () => void
}) {
  const count = data?.pending_response_count ?? 0
  const isActionable = count > 0
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "calendar-glance-widget-pulse-ultra-compact",
        "flex-row items-center justify-between h-full w-full px-3 py-2 gap-2 text-left",
        "hover:bg-surface-elevated/50 transition-colors",
        "focus-visible:outline-none focus-ring-accent",
      )}
      data-testid="calendar-glance-ultra-compact"
      data-tier="ultra-compact"
    >
      <span className="flex items-center gap-2 min-w-0">
        <Calendar
          className={cn(
            "h-4 w-4 shrink-0",
            isActionable ? "text-accent" : "text-content-muted",
          )}
          strokeWidth={1.5}
          aria-hidden
        />
        <span className="text-micro uppercase tracking-wider text-content-muted">
          Calendar
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


function CalendarGlanceSpacesPin({
  data,
  isLoading,
  onClick,
}: {
  data: CalendarGlanceData | null
  isLoading: boolean
  onClick: () => void
}) {
  const count = data?.pending_response_count ?? 0
  const isActionable = count > 0
  const inviter = data ? topInviterLabel(data) : null
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "flex items-center justify-between w-full gap-2 px-3 py-2",
        "hover:bg-accent-subtle/40 transition-colors rounded-[2px]",
        "focus-visible:outline-none focus-ring-accent",
      )}
      data-testid="calendar-glance-spaces-pin"
    >
      <span className="flex items-center gap-2 min-w-0">
        <Calendar
          className={cn(
            "h-4 w-4 shrink-0",
            isActionable ? "text-accent" : "text-content-muted",
          )}
          strokeWidth={1.5}
          aria-hidden
        />
        <span className="font-plex-sans text-body-sm text-content-base truncate">
          {inviter || (data?.has_calendar_access ? "All responded" : "Calendar")}
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


interface CalendarGlanceWidgetProps {
  variant_id?: VariantId
  surface?: string
  config?: Record<string, unknown>
}


export function CalendarGlanceWidget({
  variant_id = "glance",
  surface,
}: CalendarGlanceWidgetProps) {
  void variant_id // unused for now (Glance-only); kept for shape parity
  const navigate = useNavigate()
  const { data, isLoading } = useWidgetData<CalendarGlanceData>(
    "/widget-data/calendar-glance",
    { refreshInterval: 5 * 60 * 1000 }, // 5 min auto-refresh
  )

  const handleClick = () => {
    navigate(buildClickTarget(data))
  }

  // Sidebar (spaces_pin) renders single-tier Pattern 1
  if (surface === "spaces_pin") {
    return (
      <CalendarGlanceSpacesPin
        data={data}
        isLoading={isLoading}
        onClick={handleClick}
      />
    )
  }

  // Pulse / dashboard surfaces — three density tiers via @container
  // queries (canonical pattern per §13.4.1; see pulse-density.css).
  // All three render simultaneously; CSS dispatches visibility.
  return (
    <div
      className="h-full w-full"
      data-testid="calendar-glance-widget"
    >
      <CalendarGlanceDefault
        data={data}
        isLoading={isLoading}
        onClick={handleClick}
      />
      <CalendarGlanceCompact
        data={data}
        isLoading={isLoading}
        onClick={handleClick}
      />
      <CalendarGlanceUltraCompact
        data={data}
        isLoading={isLoading}
        onClick={handleClick}
      />
    </div>
  )
}


// Default export for register.ts side-effect import
export default CalendarGlanceWidget

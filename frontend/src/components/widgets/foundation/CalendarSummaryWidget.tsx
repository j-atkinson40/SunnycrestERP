/**
 * CalendarSummaryWidget — Phase W-4b Layer 1 Calendar Step 5.
 *
 * Pulse **Operational Layer** widget per BRIDGEABLE_MASTER §3.26.16.10.
 * Surfaces this-week schedule for operational coordination — NOT
 * individual response state (that belongs to `calendar_glance`
 * Communications Layer per §3.26.16.10 hybrid contribution).
 *
 * Per [DESIGN_LANGUAGE.md §14.10.1 + §14.4-14.5](../../../../DESIGN_LANGUAGE.md):
 * three density tiers (canonical Pattern C convention):
 *
 *   - **Default (cell_height ≥ 121px)** — CalendarDays icon + "Week
 *     schedule" eyebrow + total event count + next-event row + 7-day
 *     mini bar visualization + "View calendar →" footer.
 *
 *   - **Compact (101-120px)** — header row + single "Next: subject —
 *     relative time" line; mini bar dropped.
 *
 *   - **Ultra-compact (80-100px)** — icon + label + total count.
 *
 * Per §14.2: Lucide `CalendarDays` icon canonical. 18×18 stroke-1.5
 * in `text-content-muted` at rest, `text-accent` when there are
 * upcoming events.
 *
 * Per §14.3 typography: counts in `font-plex-mono`; per-day mini bars
 * sit on the warm `--accent-muted` baseline with active days lifting
 * to `--accent`.
 *
 * Per [§12.6a Widget Interactivity Discipline](../../../../DESIGN_LANGUAGE.md):
 * view-only with click-through navigation. Single click navigates to
 * `/calendar` (week view); next-event row click navigates to
 * `/calendar/events/{id}`.
 *
 * Data source: `GET /api/v1/widget-data/calendar-summary?days=7` with
 * 5-minute auto-refresh via `useWidgetData`.
 */

import { useNavigate } from "react-router-dom"
import { CalendarDays } from "lucide-react"

import { useWidgetData } from "../useWidgetData"
import { cn } from "@/lib/utils"
import type { VariantId } from "@/components/widgets/types"


// ── Data shape (mirrors backend `get_calendar_summary` response) ────


interface CalendarSummaryNextEvent {
  id: string
  subject: string
  start_at: string
  end_at: string
  location: string | null
}


interface CalendarSummaryDay {
  date: string
  event_count: number
  first_event_subject: string | null
}


export interface CalendarSummaryData {
  has_calendar_access: boolean
  window_days: number
  total_event_count: number
  next_event: CalendarSummaryNextEvent | null
  by_day: CalendarSummaryDay[]
}


// ── Display helpers ─────────────────────────────────────────────────


/** Relative-time formatter aligned with §14.3 micro-text typography. */
function relativeTime(iso: string): string {
  const then = new Date(iso).getTime()
  const now = Date.now()
  const diff = then - now
  const min = Math.round(diff / 60_000)
  if (min < 0) {
    const past = Math.abs(min)
    if (past < 60) return `${past} min ago`
    const hr = Math.round(past / 60)
    if (hr < 24) return `${hr}h ago`
    const day = Math.round(hr / 24)
    return `${day}d ago`
  }
  if (min < 60) return `in ${min} min`
  const hr = Math.round(min / 60)
  if (hr < 24) return `in ${hr}h`
  const day = Math.round(hr / 24)
  if (day < 7) return `in ${day}d`
  return new Date(iso).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  })
}


/** Single-character weekday label for the mini bar (Mon, Tue, … → M T W T F S S). */
function weekdayChar(iso: string): string {
  const d = new Date(`${iso}T12:00:00`)
  const map = ["S", "M", "T", "W", "T", "F", "S"]
  return map[d.getDay()] ?? ""
}


/** Empty-state copy per §14.3. */
function emptyStateLabel(data: CalendarSummaryData | null): string {
  if (!data || !data.has_calendar_access) return "No calendar access"
  return "No events this week"
}


// ── Default-tier presentation (≥121px / Brief) ──────────────────────


function CalendarSummaryDefault({
  data,
  isLoading,
  onClickWidget,
  onClickNextEvent,
}: {
  data: CalendarSummaryData | null
  isLoading: boolean
  onClickWidget: () => void
  onClickNextEvent: (eventId: string) => void
}) {
  const total = data?.total_event_count ?? 0
  const hasEvents = total > 0
  const nextEvent = data?.next_event ?? null
  const byDay = data?.by_day ?? []
  const maxDayCount = byDay.reduce(
    (m, d) => (d.event_count > m ? d.event_count : m),
    0,
  )

  return (
    <div
      className={cn(
        "calendar-summary-widget-pulse-default",
        "flex-col h-full w-full p-4 gap-3",
      )}
      data-testid="calendar-summary-default"
      data-tier="default"
    >
      {/* Header — icon + eyebrow + count */}
      <div className="flex items-baseline justify-between gap-2">
        <span className="flex items-center gap-2 min-w-0">
          <CalendarDays
            className={cn(
              "h-[18px] w-[18px] shrink-0",
              hasEvents ? "text-accent" : "text-content-muted",
            )}
            strokeWidth={1.5}
            aria-hidden
          />
          <span className="text-micro uppercase tracking-wider text-content-muted">
            Week schedule
          </span>
        </span>
        <span
          className={cn(
            "font-plex-mono text-h3 font-medium tabular-nums shrink-0",
            hasEvents ? "text-content-strong" : "text-content-muted",
          )}
          data-testid="calendar-summary-total"
        >
          {isLoading ? "—" : total}
        </span>
      </div>

      {/* Next-event row — clickable to event detail */}
      {nextEvent ? (
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation()
            onClickNextEvent(nextEvent.id)
          }}
          className={cn(
            "flex flex-col gap-0.5 min-w-0 text-left rounded-sm",
            "hover:bg-surface-elevated/50 px-2 -mx-2 py-1 -my-1",
            "focus-visible:outline-none focus-ring-accent",
            "transition-colors duration-quick ease-settle",
          )}
          data-testid="calendar-summary-next-event"
        >
          <p className="font-plex-sans text-body-sm font-medium text-content-strong truncate">
            {nextEvent.subject}
          </p>
          <p className="font-plex-mono text-caption text-content-muted truncate tabular-nums">
            {relativeTime(nextEvent.start_at)}
            {nextEvent.location ? ` · ${nextEvent.location}` : ""}
          </p>
        </button>
      ) : (
        <p
          className="font-plex-sans text-caption text-content-muted italic"
          data-testid="calendar-summary-empty"
        >
          {emptyStateLabel(data)}
        </p>
      )}

      {/* Per-day mini bar — visual summary across window */}
      {byDay.length > 0 && (
        <div
          className="flex items-end gap-1 h-7 mt-auto"
          data-testid="calendar-summary-by-day"
          aria-label="Events per day this week"
        >
          {byDay.map((d) => {
            // Bar height proportional to maxDayCount; min 4px so empty
            // days stay visible as warm baseline.
            const ratio = maxDayCount > 0 ? d.event_count / maxDayCount : 0
            const heightPx = d.event_count === 0 ? 4 : Math.max(8, Math.round(ratio * 24))
            const isActive = d.event_count > 0
            return (
              <div
                key={d.date}
                className="flex flex-col items-center gap-0.5 flex-1 min-w-0"
                title={`${d.event_count} event${d.event_count === 1 ? "" : "s"} on ${d.date}`}
              >
                <div
                  className={cn(
                    "w-full rounded-[1px] transition-colors duration-quick ease-settle",
                    isActive ? "bg-accent" : "bg-accent-muted/30",
                  )}
                  style={{ height: `${heightPx}px` }}
                  aria-hidden
                />
                <span className="font-plex-mono text-micro text-content-subtle tabular-nums">
                  {weekdayChar(d.date)}
                </span>
              </div>
            )
          })}
        </div>
      )}

      {/* Footer link */}
      <button
        type="button"
        onClick={onClickWidget}
        className={cn(
          "font-plex-sans text-caption text-accent text-left",
          "hover:underline focus-visible:outline-none focus-ring-accent rounded-sm",
        )}
      >
        View calendar →
      </button>
    </div>
  )
}


// ── Compact-tier presentation (101-120px) ───────────────────────────


function CalendarSummaryCompact({
  data,
  isLoading,
  onClickWidget,
}: {
  data: CalendarSummaryData | null
  isLoading: boolean
  onClickWidget: () => void
}) {
  const total = data?.total_event_count ?? 0
  const hasEvents = total > 0
  const nextEvent = data?.next_event ?? null

  const subline = nextEvent
    ? `Next: ${nextEvent.subject} · ${relativeTime(nextEvent.start_at)}`
    : emptyStateLabel(data)

  return (
    <button
      type="button"
      onClick={onClickWidget}
      className={cn(
        "calendar-summary-widget-pulse-compact",
        "flex-col h-full w-full p-3 gap-1 text-left",
        "hover:bg-surface-elevated/50 transition-colors",
        "focus-visible:outline-none focus-ring-accent",
      )}
      data-testid="calendar-summary-compact"
      data-tier="compact"
    >
      <div className="flex items-baseline justify-between gap-2">
        <span className="flex items-center gap-1.5 min-w-0">
          <CalendarDays
            className={cn(
              "h-4 w-4 shrink-0",
              hasEvents ? "text-accent" : "text-content-muted",
            )}
            strokeWidth={1.5}
            aria-hidden
          />
          <span className="text-micro uppercase tracking-wider text-content-muted">
            Week
          </span>
        </span>
        <span
          className={cn(
            "font-plex-mono text-body-sm font-medium tabular-nums shrink-0",
            hasEvents ? "text-content-strong" : "text-content-muted",
          )}
        >
          {isLoading ? "—" : total}
        </span>
      </div>
      <p className="font-plex-sans text-caption text-content-muted truncate">
        {subline}
      </p>
    </button>
  )
}


// ── Ultra-compact tier (80-100px) ───────────────────────────────────


function CalendarSummaryUltraCompact({
  data,
  isLoading,
  onClickWidget,
}: {
  data: CalendarSummaryData | null
  isLoading: boolean
  onClickWidget: () => void
}) {
  const total = data?.total_event_count ?? 0
  const hasEvents = total > 0
  return (
    <button
      type="button"
      onClick={onClickWidget}
      className={cn(
        "calendar-summary-widget-pulse-ultra-compact",
        "flex-row items-center justify-between h-full w-full px-3 py-2 gap-2 text-left",
        "hover:bg-surface-elevated/50 transition-colors",
        "focus-visible:outline-none focus-ring-accent",
      )}
      data-testid="calendar-summary-ultra-compact"
      data-tier="ultra-compact"
    >
      <span className="flex items-center gap-2 min-w-0">
        <CalendarDays
          className={cn(
            "h-4 w-4 shrink-0",
            hasEvents ? "text-accent" : "text-content-muted",
          )}
          strokeWidth={1.5}
          aria-hidden
        />
        <span className="text-micro uppercase tracking-wider text-content-muted">
          Week
        </span>
      </span>
      <span
        className={cn(
          "font-plex-mono text-body-sm font-medium tabular-nums shrink-0",
          hasEvents ? "text-content-strong" : "text-content-muted",
        )}
      >
        {isLoading ? "—" : total}
      </span>
    </button>
  )
}


// ── Spaces-pin (sidebar) presentation — single-tier, Pattern 1 ──────


function CalendarSummarySpacesPin({
  data,
  isLoading,
  onClick,
}: {
  data: CalendarSummaryData | null
  isLoading: boolean
  onClick: () => void
}) {
  const total = data?.total_event_count ?? 0
  const hasEvents = total > 0
  const nextEvent = data?.next_event ?? null
  const label = nextEvent
    ? nextEvent.subject
    : data?.has_calendar_access
      ? "No events this week"
      : "Week schedule"
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "flex items-center justify-between w-full gap-2 px-3 py-2",
        "hover:bg-accent-subtle/40 transition-colors rounded-[2px]",
        "focus-visible:outline-none focus-ring-accent",
      )}
      data-testid="calendar-summary-spaces-pin"
    >
      <span className="flex items-center gap-2 min-w-0">
        <CalendarDays
          className={cn(
            "h-4 w-4 shrink-0",
            hasEvents ? "text-accent" : "text-content-muted",
          )}
          strokeWidth={1.5}
          aria-hidden
        />
        <span className="font-plex-sans text-body-sm text-content-base truncate">
          {label}
        </span>
      </span>
      {total > 0 && (
        <span className="font-plex-mono text-caption font-medium tabular-nums text-content-muted shrink-0">
          {isLoading ? "—" : total}
        </span>
      )}
    </button>
  )
}


// ── Top-level dispatcher ────────────────────────────────────────────


interface CalendarSummaryWidgetProps {
  variant_id?: VariantId
  surface?: string
  config?: Record<string, unknown>
}


export function CalendarSummaryWidget({
  variant_id = "brief",
  surface,
  config,
}: CalendarSummaryWidgetProps) {
  void variant_id // unused for now; kept for shape parity
  const navigate = useNavigate()
  const days =
    typeof config?.days === "number" && Number.isFinite(config.days)
      ? Math.max(1, Math.min(31, Math.round(config.days)))
      : 7
  const { data, isLoading } = useWidgetData<CalendarSummaryData>(
    `/widget-data/calendar-summary?days=${days}`,
    { refreshInterval: 5 * 60 * 1000 }, // 5 min auto-refresh
  )

  const handleClickWidget = () => navigate("/calendar")
  const handleClickNextEvent = (eventId: string) =>
    navigate(`/calendar/events/${eventId}`)

  // Sidebar (spaces_pin) renders single-tier Pattern 1
  if (surface === "spaces_pin") {
    return (
      <CalendarSummarySpacesPin
        data={data}
        isLoading={isLoading}
        onClick={handleClickWidget}
      />
    )
  }

  // Pulse / dashboard surfaces — three density tiers via @container
  // queries. All three render simultaneously; CSS dispatches visibility.
  return (
    <div
      className="h-full w-full"
      data-testid="calendar-summary-widget"
    >
      <CalendarSummaryDefault
        data={data}
        isLoading={isLoading}
        onClickWidget={handleClickWidget}
        onClickNextEvent={handleClickNextEvent}
      />
      <CalendarSummaryCompact
        data={data}
        isLoading={isLoading}
        onClickWidget={handleClickWidget}
      />
      <CalendarSummaryUltraCompact
        data={data}
        isLoading={isLoading}
        onClickWidget={handleClickWidget}
      />
    </div>
  )
}


// Default export for register.ts side-effect import
export default CalendarSummaryWidget
